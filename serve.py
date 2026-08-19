#!/usr/bin/env python3
"""Static server + local speech-to-text for Resonance.

Listeners:
  One per NETWORK PROFILE, and each carries exactly ONE endpoint: one
  assistant, one port. Ports were shareable once — several endpoints on one,
  told apart by wake word — and that went when authentication became a
  property of the port, because a door with two assistants behind it can only
  have one lock and would have to answer for the looser of them. The profile
  nominated DEFAULT is where an endpoint naming none of them answers, and an
  upgrade turns the ports an install already had into one called "Display"
  (9701, with 9700 redirecting to it).

  HTTPS wherever a certificate exists, because getUserMedia is refused on an
  insecure origin — except on loopback, which the browser already treats as
  secure.

  ADMIN     (default 9702) the configuration interface, and the only port
                           still configured in app.json. It stays there
                           deliberately: it is the way back in when what is in
                           a profile is wrong.

  PORT / HTTPS_PORT / ADMIN_PORT in the environment still override all of it,
  and PORT alone still shifts all three (PORT, PORT+1, PORT+2) so a second
  instance needs no stored configuration of its own.

Two independent settings decide what this is: `bind` (loopback | address |
everything) and `auth` (none | accounts). They are deliberately not one
"mode" — a single label covering both starts lying the moment somebody
changes half of it.

Bound to loopback, no certificate is involved: browsers already treat
http://localhost as a secure origin, so the microphone works, nothing crosses
a network, and the admin interface is served over plain HTTP. Anywhere else
the admin listener is HTTPS-only and refuses to start without a certificate —
it takes a password and holds the assistant's API key, and neither may cross
a network in the clear. If it is missing from the startup banner, run
make-cert.sh. There is no way to write settings from the public listeners —
they serve the display and answer GET /settings, nothing more.

Reachable beyond this machine with no sign-in is permitted and warned about
loudly, every startup, in the panel and across the display itself.

POST /stt  accepts an audio blob and returns {"text": "..."} transcribed by
faster-whisper running HERE. Nothing is sent to any third party — this exists
specifically to avoid the browser's SpeechRecognition, which ships audio off
to Google. It is served from the same origin as the page so there is no CORS
and no mixed-content problem.

The HTTPS listener only starts if cert.pem/key.pem sit next to this file; see
make-cert.sh. A self-signed cert throws one browser warning — accept it and
the origin counts as secure from then on.

Plain `python3 -m http.server` also honours conditional GETs, so a browser can
sit on a cached copy of index.html and you end up debugging code that is no
longer running. This sends no-store on everything instead.
"""
import base64, contextlib, functools, hashlib, hmac, http.cookies, inspect, \
       json, os, re, \
       secrets, socket, ssl, subprocess, sys, tempfile, threading, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import manual                            # the manual, and its PDF writer

ROOT = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(ROOT, "settings.json")
USERS_PATH = os.path.join(ROOT, "users.json")
APP_PATH = os.path.join(ROOT, "app.json")
BACKEND_PATH = os.path.join(ROOT, "backend.json")
_settings_lock = threading.Lock()
_app_lock = threading.Lock()

# ------------------------------------------------------------------ backend
# Which assistant answers, and how to reach it. Deliberately NOT part of
# settings.json: that document is world-readable by design — every viewer
# builds their interface from it — so an API key placed there would be handed
# to anyone who opens the page. Same reasoning that put accounts in their own
# file. This one is admin-only and the key never leaves the server.
BACKEND_DEFAULTS = {
    "provider": "demo",                 # demo | openai | anthropic
    "base_url": "http://127.0.0.1:11434/v1",
    "model": "",
    "api_key": "",
    # A voice front-end reads the answer aloud, so the shape of the reply
    # matters as much as its content: markdown, bullets and code fences are
    # noise when spoken. Say so up front rather than stripping it after.
    "system": ("You are a spoken assistant. Answer in one or two short "
               "sentences unless asked for more. Write plain prose only — no "
               "markdown, lists, headings, or emoji — because your reply is "
               "read aloud."),
    "max_tokens": 400,
    "temperature": 0.4,
    # A cold model can take half a minute to load before it says anything.
    "timeout": 120,
    # An Ollama extension, accepted on its OpenAI-compatible path: hold the
    # model resident so the first question after a quiet spell is not the slow
    # one. Blank it for a hosted provider, which will reject unknown fields.
    "keep_alive": "30m",
    "history_turns": 8,
    # Which of Home Assistant's conversation agents answers. Blank is its
    # configured default. It belongs to the connection rather than to the
    # route because it is part of the address: the same box with two agents
    # is two destinations.
    "agent_id": "",
}
OPENAI_DIALECT = ("openai",)            # one shape, many vendors — see ask_backend
# Anthropic is its own shape, not a dialect of the above: the system prompt is a
# top-level field rather than a message, the key rides an x-api-key header, and
# the reply is a list of content blocks. It gets its own branch.
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_BASE = "https://api.anthropic.com"
# Home Assistant is an adapter, not a second concept. Its conversation API is
# chat-shaped — one POST with a bearer token, text in and text out — so it
# reaches the display through the same machinery as everything else. Inventing
# an "action target" beside the adapter would be a second mechanism for
# something the first one already does.
HOMEASSISTANT = "homeassistant"
PROVIDERS = ("demo", "anthropic", HOMEASSISTANT) + OPENAI_DIALECT
MAX_HISTORY = 24                        # hard ceiling regardless of configuration

# ------------------------------------------------------------ app settings
# How the server itself is wired, as opposed to how the interface looks.
# Editable from the admin page, but nothing here can take effect until the
# process restarts — you cannot move the floor you are standing on.
APP_DEFAULTS = {
    "http_port": 9700,               # the display, no microphone
    "https_port": 9701,              # the display in full
    "admin_port": 9702,              # this interface
    # Minutes, and a short default on purpose. An admin session is a window
    # onto a configuration everyone else is looking at the results of; it
    # should last a piece of work, not a working day. The panel signs you
    # back in without ceremony, which is what makes a short one bearable.
    "session_idle_minutes": 30,
    # ---- what it is reachable at, and what it takes to get in ----
    # Two settings, deliberately not one "mode". Binding and authentication
    # are independent, and a single label collapsing them starts lying the
    # moment somebody changes the binding: "personal" would still read
    # personal after being pointed at every interface on the machine. The
    # interface reports the actual pair instead of a name for it.
    #
    # Both default to what this server has always done, so an existing
    # install comes back up unchanged after an upgrade.
    "bind": "everything",            # loopback | address | everything
    "bind_address": "",              # the one address, when bind == "address"
    # ---- staying up unattended ----
    # A display at rest issues no requests at all, so without a poll an outage
    # would end and the screen would stay broken until somebody walked up and
    # spoke to it. The same poll keeps "last seen" fresh, gives the server
    # somewhere to answer "reload yourself", and is what makes a dead screen
    # noticeable from the panel rather than from the hallway.
    "poll_seconds": 20,
    # How many times a request tries before the display says so, and how long
    # it waits between attempts. Three is right for a restart and wrong for a
    # severed cable, so both are settings rather than constants.
    "retry_attempts": 3,
    "retry_seconds": 4,
    # A forced refresh, because a tab that never reloads accumulates. "HH:MM"
    # on the DEVICE's own clock, for the same reason a screensaver's dark hours
    # are read there: a building can span time zones and a screen's night is
    # the night outside it, not the server's.
    #
    # EMPTY IS OFF, and off is the default. A nightly reload is a net under
    # work not yet done rather than something every install needs, and an
    # upgrade that silently started reloading every screen in a building at
    # four in the morning would be this deciding something nobody asked for.
    "refresh_at": "",
    # …spread over this many minutes, or zero for all at once. Twelve tablets
    # reconnecting in the same second is a load this server did not previously
    # have; each screen takes its own offset inside the window from its own id,
    # so the spread is stable rather than re-rolled on every reload.
    "refresh_stagger": 0,
    # And the server's own, "HH:MM" on ITS clock — this one is about one
    # machine rather than twelve screens, so the machine's clock is the right
    # one. Empty is off, and off is the default.
    #
    # It is a HAND-OVER, not a stop: see do_scheduled_restart. Nothing
    # supervises this process, so a setting that only stopped the server would
    # be a setting that ended the service at three in the morning.
    "restart_at": "",
    # ---- what the panel reads back ----
    # How much of the log the panel shows. A setting rather than the constant
    # it was, because the right amount is a property of the deployment: a house
    # with three screens wants the lot, and a building with forty wants the
    # last screenful of a file that is mostly check-ins. It bounds the ANSWER,
    # not the file — see LOG_TAIL_BYTES, which bounds the read.
    "log_lines": 800,
}
#: (low, high) for the numbers above — the ones CLAMPED rather than refused,
#: because a number outside the range is somebody nudging a field rather than a
#: configuration that would stop the server coming up. A poll faster than a
#: couple of seconds is a denial of service somebody configured by accident;
#: one slower than five minutes is a screen that stays dead through a lunch
#: break. The log's floor is a screenful and its ceiling is what a browser will
#: render without becoming the reason the panel is slow.
UNATTENDED_LIMITS = {"poll_seconds": (2, 300), "retry_attempts": (1, 10),
                     "retry_seconds": (1, 60), "refresh_stagger": (0, 240),
                     "log_lines": (50, 5000)}
PORT_MIN, PORT_MAX = 1024, 65535     # below 1024 needs root; this runs as you
SESSION_MIN, SESSION_MAX = 5, 480    # minutes: below 5 is unusable, above 8h absurd
BIND_MODES = ("loopback", "address", "everything")
#: TWO RUNGS. Nothing at the door, or accounts with roles.
#:
#: There were three. The middle one was a single PIN for the whole panel, and
#: it went with every other PIN in this product: it could not say WHO did a
#: thing — the log wrote "(single PIN)" rather than naming anybody — and the
#: deployment it existed for, the one with a single administrator, is an
#: account with one member. That is a login screen either way, and one of the
#: two ways left a hole in the log.
#:
#: An install saved on the old middle rung comes up on `accounts`; see
#: read_app. The first-run password is minted the same way it is for any other
#: install that has no account yet.
#: There is no deployment-wide sign-in setting any more, in either
#: direction. The PANEL always asks — it holds the API key and every
#: credential, and a switch that opens it is a switch somebody leaves on. The
#: DISPLAYS ask per endpoint, on `needs_signin`, because "must there be a
#: person" is a property of the thing being reached rather than of the server:
#: three assistants on one box can legitimately want three different answers,
#: and one switch covering all of them could only ever be set to the strictest.
#:
#: `auth` is dropped from app.json on read. A stored value is ignored rather
#: than migrated: there is nothing left for it to mean.
LOOPBACK = "127.0.0.1"


def bind_host(cfg):
    """The address the listeners actually bind. Binding one address rather
    than every interface is worth doing on its own account: a laptop that
    later joins another network does not follow you onto it."""
    if cfg.get("bind") == "loopback":
        return LOOPBACK
    if cfg.get("bind") == "address" and cfg.get("bind_address"):
        return cfg["bind_address"]
    return "0.0.0.0"


def exposed(cfg):
    """Can anything other than this machine reach it? The question that
    decides whether skipping authentication is structural or a risk."""
    return bind_host(cfg) != LOOPBACK


def posture_warning(cfg):
    """The one arrangement that is allowed but should never be quiet: reachable
    from the network, and no sign-in in front of the DISPLAYS. Not refused —
    somebody may want exactly this on a network they control — but a laptop
    configured this way that later joins an office network must say so.

    It no longer says anything about the configuration page. That is always
    signed into, whatever this setting is, so the old wording — "anyone who can
    reach this machine can change its configuration" — stopped being true."""
    if exposed(cfg) and any(not r.get("needs_signin")
                            for r in read_routes()["routes"].values()
                            if r.get("enabled", True)):
        where = ("every interface on this machine" if bind_host(cfg) == "0.0.0.0"
                 else bind_host(cfg))
        return ("Reachable at %s, and at least one assistant can be used "
                "without signing in — anyone who can reach this machine can "
                "use it, and whatever it costs to run. The admin panel is not "
                "affected: that always asks." % where)
    return ""


def read_app():
    cfg = dict(APP_DEFAULTS)
    try:
        with open(APP_PATH) as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            # This was `session_idle_hours` until the unit changed. Carry the
            # stored value across rather than dropping it: silently shortening
            # somebody's session is the safe direction, but silently REWRITING
            # a security setting they chose is not something to do quietly —
            # the migrated number shows up in the panel for them to lower.
            if "session_idle_minutes" not in stored and "session_idle_hours" in stored:
                try:
                    cfg["session_idle_minutes"] = min(
                        SESSION_MAX, max(SESSION_MIN,
                                         int(float(stored["session_idle_hours"]) * 60)))
                except (TypeError, ValueError):
                    pass
            cfg.update({k: v for k, v in stored.items() if k in APP_DEFAULTS})
    except (OSError, ValueError):
        pass
    # THE MIDDLE RUNG IS GONE. An install saved on the single panel PIN comes
    # up on accounts rather than refusing to start or, worse, falling through
    # to no sign-in at all — a removed authentication mode must never fail
    # OPEN. Read-time only and the file is not rewritten: the panel shows
    # `accounts` and the admin's next save is what makes it permanent.
    return cfg


def write_app(cfg):
    with _app_lock:
        tmp = APP_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(cfg, fh, indent=2, sort_keys=True)
        os.replace(tmp, APP_PATH)


def port_free(p, host="0.0.0.0"):
    """Can we actually bind it? A port already taken by something else would
    otherwise pass validation and only fail at the next restart — by which
    point the admin interface is gone and the fix is editing JSON on the box
    by hand. Ports this process already holds are its own and count as free.

    Tested against the address that will actually be bound: a port held by
    something else on a different interface does not collide with loopback,
    and refusing it would reject a configuration that works."""
    import socket
    if p in (RUNNING.get("http_port"), RUNNING.get("https_port"),
             RUNNING.get("admin_port")):
        return True
    # …and so is a socket this process is already holding — but only the same
    # socket. Asked WITHOUT the address, this said "9701 is mine" about every
    # address on the machine, so moving a profile onto an address where some
    # OTHER process holds that port would have been allowed and then failed to
    # bind at the next restart. See holding_it.
    if holding_it(host, p):
        return True
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, p))
        return True
    except OSError:
        return False
    finally:
        s.close()


def local_addresses():
    """The IPv4 addresses this machine answers on, offered to the panel so an
    address can be chosen rather than typed. Typing one by hand is a way to
    configure a server that will not start."""
    import socket
    found = {LOOPBACK}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass
    # gethostname() only finds an address that has a matching line in the
    # hosts file, which on a plain server install is often none of them.
    # Asking the routing table which source address an outbound connection
    # would take finds the real one regardless. Nothing is sent: connect() on
    # a UDP socket only fixes the route.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))       # TEST-NET-1: reserved, never routed
        found.add(s.getsockname()[0])
    except OSError:
        pass
    finally:
        s.close()
    return sorted(found)


def holding_it(host, port):
    """Is this exact listening socket one this process already has?

    The question a profile's save has to ask is not "is this port free" but
    "will this port be free once I have restarted", and the difference is
    entirely the sockets this process is holding right now. Three ways one of
    ours covers the address being asked about:

    - the same pair, which is a profile being edited without moving its socket
    - our WILDCARD on that port, which is what ANY binds and what makes a
      bind test on any single address fail while we are up
    - the request being the wildcard while we hold that port on some address,
      which is a profile moving the other way, off an address onto ANY

    Anything else is somebody else's, and gets a real bind test."""
    if (host, port) in _BOUND or ("0.0.0.0", port) in _BOUND:
        return True
    return host == "0.0.0.0" and any(pp == port for _, pp in _BOUND)


def local_interfaces():
    """Every IPv4 address this machine has, with the interface carrying it, as
    [(address, interface)] — so the panel can offer *10.0.0.4 · eth0* rather
    than a bare number nobody can place.

    Read straight from the kernel with an ioctl rather than by shelling out to
    `ip` or taking a dependency: this server has none, and one for a list of
    addresses would be a poor first. Anything it cannot answer for falls back
    to the addresses alone, which is what was offered before this existed."""
    import socket
    out, seen = [], set()
    try:
        import fcntl, struct
        SIOCGIFADDR = 0x8915
        for _, name in socket.if_nameindex():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                packed = fcntl.ioctl(
                    s.fileno(), SIOCGIFADDR,
                    struct.pack("256s", name.encode()[:15]))
                addr = socket.inet_ntoa(packed[20:24])
            except OSError:
                continue                 # no IPv4 on this interface
            finally:
                s.close()
            if addr not in seen:
                seen.add(addr)
                out.append((addr, name))
    except Exception:
        pass
    for addr in local_addresses():       # anything the ioctl route missed
        if addr not in seen:
            seen.add(addr)
            out.append((addr, ""))
    return out


def net_host(vals, fallback):
    """The address a network profile binds.

    Empty means ANY, which is this server's own binding. And a named address
    is only honoured while the server is not pinned tighter than it: the
    comment here used to claim a profile never reaches further than the app it
    belongs to, and the code did not enforce it — set the server to THIS
    MACHINE ONLY and a profile naming a LAN address would have bound the LAN
    address anyway, which is that setting quietly not meaning what it says.

    Bound to one address, that address wins for everything. Bound to
    everything, a profile may choose. There is no arrangement where a profile
    is offered a reach the app was told not to have."""
    addr = str((vals or {}).get("address") or "").strip()
    if fallback not in ("0.0.0.0", ""):
        return fallback              # the app is pinned; nothing outruns it
    return addr or fallback


def port_free_anywhere(port, addrs):
    """Free on EVERY one of these addresses, which is what ANY has to mean.

    ANY binds the wildcard, and the kernel refuses a wildcard bind when the
    port is held on even one address. So a rule of "allowed if something can
    carry it" would have saved a profile that then could not come up — the
    panel saying yes and the server saying no at the next restart, in the log,
    where nobody was looking.

    Tested per address rather than by binding 0.0.0.0 once, because the answer
    has to say WHICH address is holding it. A refusal naming the port and not
    the address leaves somebody to go and find it."""
    taken = [a for a in addrs if not port_free(port, a)]
    return (not taken, taken)


def address_bindable(addr):
    """Is this address one this machine actually has? An address that is not
    is the same failure as a taken port — it passes validation, and then the
    server will not start, with the admin interface gone along with it."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return False
    try:
        s.bind((addr, 0))       # port 0: the kernel picks, we only test the address
        return True
    except OSError:
        return False
    finally:
        s.close()


def read_backend():
    """The one-assistant document this server had before routes. Read once,
    by the migration that turns it into route one, and never written again —
    but not deleted either, because an upgrade that removes the file it read
    from leaves nothing to go back to if the migration was wrong."""
    cfg = dict(BACKEND_DEFAULTS)
    try:
        with open(BACKEND_PATH) as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            cfg.update({k: v for k, v in stored.items() if k in BACKEND_DEFAULTS})
    except (OSError, ValueError):
        pass
    return cfg


def validate_backend(obj, current):
    """Returns (config, error). Refuses a configuration that cannot work,
    rather than accepting it and failing later in front of somebody.

    Still one function after routes arrived, and deliberately: one adapter
    configuration is one adapter configuration whether the server holds one
    of them or six. validate_route calls this for a route's connection half
    and adds the name and the wake word on top."""
    cfg = dict(current)
    for k in ("provider", "base_url", "model", "system", "keep_alive",
              "agent_id"):
        if k in obj:
            cfg[k] = str(obj[k] or "").strip()
    if cfg["provider"] not in PROVIDERS:
        return None, "unknown provider '%s'" % cfg["provider"]
    for k, lo, hi in (("max_tokens", 16, 8000), ("timeout", 5, 600),
                      ("history_turns", 0, MAX_HISTORY)):
        if k in obj:
            try:
                v = int(obj[k])
            except (TypeError, ValueError):
                return None, "%s must be a whole number" % k.replace("_", " ")
            if not (lo <= v <= hi):
                return None, "%s must be between %d and %d" % (
                    k.replace("_", " "), lo, hi)
            cfg[k] = v
    if "temperature" in obj:
        try:
            t = float(obj["temperature"])
        except (TypeError, ValueError):
            return None, "temperature must be a number"
        if not (0.0 <= t <= 2.0):
            return None, "temperature must be between 0 and 2"
        cfg["temperature"] = t
    if obj.get("clear_key"):
        cfg["api_key"] = ""
    elif str(obj.get("api_key") or "").strip():
        cfg["api_key"] = str(obj["api_key"]).strip()

    # A base URL and a key belong to a provider, and neither survives a
    # change of one. Left alone, a route switched to Anthropic would keep
    # whatever endpoint it had — so the panel's default local URL would take
    # an Anthropic key, on an x-api-key header, to a model on this network.
    # That is worse than any error, because it looks like it worked.
    if cfg["provider"] != (current.get("provider") or "demo"):
        if "base_url" not in obj:
            # Home Assistant has no default address — it is wherever this
            # house put it — so switching to it clears the field rather than
            # leaving a model's endpoint sitting under a new label.
            cfg["base_url"] = ("" if cfg["provider"] == HOMEASSISTANT else
                               ANTHROPIC_BASE if cfg["provider"] == "anthropic"
                               else BACKEND_DEFAULTS["base_url"])
        if not str(obj.get("api_key") or "").strip():
            cfg["api_key"] = ""

    if cfg["provider"] != "demo":
        if cfg["provider"] == HOMEASSISTANT:
            # No model field: Home Assistant has no model of its own. What it
            # has is the harness — a conversation agent, and behind an
            # LLM-backed one a model that HA is configured with, not this
            # server. Asking for one here would be a field with nowhere to go.
            if not cfg["base_url"]:
                return None, ("Home Assistant needs its address, e.g. "
                              "http://homeassistant.local:8123")
            # Unreachable and rejected are the two ways this fails in front of
            # somebody, and the second one is preventable here.
            if not cfg["api_key"]:
                return None, "Home Assistant needs a long-lived access token"
        elif not cfg["model"]:
            return None, "a model is required"
        if cfg["provider"] == "anthropic":
            # There is exactly one endpoint, so an empty field is a blank to
            # fill in rather than an error to report.
            cfg["base_url"] = cfg["base_url"] or ANTHROPIC_BASE
            # A hosted-only provider with no key cannot answer, and finding
            # that out means somebody stood in front of the screen and asked
            # it something. Say so at the point of saving instead.
            if not cfg["api_key"]:
                return None, "Anthropic needs an API key"
        from urllib.parse import urlparse
        if urlparse(cfg["base_url"]).scheme not in ("http", "https"):
            return None, "the base URL must start with http:// or https://"
    return cfg, None


def _post_json(url, payload, headers, timeout):
    """One HTTP call on the standard library. No dependency is worth adding
    for this, and the visualiser's zero-dependency rule deserves company."""
    import urllib.error, urllib.request
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers=dict(headers, **{"Content-Type": "application/json"}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        # The provider's own message is the useful part. A bare "400" tells an
        # operator nothing about which field they got wrong.
        raw = exc.read().decode("utf-8", "replace")[:500].strip()
        detail = raw
        try:
            j = json.loads(raw)
            err = j.get("error")
            detail = (err.get("message") if isinstance(err, dict) else err) or raw
        except ValueError:
            pass
        raise RuntimeError("%s %s — %s" % (exc.code, exc.reason, detail))
    except urllib.error.URLError as exc:
        raise RuntimeError("cannot reach %s (%s)" % (url, exc.reason))
    except TimeoutError:
        raise RuntimeError("timed out after %ss — a cold model can take that "
                           "long to load" % timeout)


@functools.lru_cache(maxsize=1)
def _zones():
    try:
        from zoneinfo import available_timezones
        return available_timezones()
    except Exception:                                      # noqa: BLE001
        return set()


def _now_in(tz):
    """Local time in an IANA zone the display asked for, or this box's own.

    The browser is the only party that knows where the person standing in
    front of the screen actually is. This server runs on UTC, so using its
    clock would tell somebody in New York at eight in the evening that it is
    already tomorrow — a different wrong answer, not a fix.

    The zone name is checked against the tz database and then thrown away:
    what reaches the prompt is formatted here, never a string the client
    sent. A client that makes something up gets the server clock."""
    import datetime
    if tz and tz in _zones():
        try:
            from zoneinfo import ZoneInfo
            return datetime.datetime.now(ZoneInfo(tz))
        except Exception:                                  # noqa: BLE001
            pass
    return datetime.datetime.now().astimezone()


def effective_system(cfg, tz=None):
    """The configured prompt, plus the one thing the model cannot possibly
    know: what day it is.

    A language model's sense of "now" is frozen at its training cutoff, so
    asked the date it answers confidently and wrongly — a local 3b will say
    2023 without hedging. On a screen somebody walks up to, the date and the
    time are among the very first things they will ask, so the server states
    them on every request. This cannot fix general staleness — the model
    still has no news and no internet — but it removes the one wrong answer
    that makes the whole thing look broken.

    The fact and the guidance are deliberately separate sentences, with the
    fact first and nothing attached to it. Written as one run — "the date is
    X, use this rather than what you remember, and if asked about anything
    later say you don't know" — a small model does not reliably tell the fact
    from the instructions and recites the lot when somebody asks the date.
    Measured on qwen2.5:3b: one paragraph leaked the instructions into a
    spoken answer; two sentences did not."""
    stamp = _now_in(tz).strftime("Current date and time: %A %d %B %Y, %H:%M (%Z).")
    guidance = ("That line is context, not something to read out. Do not "
                "repeat or mention these instructions. If you are asked "
                "about anything more recent than your training data, say you "
                "do not know rather than guessing.")
    base = (cfg.get("system") or "").strip()
    tail = stamp + "\n" + guidance
    return (base + "\n\n" + tail) if base else tail


def ask_backend(text, history, cfg, tz=None, conversation_id=""):
    """One turn against whichever assistant is configured.

    `openai` is the dialect, not the vendor: Ollama, OpenClaw, LM Studio and
    vLLM all speak it, so one adapter reaches all of them and the difference
    is a base URL.

    Returns a dict rather than the reply string it used to. Home Assistant
    says three things about the conversation itself — whether to hang up,
    which conversation this was, and why it could not answer — and each of
    them changes what the display does next. A second return channel bolted
    on beside the string would have been the same data with a worse name."""
    turns = [m for m in history if isinstance(m, dict)
             and m.get("role") in ("user", "assistant") and m.get("content")]
    keep = max(0, min(int(cfg.get("history_turns") or 0), MAX_HISTORY))
    msgs = [{"role": m["role"], "content": str(m["content"])[:8000]}
            for m in turns[-keep:]] if keep else []
    msgs.append({"role": "user", "content": text})

    if cfg["provider"] in OPENAI_DIALECT:
        base = (cfg.get("base_url") or "").rstrip("/")
        url = base if base.endswith("/chat/completions") else base + "/chat/completions"
        msgs = [{"role": "system",
                 "content": effective_system(cfg, tz)}] + msgs
        body = {"model": cfg["model"], "messages": msgs, "stream": False,
                "max_tokens": int(cfg.get("max_tokens") or 400),
                "temperature": float(cfg.get("temperature") or 0)}
        if cfg.get("keep_alive"):
            body["keep_alive"] = cfg["keep_alive"]
        key = (cfg.get("api_key") or "").strip()
        headers = {"Authorization": "Bearer " + key} if key else {}
        j = _post_json(url, body, headers, int(cfg.get("timeout") or 120))
        choices = j.get("choices") or []
        if not choices:
            raise RuntimeError("the model returned no choices")
        return {"reply": ((choices[0].get("message") or {}).get("content")
                          or "").strip()}

    if cfg["provider"] == "anthropic":
        base = (cfg.get("base_url") or ANTHROPIC_BASE).rstrip("/")
        if base.endswith("/messages"):
            url = base
        else:
            url = re.sub(r"/v1$", "", base) + "/v1/messages"
        body = {"model": cfg["model"], "messages": msgs,
                # required here, unlike the OpenAI shape where it is optional
                "max_tokens": int(cfg.get("max_tokens") or 400)}
        body["system"] = effective_system(cfg, tz)   # top-level, not a message
        # No temperature. The current Claude models reject the sampling
        # parameters outright with a 400, and older ones cap at 1.0 where this
        # panel's slider goes to 1.5 — sending it would be a field that works
        # on some models and breaks the assistant on others. The prompt is the
        # steering wheel here. keep_alive is likewise an Ollama extension and
        # has no meaning to a hosted provider.
        headers = {"x-api-key": (cfg.get("api_key") or "").strip(),
                   "anthropic-version": ANTHROPIC_VERSION}
        j = _post_json(url, body, headers, int(cfg.get("timeout") or 120))
        # A reply is a list of content blocks, and only the text ones are ours
        # to speak. Joining rather than taking the first keeps a reply that
        # arrives in several pieces intact.
        parts = [b.get("text") or "" for b in (j.get("content") or [])
                 if isinstance(b, dict) and b.get("type") == "text"]
        reply = "\n".join(p for p in parts if p).strip()
        if not reply and j.get("stop_reason") == "refusal":
            raise RuntimeError("the model declined to answer that")
        return {"reply": reply}

    if cfg["provider"] == HOMEASSISTANT:
        return ask_homeassistant(text, cfg, conversation_id)

    raise RuntimeError("provider '%s' has no adapter" % cfg["provider"])


def ha_url(base, path):
    """Home Assistant's API under whatever was typed in the address field.

    Somebody setting this up has that URL in another tab, and what they copy
    is as likely to be `…:8123/api` — or the conversation path itself, from
    the documentation — as the bare origin. All three mean the same house."""
    base = (base or "").rstrip("/")
    base = re.sub(r"/api(/conversation/process)?$", "", base)
    return base + path


def ask_homeassistant(text, cfg, conversation_id=""):
    """One turn against Home Assistant's conversation agent.

    No history, no system prompt, no token or temperature limits: HA holds
    the conversation itself against `conversation_id`, and what the agent is
    told is configured in HA. Sending our own would be this server's idea of
    the conversation arriving beside HA's, and the fields are hidden in the
    panel for the same reason."""
    body = {"text": text}
    if conversation_id:
        body["conversation_id"] = conversation_id
    if (cfg.get("agent_id") or "").strip():
        body["agent_id"] = cfg["agent_id"].strip()
    j = _post_json(ha_url(cfg.get("base_url"), "/api/conversation/process"),
                   body, {"Authorization": "Bearer " + (cfg.get("api_key") or "").strip()},
                   int(cfg.get("timeout") or 120))
    resp = j.get("response") or {}
    speech = (((resp.get("speech") or {}).get("plain") or {})
              .get("speech") or "").strip()
    kind = str(resp.get("response_type") or "")
    # The fallthrough signal, and structured so that acting on it is a branch
    # rather than string-matching an apology. Only an error carries a code
    # worth reading; `data` on a successful action is a list of targets.
    code = str((resp.get("data") or {}).get("code") or "") if kind == "error" else ""

    # An action that succeeded and said nothing is not a failure, but silence
    # is indistinguishable from one on a display somebody is standing in
    # front of — and a command that quietly did nothing is the failure this
    # adapter most needs to not have.
    if not speech and kind == "action_done":
        speech = "Done."

    # `continue_conversation` is read and deliberately not acted on. It was,
    # for one day: false closed the conversation immediately, on the reasoning
    # that a completed command has nothing to follow. In a room that is wrong.
    #
    # Measured 2026-08-15, on the first real installation: after each command
    # the display went silently to sleep, five further utterances were
    # transcribed and dropped at the wake gate, and the person concluded it had
    # locked up — they had no way to know the conversation had ended, and the
    # house had become the one endpoint you cannot speak to twice. Saying a
    # wake word again was the fix, which is a thing nobody should have to
    # discover.
    #
    # The awake window already does this job, everywhere, the same way. Closing
    # a few seconds earlier is not worth a house that behaves unlike every
    # other endpoint, and `true` needs nothing done to it — staying awake is
    # the default, so "which room?" is answered without re-addressing.
    return {"reply": speech, "code": code,
            "conversation_id": str(j.get("conversation_id") or "")}


# ------------------------------------------------------------------- routes
# One assistant configuration becomes a set of named ones. A route is a name,
# a wake word and its aliases, an adapter and its configuration, and
# optionally its own voice — so you can HEAR which one answered, which turns
# out to matter the moment two of them can reply to the same room.
#
# A route is published in two halves, and one of them is never published at
# all. Wake-word matching happens in the browser, so some of a route has to
# reach it; the rest has no business there.
#
#   presentation  name, greeting, voice        anyone who can reach the port
#   routing       wake word, aliases, strict   the same today; behind the
#                                              device token from phase 2
#   connection    adapter kind, base URL,      nobody, through any browser
#                 API key
#
# The adapter kind is on the wrong side of that line to publish. Nothing
# needs it — routing is by wake word and replies come back already labelled —
# and it is the one field that tells a reader what this box fronts. That is a
# targeting signal rather than a name.
ROUTES_PATH = os.path.join(ROOT, "routes.json")
_routes_lock = threading.Lock()

ROUTE_PRESENTATION = ("name", "greeting", "voice")
#: …and where those two now come FROM. A route names a speech profile, and the
#: profile carries the voice, the engine, the rate and the greeting phrases —
#: everything a route used to hold a private copy of. Two screens wanting the
#: same voice used to mean typing it twice.
ROUTE_SPEECH_KEYS = ("ttsvoice", "ttsengine", "vrate", "vpitch", "greetings")
ROUTE_ROUTING = ("wakeword", "aliases", "strict")
#: everything else is BACKEND_DEFAULTS, and it is the connection half
ROUTE_PUBLIC = ROUTE_PRESENTATION + ROUTE_ROUTING

ROUTE_DEFAULTS = dict(BACKEND_DEFAULTS)
ROUTE_DEFAULTS.update({
    "name": "assistant",
    # Blank means "use the shared greeting phrases". A route only needs its
    # own where it should sound different from the rest — which is the point
    # of a route having a voice as well.
    "greeting": "",
    "voice": "",                 # blank = whatever the shared settings chose
    # Which speech profile answers for this route. Blank is the deployment's
    # default, the same rule a device follows.
    "speech": "",
    # Which network profile — that is, which port of its own — this endpoint
    # answers on. Blank is the shared display port, which is where they all
    # were before this existed.
    "network": "",
    # …and which model profile it speaks to. Same rule again, and it has to be
    # a default rather than an incidental key: read_routes rebuilds each record
    # from this map, so a field missing here is a field silently dropped on the
    # next read — and an endpoint that forgot which model it uses is an
    # endpoint that answers as DEMO without saying why.
    "model_profile": "",
    "wakeword": "resonance",
    "aliases": [],
    # Exact matching, for routes that DO things rather than answer. The same
    # false-positive rate costs a few tokens on one route and actuates
    # hardware on the other.
    "strict": False,
    "enabled": True,
    # Another route's id, or blank. Nobody remembers which name owns which
    # capability, so asking the house something it cannot answer will be
    # constant: the house reports that it recognised no intent, the named
    # route gets the question instead, and the person is never told they used
    # the wrong word. A relationship between routes rather than part of an
    # adapter's configuration, which is why it lives here and not in
    # BACKEND_DEFAULTS.
    "fallthrough": "",
    # Which displays may use this endpoint. Two fields rather than an empty
    # list meaning one thing and a filled one another: `restricted` off is "any
    # display", which is what every endpoint was before this existed, so an
    # upgrade changes nothing until somebody switches it on. An empty list with
    # the switch ON is an endpoint no display may use — allowed rather than
    # refused, because restricting one before the tablet that will use it has
    # been hung is a legitimate order to do things in, and the panel says so
    # out loud instead.
    "restricted": False,
    # MUST THERE BE A PERSON. Separate from `restricted`, and deliberately:
    # that one asks WHICH callers, this one asks whether a caller has proved
    # who they are at all. An endpoint can be open to everybody and still
    # insist they sign in — a hosted model worth giving to anyone in the
    # building and to nobody walking past it.
    #
    # It refuses a DEVICE outright, approved or not. A wall screen has no
    # person on it and never will; that is what makes this the control that
    # limits what an expensive model costs, where an allow-list of screens
    # only limits which rooms it is answered in.
    "needs_signin": False,
    "displays": [],
    # …and the groups it names. Kept beside the individual list rather than
    # folded into it: a grant made to "the physics department" should still
    # read that way next year, and flattening it at the point of saving would
    # turn it into twelve ids nobody can maintain.
    "groups": [],
    # The people it names. A THIRD list rather than more ids in the first,
    # because a display and a person are different populations reached by
    # different sessions — the same reason groups refuse to mix the two kinds
    # — and one list holding either would be a list nobody could audit. Empty
    # on every existing route, so an upgrade grants nobody anything.
    "identities": [],
})
MAX_ROUTES = 24                  # a household, not a directory service


def _keep_word(s):
    """A wake word as it was typed, minus what the matcher cannot carry.

    Case is KEPT. It is a name, and it is printed on a wall — "say Resonance"
    rather than "say resonance" — so forcing it down was the server deciding
    how somebody's assistant is spelt. Nothing is lost by keeping it: the
    browser lowercases both the word and what it heard before comparing them,
    so what this answers to is unchanged.

    The same characters are still dropped as before, and deliberately: the
    matcher discards anything that is not a letter, a digit or a space, so
    keeping a hyphen here would print a word that is not the word being
    matched."""
    s = re.sub(r"[^A-Za-z0-9\s]", " ", str(s or ""))
    return re.sub(r"\s+", " ", s).strip()



def _blank_routes():
    return {"default": "", "routes": {}}


def _migrate_routes():
    """The single assistant this server had until now becomes route one.

    Its connection is backend.json verbatim, and its wake word is the one out
    of the shared settings — which is where the display read it from, so the
    box answers to exactly the same word after the upgrade as before it. The
    two source documents are left on disk untouched: an upgrade that deletes
    the thing it read from has no way back if the migration was wrong."""
    cfg = read_backend()
    stored = read_settings()
    rec = dict(ROUTE_DEFAULTS)
    rec.update({k: cfg[k] for k in BACKEND_DEFAULTS})
    rec["wakeword"] = _keep_word(stored.get("wakeword")) or ROUTE_DEFAULTS["wakeword"]
    rec["aliases"] = [w for w in (_keep_word(a) for a in
                                  re.split(r"[\n,]", str(stored.get("wakealiases") or "")))
                      if w]
    # A name, not a second wake word: this is what the panel and the
    # transcript call it, and the word it answers to is its own field.
    rec["name"] = rec["wakeword"] or "assistant"
    rec.update(created=int(time.time()), created_by="migration")
    rid = "r" + secrets.token_hex(4)
    return {"default": rid, "routes": {rid: rec}}


def read_routes():
    """The whole document, migrating the older single-assistant one in on
    first read. Never returns something with no routes in it: a server with
    nowhere to send a question is not a state the rest of this file should
    have to reason about."""
    doc = None
    try:
        with open(ROUTES_PATH) as fh:
            stored = json.load(fh)
        if isinstance(stored, dict) and isinstance(stored.get("routes"), dict):
            doc = {"default": str(stored.get("default") or ""), "routes": {}}
            for rid, rec in stored["routes"].items():
                out = dict(ROUTE_DEFAULTS)
                out.update({k: v for k, v in rec.items() if k in ROUTE_DEFAULTS})
                out["aliases"] = [w for w in (_keep_word(a) for a in
                                              (rec.get("aliases") or [])) if w]
                out["displays"] = [str(d)[:32] for d in
                                   (rec.get("displays") or [])][:MAX_ALLOW]
                out["groups"] = [str(g)[:32] for g in
                                 (rec.get("groups") or [])][:MAX_GROUPS]
                out["identities"] = [str(p)[:32] for p in
                                     (rec.get("identities") or [])][:MAX_ALLOW]
                out["created"] = rec.get("created")
                out["created_by"] = rec.get("created_by")
                doc["routes"][str(rid)] = out
    except (OSError, ValueError):
        pass
    if not doc or not doc["routes"]:
        doc = _migrate_routes()
        write_routes(doc)
    _settle_default(doc)
    return doc


def _settle_default(doc):
    """The default must be a route that can actually answer.

    It is where a question with no wake word behind it goes, so a default
    pointing at a deleted or switched-off route is a composer that silently
    does nothing. Applied on both read and write: a hand-edited file gets the
    same treatment as one this server wrote."""
    rs = doc["routes"]
    if doc["default"] in rs and rs[doc["default"]].get("enabled", True):
        return
    live = [r for r in rs if rs[r].get("enabled", True)] or list(rs)
    doc["default"] = sorted(live, key=lambda r: (rs[r].get("created") or 0,
                                                 rs[r]["name"]))[0] if live else ""


def write_routes(doc):
    _settle_default(doc)
    with _routes_lock:
        tmp = ROUTES_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(doc, fh, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)                     # it holds credentials
        os.replace(tmp, ROUTES_PATH)


def route_order(doc):
    """Oldest first, and the default first of all. The order decides which
    route a question with no wake word behind it reaches — typed into the
    composer, pushed through an embed, or sent by the self-test."""
    # Name breaks the tie, because several routes added in one sitting share
    # a timestamp to the second and a list that reshuffles itself between
    # visits is a list nobody can find anything in.
    rest = sorted((r for r in doc["routes"] if r != doc["default"]),
                  key=lambda r: (doc["routes"][r].get("created") or 0,
                                 doc["routes"][r]["name"]))
    return ([doc["default"]] if doc["default"] in doc["routes"] else []) + rest


#: What a model profile carries. `fallthrough` is deliberately NOT here: it
#: names another endpoint, so it belongs to the endpoint rather than to a
#: connection several of them might share.
MODEL_KEYS = ("provider", "base_url", "model", "api_key", "agent_id")


def _model_pool():
    try:
        return display_settings()["models"]
    except Exception:
        return []


def with_model(rec):
    """A route's connection, resolved from the model profile it names.

    Overlaid rather than replacing the record, so everything that is still the
    ROUTE's — its system prompt, its limits, where it falls through to — is
    untouched. A route naming no profile gets the deployment's default; one
    whose profile has been deleted falls back to it too, rather than quietly
    talking to whatever base URL was last typed."""
    pool = _model_pool()
    if not pool:
        return rec
    prof = find_look(str(rec.get("model_profile") or ""), pool)
    if prof is None:
        try:
            prof = find_look(display_settings()["model_default"], pool)
        except Exception:
            prof = None
    if not prof:
        return rec
    out = dict(rec)
    for k in MODEL_KEYS:
        if k in prof:
            out[k] = prof[k]
    return out


def _speech_pool():
    try:
        return display_settings()["speeches"]
    except Exception:
        return []


def _speech_default():
    try:
        return display_settings()["speech_default"]
    except Exception:
        return ""


def public_routes(doc, disp=None, ident=None):
    """The two halves a browser may see. The connection half is not omitted
    from the serialisation by accident — it is enumerated the other way
    round, so a field added to a route later is private until somebody
    decides otherwise.

    Presentation goes to anything that can reach the port, which is what keeps
    a newly hung display looking right before anybody has approved it. Routing
    — the words that actually reach an endpoint — goes only to a caller
    holding a display token, which is every browser that has loaded the page
    and nothing that has not.

    `allowed` is not a field of the route: it is this caller's answer about
    it, and the routing half arrives whether it is true or false. That is
    deliberate. A display has to RECOGNISE the wake word of an endpoint it may
    not use in order to drop the utterance — the alternative is a house
    command it cannot identify landing in whatever conversation it is already
    having, which is the exact fault this phase exists to remove."""
    out = []
    for rid in route_order(doc):
        rec = doc["routes"][rid]
        if not rec.get("enabled", True):
            continue
        row = {k: rec[k] for k in ROUTE_PRESENTATION}
        # Resolved here, so a browser is handed a voice rather than the name of a
        # profile it has no business knowing the rest of. A route naming none
        # falls back to the deployment's default speech profile, and one whose
        # profile has been deleted falls back with it rather than going silent.
        prof = find_look(str(rec.get("speech") or ""), _speech_pool()) \
               or find_look(_speech_default(), _speech_pool()) or {}
        for k in ROUTE_SPEECH_KEYS:
            if k in prof:
                row[k] = prof[k]
        # A route's own greeting still wins where somebody typed one: the
        # profile is the deployment's voice, the route's line is this one's.
        if not row.get("greeting") and prof.get("greetings"):
            row["greeting"] = prof["greetings"]
        if not row.get("voice") and prof.get("ttsvoice"):
            row["voice"] = prof["ttsvoice"]
        row.update(id=rid, allowed=subject_may(rec, disp, ident))
        # A PERSON gets the routing half on the same terms a display does. The
        # wake gate runs in the browser, so a session that is handed no wake
        # words cannot drop an utterance it should drop — it simply never
        # recognises one, which is the fault this half exists to prevent,
        # arriving through the door marked "we only thought about devices".
        if disp or ident:
            row.update({k: rec[k] for k in ROUTE_ROUTING})
            # …and the words come from the speech profile now, not from the
            # route's own record. An endpoint names a profile; the profile says
            # what wakes it, what else to accept for it, and how close a match
            # has to be. A route keeps its stored copy only so that unpicking
            # this later does not lose what somebody typed.
            if "wakeword" in prof:
                row["wakeword"] = str(prof.get("wakeword") or "")
            if "wakealiases" in prof:
                row["aliases"] = [a.strip() for a
                                  in str(prof.get("wakealiases") or "").splitlines()
                                  if a.strip()]
            if "wakestrict" in prof:
                row["strict"] = bool(prof.get("wakestrict"))
            # A PERSON'S OWN WORD, on the endpoint a question goes to when
            # nothing named one. It is added rather than substituted: the
            # shared word still works on their device, because taking it away
            # would mean somebody who set a personal word could no longer join
            # in when a room says the house's name.
            #
            # Only theirs. Every other browser is handed the shared words
            # alone, which is the whole mechanism — the collision stops because
            # nobody else's device has ever heard of it.
            if ident and ident.get("wakeword") and rid == doc.get("default"):
                row["aliases"] = list(row.get("aliases") or []) + [ident["wakeword"]]
        out.append(row)
    return out


def admin_routes(doc):
    """Everything, less the credential itself. Whether a key is STORED is not
    the key, and an admin needs to see the difference between a route with
    one and a route without."""
    out = []
    for rid in route_order(doc):
        rec = dict(doc["routes"][rid])
        row = {k: rec.get(k) for k in ROUTE_DEFAULTS if k != "api_key"}
        row.update(id=rid, has_key=bool(rec.get("api_key")),
                   created=rec.get("created"), created_by=rec.get("created_by"),
                   is_default=(rid == doc["default"]))
        out.append(row)
    return out


def net_profile(nid):
    """A network profile by id, or None."""
    if not nid:
        return None
    for n in display_settings()["networks"]:
        if n["id"] == nid:
            return n
    return None


def net_members(doc, nid):
    """Which endpoints a port carries, in order.

    Read at request time rather than frozen when the listener was bound, so
    moving an endpoint between ports takes effect on the next question — the
    SOCKET needs a restart, the membership does not.

    NAMING NO PROFILE MEANS NO PORT. It used to mean "the default one", and
    that fallback was the thing quietly putting two assistants on one port:
    two endpoints that had simply never been given a port both landed on it,
    without anybody choosing that. An endpoint with no profile is now attached
    to nothing and answers nowhere — visibly, and said at startup — which is a
    state somebody fixes rather than one that hides.

    The profile that owns the built-in display port is still nominated, but
    that is about which LISTENER is the display's; it no longer collects
    endpoints that named nothing."""
    if not nid:
        return list(route_order(doc))
    return [r for r in route_order(doc)
            if doc["routes"][r].get("network") == nid]


def route_dest(cfg):
    """What a route reaches, for the console and the log. A model name where
    there is one; a house has none, and printing an empty field there reads
    as a configuration somebody forgot to finish."""
    if cfg["provider"] == HOMEASSISTANT:
        return "home assistant" + (" · " + cfg["agent_id"] if cfg.get("agent_id") else "")
    if cfg["provider"] == "demo":
        return "demo"
    return "%s/%s" % (cfg["provider"], cfg["model"] or "(no model)")


def resolve_route(doc, rid):
    """Which route answers. An id nobody recognises falls back to the default
    rather than failing: a display holding a route that was deleted while it
    was awake should keep working, and the alternative is a screen that has
    gone quiet for a reason nobody standing in front of it can see.

    The record comes back with its connection already resolved from the model
    profile it names — a copy, never the stored record, so nothing downstream
    can write a profile's credential back into a route."""
    if rid and rid in doc["routes"] and doc["routes"][rid].get("enabled", True):
        return rid, with_model(doc["routes"][rid])
    d = doc["default"]
    if d in doc["routes"] and doc["routes"][d].get("enabled", True):
        return d, with_model(doc["routes"][d])
    for r in route_order(doc):
        if doc["routes"][r].get("enabled", True):
            return r, with_model(doc["routes"][r])
    return "", None


def validate_route(obj, current, doc, rid=None):
    """Returns (record, error). The connection half is the backend validator
    unchanged — one adapter configuration is one adapter configuration,
    whether there is one of them or six."""
    rec, err = validate_backend(obj, current)
    if err:
        return None, err
    for k in ("name", "greeting", "voice"):
        if k in obj:
            rec[k] = str(obj[k] or "").strip()[:200]
    if "speech" in obj:
        pid = str(obj["speech"] or "")[:16]
        if pid and not any(p["id"] == pid
                           for p in display_settings()["speeches"]):
            return None, ("that speech profile no longer exists — reload the "
                          "panel to see the current list")
        # One endpoint per profile. A speech profile carries the WAKE WORD, so
        # two endpoints naming the same one answer to the same name and cannot
        # be told apart — the utterance would reach whichever matched first.
        # Refused here rather than left to be discovered by talking to it.
        if pid:
            taken = [k for k, r in doc["routes"].items()
                     if k != rid and r.get("speech") == pid]
            if taken:
                other = doc["routes"][taken[0]].get("name") or "another endpoint"
                return None, ("%s already uses that speech profile — a profile "
                              "carries the wake word, so two endpoints sharing "
                              "one would answer to the same name" % other)
        rec["speech"] = pid
    if "network" in obj:
        nid = str(obj["network"] or "")[:16]
        pool = display_settings()["networks"]
        if nid and not any(p["id"] == nid for p in pool):
            return None, ("that network profile no longer exists — reload the "
                          "panel to see the current list")
        rec["network"] = nid

    # ONE PORT, ONE ENDPOINT. No exceptions, including the built-in display
    # ports.
    #
    # Ports used to be shareable: several endpoints on one, told apart by wake
    # word. It is gone because a port is the level authentication is decided
    # at, and a door with two assistants behind it can only have one lock —
    # the moment they disagreed about needing a sign-in, the port had to
    # answer for both and answered for the looser of them. One assistant per
    # door is what makes the answer unambiguous.
    #
    # OUTSIDE the `if "network" in obj` above, and that is the whole point.
    # Inside it, the rule only ran when a save happened to carry the network
    # field — so an install whose endpoints all sat on the display port sailed
    # through every save, because none of them was CHANGING port. The rule is
    # about the state being saved, not about which fields the panel sent.
    #
    # BLANK IS NOT A PORT. It used to resolve to the default profile, and two
    # endpoints that had simply never been given one both landed there — the
    # collision this rule exists to prevent, arriving through the one door the
    # rule could not see. Naming no profile now attaches an endpoint to
    # nothing, so blanks cannot collide with each other and there is nothing
    # here to compare them against.
    target = str(rec.get("network") or "")
    if target:
        other = [k for k, r in doc["routes"].items()
                 if k != rid and str(r.get("network") or "") == target]
        if other:
            who = doc["routes"][other[0]].get("name") or "another endpoint"
            return None, ("%s already answers on that port, and a port carries "
                          "one endpoint — give this one a port of its own "
                          "under PROFILES \u25b8 NETWORK" % who)
    if "model_profile" in obj:
        mid = str(obj["model_profile"] or "")[:16]
        if mid and not any(p["id"] == mid
                           for p in display_settings()["models"]):
            return None, ("that model profile no longer exists — reload the "
                          "panel to see the current list")
        rec["model_profile"] = mid
        # Sharing one is fine and expected — several endpoints can speak to the
        # same model. What is NOT kept is the route's own copy of the
        # connection: a stale key sitting in routes.json reads as live, and
        # leaves with_model two answers to choose between.
        for k in MODEL_KEYS:
            rec[k] = "demo" if k == "provider" else ""
    if not rec["name"]:
        return None, "a route needs a name"
    if "strict" in obj:
        rec["strict"] = bool(obj["strict"])
    if "enabled" in obj:
        rec["enabled"] = bool(obj["enabled"])
    if "fallthrough" in obj:
        rec["fallthrough"] = str(obj["fallthrough"] or "").strip()[:32]
    if rec.get("fallthrough"):
        # Both of these are a route that silently answers nothing: one is a
        # loop, the other is a name that no longer exists. A deleted target
        # is left to the route that pointed at it rather than rewritten
        # here — see /routes/delete.
        if rec["fallthrough"] == rid:
            return None, "a route cannot fall through to itself"
        if rec["fallthrough"] not in doc["routes"]:
            return None, "the route to fall through to no longer exists"
    if "restricted" in obj:
        rec["restricted"] = bool(obj["restricted"])
    if "needs_signin" in obj:
        rec["needs_signin"] = bool(obj["needs_signin"])
    if "displays" in obj:
        # Checked against the displays that exist, so a stale id cannot sit in
        # an allow-list looking like a device somebody approved. Unknown ones
        # are dropped rather than refused: the panel sends the list it was
        # shown, and a display deleted in another tab between the two is not a
        # mistake worth making the admin retype a form over.
        known = read_displays()
        seen, out = set(), []
        for d in (obj["displays"] or []):
            d = str(d)[:32]
            if d in known and d not in seen:
                seen.add(d)
                out.append(d)
        rec["displays"] = out[:MAX_ALLOW]
    if "groups" in obj:
        known = read_groups()
        seen, out = set(), []
        for g in (obj["groups"] or []):
            g = str(g)[:32]
            if g in known and g not in seen:
                seen.add(g)
                out.append(g)
        rec["groups"] = out[:MAX_GROUPS]
    if "identities" in obj:
        # Same treatment as the displays above, and for the same reason: an id
        # for somebody who has been deleted must not sit in an allow-list
        # looking like a grant to a person.
        known = read_identities()
        seen, out = set(), []
        for p in (obj["identities"] or []):
            p = str(p)[:32]
            if p in known and p not in seen:
                seen.add(p)
                out.append(p)
        rec["identities"] = out[:MAX_ALLOW]
    if "wakeword" in obj:
        rec["wakeword"] = _keep_word(obj["wakeword"])[:40]
    # No longer required on the route. The word lives in the speech profile the
    # route names, and demanding one here would refuse every endpoint saved
    # from a panel that no longer has the field. What a route DOES still need
    # is a way to be reached, and that is now the profile — checked above.
    rec.setdefault("wakeword", "")
    if "aliases" in obj:
        raw = obj["aliases"]
        if not isinstance(raw, (list, tuple)):
            raw = re.split(r"[\n,]", str(raw or ""))
        seen, out = set(), []
        for a in raw:
            w = _keep_word(a)[:40]
            if w and w not in seen:
                seen.add(w)
                out.append(w)
        rec["aliases"] = out[:20]

    # Two routes answering to the same word is still a route nobody can reach,
    # but it is no longer checked HERE: the words live in speech profiles now,
    # every route carries the same vestigial default, and comparing those
    # refused every save. What prevents the clash instead is one endpoint per
    # profile, refused above — two endpoints cannot share a word because they
    # cannot share the profile the word is in.
    return rec, None


def validate_app(obj, current):
    """Returns (config, error). Refuses anything that would leave the server
    unable to start, because the only way back would be editing JSON on the
    box by hand."""
    cfg = dict(current)
    # Clamped rather than refused: these are a screen's own housekeeping, and a
    # number outside the range is somebody nudging a field rather than a
    # configuration that would stop the server coming up. The ports below are
    # the opposite, which is why they refuse.
    for k, (lo, hi) in UNATTENDED_LIMITS.items():
        if k not in obj:
            continue
        try:
            v = int(obj[k])
        except (TypeError, ValueError):
            return None, "%s must be a whole number" % k.replace("_", " ")
        cfg[k] = min(hi, max(lo, v))
    # Refused rather than clamped, unlike the numbers above: there is no
    # nearest sensible time to a typo, and a field silently corrected to 00:00
    # is a building reloading at midnight because somebody mistyped.
    for k, what in (("refresh_at", "refresh"), ("restart_at", "restart")):
        if k not in obj:
            continue
        v = str(obj[k] or "").strip()
        if v:
            m = re.match(r"^([0-9]{1,2}):([0-9]{2})$", v)
            if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
                return None, ("the %s time reads as HH:MM, or empty for none"
                              % what)
            v = "%02d:%s" % (int(m.group(1)), m.group(2))
        cfg[k] = v
    for k in ("http_port", "https_port", "admin_port"):
        if k not in obj:
            continue
        try:
            v = int(obj[k])
        except (TypeError, ValueError):
            return None, "%s must be a whole number" % k.replace("_", " ")
        if not (PORT_MIN <= v <= PORT_MAX):
            return None, ("%s must be between %d and %d — below %d needs root, "
                          "and this server runs as an ordinary user"
                          % (k.replace("_", " "), PORT_MIN, PORT_MAX, PORT_MIN))
        cfg[k] = v
    ports = [cfg["http_port"], cfg["https_port"], cfg["admin_port"]]
    if len(set(ports)) != 3:
        return None, "the three ports must all differ"

    # Binding, before the port check, because which addresses count as taken
    # depends on what is being bound.
    if "bind" in obj:
        v = str(obj["bind"] or "").strip()
        if v not in BIND_MODES:
            return None, "binding must be one of: " + ", ".join(BIND_MODES)
        cfg["bind"] = v
    if "bind_address" in obj:
        cfg["bind_address"] = str(obj["bind_address"] or "").strip()
    if cfg["bind"] == "address":
        if not cfg["bind_address"]:
            return None, "choose which address to bind, or bind everything"
        if not address_bindable(cfg["bind_address"]):
            return None, ("this machine has no address %s — the server would "
                          "fail to start on it" % cfg["bind_address"])

    # …and not on top of a network profile. Those are the app's ports now, and
    # the portal landing on one of them would take the display down and the
    # way of fixing it with the same restart.
    for n in display_settings()["networks"]:
        v = n.get("values") or {}
        for key in ("port", "redirect"):
            try:
                got = int(v.get(key) or 0)
            except (TypeError, ValueError):
                continue
            if got and got == cfg["admin_port"]:
                return None, ("port %d is the network profile %s — the admin "
                              "portal cannot sit on a port the app answers on"
                              % (got, n["name"]))

    host = bind_host(cfg)
    for k in ("http_port", "https_port", "admin_port"):
        if cfg[k] != current[k] and not port_free(cfg[k], host):
            return None, ("port %d is already in use by something else on this "
                          "machine — the server would fail to start on it"
                          % cfg[k])

    if "session_idle_minutes" in obj:
        try:
            m = int(obj["session_idle_minutes"])
        except (TypeError, ValueError):
            return None, "session length must be a whole number of minutes"
        if not (SESSION_MIN <= m <= SESSION_MAX):
            return None, ("session length must be between %d and %d minutes"
                          % (SESSION_MIN, SESSION_MAX))
        cfg["session_idle_minutes"] = m
    return cfg, None

# ------------------------------------------------------------------ displays
# The problem this exists for: two people in a room, one of them addressing the
# wall tablet, and everybody else's microphone hearing it too.
#
# Push-to-talk on a personal device is the correct configuration and is already
# a per-browser setting — and it is not a control, because nothing makes
# anybody set it. So the enforcement is here, at /ask: an endpoint can carry
# the displays allowed to use it, and a phone that wakes on the house name is
# refused regardless of how its browser is configured. The browser's settings
# stop being load-bearing.
#
# A NAME CANNOT BE THE CREDENTIAL. `?display=kitchen` is guessable, so binding
# on the declared name alone would let anything that types it reach the
# endpoint. The server issues an unguessable token on first visit and an admin
# approves the device: the name says which place it is, the token says it IS
# that place. Somebody who types a wall display's URL into their own phone is
# issued a NEW token, which nobody approved — the kitchen tablet's token is in
# the kitchen tablet's cookie jar and was never in the URL. The URL is a name,
# not a key.
#
# Places and people bind differently, and the difference is cardinality: a wall
# display is one physical object, so it is pinned to a single token an admin
# blesses. A person is not — phone, tablet and laptop are all legitimately them
# — so their credential is something they KNOW, which is an email address and
# a password. One mechanism, two ways of granting it.
DISPLAYS_PATH = os.path.join(ROOT, "displays.json")
_displays_lock = threading.Lock()
DISPLAY_COOKIE = "rsn_did"
#: Ten years. A wall display is commissioned once and then nobody touches it;
#: an expiring token would take a screen off the wall for a reason nobody
#: standing in front of it could see. Revocation is deleting the record, and
#: that is immediate.
DISPLAY_MAX_AGE = 10 * 365 * 24 * 3600
#: The hard ceiling on an allow-list, and the only one of these that is not a
#: setting: it bounds a field inside a route record rather than the size of the
#: deployment, and no endpoint names five thousand devices one at a time. The
#: numbers that DO scale with the deployment are in DISPLAY_SETTINGS.
MAX_ALLOW = 500
SEEN_INTERVAL = 300              # seconds between writes of "last seen"

#: An enrolment code is TYPED, on the device being enrolled, and that device is
#: a television with a remote or a screen with an on-screen keyboard. Every
#: character is a chore, so there are six of them — and six characters are only
#: safe because of the four rules around them: one use, ten minutes, a back-off
#: on wrong guesses, and an alphabet with no character anybody can misread into
#: another. O/0, I/1 and L are simply not in it, so a misread character is not
#: a different valid code, it is not a code at all.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LEN = 6
_code_fails = {}                 # client ip -> [count, blocked_until]


def norm_code(raw):
    """What somebody typed, as the code it meant. Case folded and everything
    that is not a letter or a digit dropped, so the panel can print K7QP-4M
    and `k7qp 4m` still works."""
    return re.sub(r"[^A-Z0-9]", "", str(raw or "").upper())[:16]


def new_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LEN))


def code_blocked(ip):
    rec = _code_fails.get(ip)
    return bool(rec and rec[1] > time.time())


def note_code_failure(ip):
    """The same geometric back-off as the sign-in, in its own ledger. It is
    what makes six characters enough: a billion possibilities matters only if
    guessing is cheap, and after five wrong ones this address waits."""
    rec = _code_fails.setdefault(ip, [0, 0])
    rec[0] += 1
    if rec[0] >= 5:
        rec[1] = time.time() + min(300, 15 * (2 ** (rec[0] - 5)))


DISPLAY_DEFAULTS = {
    "name": "",                  # what an admin called it
    # An admin's override of which display population this row was in, back
    # when there were two of them. There is one now — a display is a display,
    # and how it enrolled is `origin` below, which describes the row instead of
    # sorting it. Kept so an existing document round-trips rather than losing a
    # key on its first save; nothing reads it and nothing writes it.
    "kind": "",
    "asked": "",                 # the ?display= name it announced itself with
    "approved": False,
    # An unspent enrolment code, and when it dies. Stored in the clear rather
    # than hashed, because the panel has to be able to show it to whoever is
    # about to type it — and this file is admin-only, mode 600, and the code is
    # worthless ten minutes after it was made.
    "code": "", "code_expires": 0,
    # A stored fingerprint, and it is a HINT FOR THE PERSON APPROVING — "this
    # matches your approved kitchen display" — for the one case a token cannot
    # survive, which is a browser wiping its data. It must never become the
    # credential: fingerprints are forgeable by the client, unstable across
    # updates, and identical across two tablets bought together, which is every
    # property you do not want in one. Nothing on this server reads it.
    "hint": "",
    "salt": "", "hash": "",
    "created": 0, "last_seen": 0,
    "approved_by": "", "approved_at": 0,
    # What the person at the device said when they asked for access, in the
    # admin's own words: [{"label": …, "value": …}] in the order the form put
    # them. Self-asserted and worth nothing on its own — but a request that
    # arrives saying "Sarah, building 4 laptop" is one an admin who cannot see
    # the device can act on, where an anonymous row is one they can only guess
    # at. That guessing is the whole point: approving what you cannot identify
    # is not a decision, it is a coin toss.
    "answers": [], "requested_at": 0,
    # Guest access is a LIFECYCLE, not a session. It runs out, and the person
    # asks again — against this same row, so what they told you the first time
    # is still here and they do not fill the form in twice. Zero means never,
    # which is every display an admin issued a code for: a wall screen going
    # dark on a timer is not a security property, it is an outage.
    "expires": 0, "renewals": 0,
    # A refusal, and it is two messages. One the person reads, one for whoever
    # comes to this row in six months wondering why it says no.
    "denied": False, "deny_reason": "", "deny_note": "",
    # …and whether they may ask again. Per device rather than per person: a
    # laptop turned away is a laptop turned away, and the same human on their
    # phone is a new row with a fresh ask. Anything stronger needs an identity,
    # which is what a dedicated URL is for.
    "deny_repeat": True,
    # ---- what makes this one a kiosk rather than a browser tab ----
    #
    # Is this device a KIOSK — a screen people walk up to, that nobody has open
    # and nobody is sitting at? A wall, a stand, a reception counter, a
    # tabletop: the mounting was never what any of this followed from, and
    # calling it "on a wall" told anybody deploying it on a stand that the
    # feature was not for them.
    #
    # Most rows in a real deployment are not kiosks: a guest's laptop and a
    # phone are displays too and want none of it. So it is one tick, and while
    # it is off the profile below is stored and not applied — untick it, the
    # screen goes back to being an ordinary page; tick it again and what you
    # chose is still there.
    "kiosk": False,
    # …and WHICH KIOSK it is, by the id of a profile in the settings below.
    # Empty means the deployment's default, which an admin picks — so a screen
    # hung on a wall and never configured still behaves like the other screens
    # in the building rather than like nothing.
    #
    # An ID rather than the settings themselves. That is the whole point of a
    # profile: change what a hallway screen does once, and every hallway screen
    # changes with it, instead of twelve rows drifting out of step with no way
    # to see which had.
    "kiosk_profile": "",
    # HOW THIS ROW GOT HERE: "code" for one an admin named and minted a code
    # for, "page" for one that arrived because somebody opened the display
    # page. Empty on rows that predate the field, which fall back to a guess —
    # see enrolled_as.
    #
    # Recorded at creation because it is the one thing about a row that is
    # true from the start and never changes. It used to be inferred from
    # whether the row had ever pressed REQUEST ACCESS, which is a different
    # question with a different answer: a browser sitting on the request form
    # has not pressed it yet and is not, for that reason, a screen somebody
    # bolted to a wall.
    "origin": "",
    # Which network profile this device was set up on, by id. Empty is the
    # deployment's default. It decides the address and port its enrolment URL
    # names: a building with several ports has several right answers to "what
    # do I type into this screen", and the one that is right is the one for the
    # network the screen is on.
    "network": "",
    # When an admin last asked this screen to reload itself. The display sends
    # the moment it booted with every poll and reloads when this is newer, so
    # the request clears itself by being satisfied — no acknowledgement to
    # store, and nothing left set to fire a second time on the next boot.
    "reload_req": 0,
}

#: How many screensaver profiles may exist. A deployment has a handful of
#: KINDS of place — a hallway, a bedroom, a shop floor — not one per screen. A
#: list long enough to need scrolling is a list somebody has stopped curating.
MAX_SAVERS = 8
#: (low, high) for the three numbers in a profile. `delay` takes 0 as well and
#: means the profile never starts, which is how you park one without deleting
#: it and unpicking every device that names it.
SAVER_LIMITS = {"delay": (15, 24 * 3600),
                # Under a third of the frame is a postage stamp somebody has to
                # walk up to; over nine tenths there is no margin left to drift
                # within and the shrink has bought nothing.
                "scale": (30, 90),
                # Not 100: a screen dimmed the whole way is switched off, and
                # switching a screen off is a different feature with different
                # consequences — you cannot see that it is still working.
                "dim": (0, 85),
                # ---- and the same again, on a clock ----
                # A hallway at two in the morning should be dark whether or not
                # anybody has just walked past it, which the idle dim above
                # cannot express: somebody walking by at 3am wakes the screen to
                # full brightness for the rest of the night.
                #
                # The hours the dark runs between. EQUAL MEANS OFF — one field
                # cannot say "no window" on its own, and a separate switch to
                # say it would be a third control for a thing two already
                # imply. A `from` later than `to` wraps midnight, which is the
                # ordinary case rather than the exception.
                "night_from": (0, 23), "night_to": (0, 23),
                "night_dim": (0, 85)}
#: What a device gets when it names no profile, or names one that has since
#: been deleted. Off, in both cases, and deliberately the same answer: a screen
#: pointing at a profile nobody can see any more must not keep drifting to
#: numbers that exist nowhere in the panel.
SAVER_OFF = {"delay": 0, "scale": 70, "dim": 45,
             "night_from": 0, "night_to": 0, "night_dim": 0}

#: The appearance a PLACE overrides, and the whole of it. Everything else on
#: LOOK, MOTION and SPEECH stays in the one shared document, so tuning the
#: bloom once still reaches every screen in the building — which is the point
#: of a shared document and the thing a per-place override quietly destroys if
#: it is allowed to cover everything.
#:
#: These four are the ones that actually differ between a hallway read at three
#: metres and a laptop at fifty centimetres: how big the type is, how bright it
#: is, whether the figure fills the frame, and which figure it is.
#:
#: Validated against the values the panel offers rather than stored as typed. A
#: palette name that is not a palette is not a screen that looks wrong, it is
#: `PALETTES[S.palette].ink` throwing once per frame forever.
LOOK_VALUES = {
    "fs":      ("1", "1.12", "1.25"),
    "palette": ("blue", "milk", "ice", "amber", "rust"),
    "layout":  ("hero", "bleed"),
    "mode":    ("stack", "ridge", "disc", "orb", "knot"),
}
#: How many appearance profiles may exist — the same reasoning and the same
#: number as the screensavers. A place, not a screen.
MAX_LOOKS = 8

#: The displays document's own settings, as opposed to the rows in it. Set in
#: the panel, and none of them needs a restart.
#: Days. Long enough to still be there on Monday for a fault somebody noticed
#: on Saturday, short enough that it is not a record of a household.
EVENT_DAYS_DEFAULT = 7
EVENT_DAYS_LIMITS = (1, 90)

DISPLAY_SETTINGS = {
    # May a device nobody invited ask for access at all?
    #
    # Off, the only way in is a code an admin issued deliberately, and an
    # uninvited device simply uses the endpoints open to everything — no queue,
    # nothing to police, and no row anybody has to make a decision about. Which
    # is why it cannot be turned off unless such an endpoint exists: off with
    # nothing open is a server that answers nobody, silently.
    #
    # On, a device can put its hand up. Either way it is RECORDED: the list is
    # what has connected, and a request is one of those rows asking for
    # something.
    "guest_requests": True,
    # How many rows may exist at once. "A household, not a directory service"
    # was the wrong ceiling the moment a guest's laptop became a row too — on a
    # campus, sixty-four is a fortnight, and a full list means nothing new can
    # arrive at all.
    "max_displays": 500,
    # …and how many may be waiting on a decision. The oldest waiting row is
    # dropped when this fills, so this is the number that decides whether a
    # genuine request can be pushed out of the queue by noise.
    "max_pending": 100,
    # Days a guest's access lasts before they have to ask again.
    "guest_days": 30,
    # The request form, as the admin built it. Up to five fields, each with a
    # label and whether it must be answered, and at most one of them a message
    # box for a reason somebody needs a paragraph to give. Empty means nobody
    # has built one yet.
    "form": [],
    # The appearance profiles, each {id, name, fs, palette, layout, mode}.
    # A place — a hallway, a shop floor — not a screen, and named from a device
    # exactly as a screensaver is. Its own list rather than a field on the
    # screensaver profile, because the two are different axes: day and night in
    # one hallway share an appearance and differ only in the dim, and a laptop
    # can want larger type without being told to drift.
    "looks": [],
    # The screensaver profiles, each {id, name, delay, scale, dim}. CENTRAL,
    # and named from a device rather than copied into it — see the `saver`
    # field on a row. A deployment has a handful of kinds of place, and the
    # numbers that suit a hallway suit every hallway in the building.
    "savers": [],
    # The kiosk profiles, each {id, name, voice_only, look, saver}. A public
    # screen people walk up to — a wall, a stand, a reception counter, a
    # tabletop — as against a page somebody opened and is sitting at. The
    # mounting was never the point: what these settings follow from is that
    # nobody owns the session and nobody has a keyboard.
    # Snapshots of the GEOMETRY and SPEECH tabs, the way `looks` is a snapshot
    # of APPEARANCE. Three lists rather than one because a place can want a
    # hallway's appearance with a quieter microphone, and folding them together
    # would mean a profile per combination.
    "motions": [],
    "speeches": [],
    # Which profile in each list an ordinary display gets. One per list, always
    # set, and the profile it names cannot be removed — a list whose default
    # points at nothing would leave every screen with no appearance at all.
    # The connection half of an endpoint, under a name: which provider, which
    # base URL, which model, and the key for it. An endpoint names one instead
    # of carrying its own copy — two endpoints on the same model used to be the
    # same credential typed twice.
    "models": [],
    # A port, under a name, that one endpoint answers on. No nominated default
    # here and deliberately so: every other list has one because a row naming
    # nothing still has to look like something, and an endpoint naming no
    # network profile is not missing a setting — it is on the shared display
    # port, which is where every endpoint was before this existed. A default
    # would silently move one onto a port of its own.
    "networks": [],
    # …and, unlike MODELS, one of them is nominated. It has to be: the display
    # ports live here now rather than in app.json, so an endpoint naming no
    # profile still has to answer somewhere, and that somewhere is this one.
    # A default network profile is always SHARED, or endpoints naming nothing
    # would be pointed at a port that refuses to carry more than one.
    # WHICH PROFILE OWNS THE BUILT-IN DISPLAY PORT, and nothing else. It was
    # also where an endpoint naming no profile landed, and that second job is
    # gone: it put two assistants on one port whenever two of them had simply
    # never been given one. Naming no profile now means no port at all.
    "network_default": "",
    "model_default": "",
    "look_default": "",
    "motion_default": "",
    "speech_default": "",
    "kiosks": [],
    # Which of them a device gets when it names none. An id rather than "the
    # first in the list", so reordering the panel cannot silently change what
    # every unconfigured screen in the building is doing — the same reason a
    # route's default is stored by id.
    "kiosk_default": "",
    # How long an enrolment code is worth anything for, in minutes. ZERO IS
    # NEVER, which is a real answer: a deployment that mints a code on Friday
    # and hangs the screen on Monday is not less secure for it, because a code
    # is one use and the row it enrols was approved the moment it was created.
    # Ten minutes is the default because the usual case is somebody walking
    # across a building with six characters in their head.
    "code_minutes": 10,
    # Which group each population lands in when it starts working. Minted on
    # first need rather than shipped, so an install that never uses groups
    # never grows two it did not ask for — see default_group.
    "device_group": "",
    "identity_group": "",
    # Set once ensure_system_groups has had its one chance to correct a name it
    # had shipped and since changed. After that a default group's name is the
    # admin's, including if they choose the old one back.
    "group_names_done": 0,
    # How long a technical event and its conversation record are kept. SHORT
    # on purpose: retention is the only control there is over a store that
    # holds what was said to a display, and a generous default is a decision
    # made on somebody's behalf about their household.
    "event_days": EVENT_DAYS_DEFAULT,
    # Where alerts go besides the list. Off by default: a server that started
    # posting somewhere on first run would be making a decision about somebody
    # else's network.
    "syslog_on": 0,
    "syslog_host": "",                   # blank means the local daemon
    "syslog_port": 514,
    "syslog_facility": "user",
    # A JSON POST, which is what ntfy, Slack, Discord and Gotify all take.
    "hook_on": 0,
    "hook_url": "",
    # ITS OWN CONNECTION, not a route's. Home Assistant is the strongest sink
    # in this deployment — already connected, and a thing that can speak
    # through the house, so a screen that dies gets announced by the building
    # it is part of. But hanging alerting off a ROUTE means alerting
    # disappears when somebody deletes that route, which is a surprising way
    # to lose the thing that tells you a screen is dead.
    "ha_on": 0,
    "ha_url": "",
    "ha_token": "",
    # Anything HA will call. persistent_notification.create always exists and
    # needs nothing configured, so it is the default; notify.notify or a
    # tts service is the one that actually speaks, and is a field rather than
    # an assumption because which of them exists is the deployment's business.
    "ha_service": "persistent_notification/create",
    # LAST, and last for a reason. smtplib costs no dependency, but email wants
    # a server and credentials and fails silently more often than anything else
    # here — a queue somewhere else decides whether this was ever delivered.
    "mail_on": 0,
    "mail_host": "", "mail_port": 587, "mail_tls": 1,
    "mail_user": "", "mail_pass": "",
    "mail_from": "", "mail_to": "",
    # Immediate, or gathered up and sent on a timer. Alerts marked `now` — the
    # one with a person standing at a screen — ignore this entirely.
    "digest_on": 0,
    "digest_minutes": 60,
    # The house asleep, on the device clock — the same clock dark hours use.
    "quiet_on": 0,
    "quiet_from": 22,
    "quiet_to": 7,
    # Kept so an existing document round-trips rather than losing a key on the
    # first save. `user` was the second DISPLAY kind and folded into `device`;
    # nothing reads this now, and nothing writes it either.
    "user_group": "",
}
MAX_FORM_FIELDS = 5
#: (low, high) for each number the panel can set
DISPLAY_LIMITS = {"event_days": EVENT_DAYS_LIMITS,
                  "max_displays": (2, 5000), "max_pending": (1, 1000),
                  "guest_days": (1, 3650),
                  # 0 is off — see code_minutes. A week is the top because a
                  # code good for longer than anybody remembers issuing it is
                  # one nobody will think to revoke.
                  "code_minutes": (0, 10080)}

#: The admin panel's own preview frames the real display page, so it says
#: hello like any other. It is not a display: it is the panel, served from the
#: admin listener to somebody already signed in as an admin. Recording it would
#: put a row in the enrolment queue every time an admin opened the panel.
PREVIEW_DISPLAY = {"id": "(preview)", "name": "preview", "approved": True,
                   "preview": True}

#: Refusals, in memory. The early warning when somebody is trying a URL they
#: overheard — and deliberately not on disk: it is diagnostic rather than
#: configuration, and a device outside the house repeating itself must not turn
#: into a write per utterance.
_display_refusals = {}           # display id -> [count, last_ts, endpoint name]


def read_displays_doc():
    try:
        with open(DISPLAYS_PATH) as fh:
            doc = json.load(fh)
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def clean_form(raw):
    """The admin's request form, sanitised. A field with no label is a box
    nobody can answer, so it is dropped rather than shown blank — and only the
    first message field stays a message, because two paragraph boxes is a form
    somebody built by accident."""
    out, seen_message = [], False
    for f in (raw or [])[:MAX_FORM_FIELDS]:
        if not isinstance(f, dict):
            continue
        label = str(f.get("label") or "").strip()[:60]
        if not label:
            continue
        message = bool(f.get("message")) and not seen_message
        seen_message = seen_message or message
        out.append({"label": label, "required": bool(f.get("required")),
                    "message": message})
    return out


def clean_savers(raw):
    """The screensaver profiles, sanitised, in the order the panel put them.

    An id is minted for a profile that arrives without one, and kept for every
    profile that has one — a device names a profile by id, so a rename must not
    orphan it and a reorder must not silently move a screen onto somebody
    else's numbers. Duplicate ids are re-minted for the same reason: two rows
    claiming the same id is one row nobody can point at."""
    out, seen = [], set()
    for s in (raw or [])[:MAX_SAVERS]:
        if not isinstance(s, dict):
            continue
        name = str(s.get("name") or "").strip()[:40]
        if not name:
            continue                     # a profile with no name is unpickable
        sid = str(s.get("id") or "")[:16]
        if not sid or sid in seen:
            sid = "s" + secrets.token_hex(4)
        seen.add(sid)
        row = {"id": sid, "name": name}
        for k, (lo, hi) in SAVER_LIMITS.items():
            try:
                v = int(s.get(k, SAVER_OFF[k]))
            except (TypeError, ValueError):
                v = SAVER_OFF[k]
            row[k] = 0 if (k == "delay" and v <= 0) else min(hi, max(lo, v))
        # A window of zero length is no window, however it was written.
        if row["night_from"] == row["night_to"]:
            row["night_dim"] = 0
        out.append(row)
    return out


#: The three profile lists that are snapshots of a settings tab, and the tab
#: each one belongs to. A profile holds EVERY key that tab writes rather than a
#: hand-picked four: the tab is the editor and the profile is what it looked
#: like when you pressed the button, so anything you could tune there is
#: something a place can differ in.
#:
#: The values are stored the way the shared settings document is stored —
#: unvalidated here, checked by the display as it applies them. That is not
#: laxness, it is the same contract: settings.json is written the same way, and
#: a second validator that drifted from the display's own would be worse than
#: none.
PROFILE_LISTS = {"looks": "look", "motions": "motion", "speeches": "speech"}

#: A profile carries at most this many keys. A tab has tens; a document
#: arriving with thousands is not a profile.
MAX_PROFILE_KEYS = 120


def clean_profiles(raw, prefix, limit=None):
    """A list of {id, name, values}, sanitised, in the order the panel put it.

    Same id discipline as the screensavers — see clean_savers — because a
    device and a kiosk profile both name these by id, so a rename must not
    orphan one and a reorder must not move a screen onto somebody else's
    settings."""
    out, seen = [], set()
    for s in (raw or [])[:(limit or MAX_LOOKS)]:
        if not isinstance(s, dict):
            continue
        name = str(s.get("name") or "").strip()[:40]
        if not name:
            continue
        pid = str(s.get("id") or "")[:16]
        if not pid or pid in seen:
            pid = prefix + secrets.token_hex(4)
        seen.add(pid)
        vals = s.get("values")
        if not isinstance(vals, dict):
            # An old-shape appearance profile: four settings sitting flat on
            # the row. Lift them into `values` rather than dropping them —
            # this is what somebody's hallway already looks like.
            vals = {k: s[k] for k in LOOK_VALUES if k in s}
        clean = {}
        for k, v in list(vals.items())[:MAX_PROFILE_KEYS]:
            if isinstance(k, str) and isinstance(v, (str, int, float, bool)):
                clean[k[:40]] = v
        out.append({"id": pid, "name": name, "values": clean})
    return out


def clean_looks(raw):
    """Kept as its own name because the appearance list is referenced by it all
    over — it is clean_profiles with the appearance prefix."""
    return clean_profiles(raw, "l", MAX_LOOKS)


def find_look(lid, looks=None):
    """The appearance a row names, or None for "whatever everybody gets".

    None where it names nothing and None where it names one that has been
    deleted — the same fail-quiet as a missing screensaver, and here it means
    the screen falls back to the shared document, which is a working
    appearance rather than a blank one."""
    if not lid:
        return None
    for s in (looks if looks is not None else display_settings()["looks"]):
        if s["id"] == lid:
            return dict(s.get("values") or {})
    return None


def find_saver(sid, savers=None):
    """The profile a row names, resolved to numbers. Off where it names none,
    and off where it names one that has been deleted — a screen must not go on
    drifting to a profile nobody can find in the panel to change."""
    if not sid:
        return dict(SAVER_OFF)
    for s in (savers if savers is not None else display_settings()["savers"]):
        if s["id"] == sid:
            return {k: s[k] for k in SAVER_OFF}
    return dict(SAVER_OFF)


#: How many kiosk profiles may exist. The same reasoning as the screensavers:
#: a deployment has a handful of KINDS of public screen — a hallway, a
#: reception desk, a shop floor — not one per screen.
MAX_KIOSKS = 8

#: What a kiosk profile holds, and the value of each where it says nothing.
#:
#: COMPOSED rather than self-contained: `look` and `saver` are ids into the two
#: lists beside this one rather than copies of their values. Absorbing them
#: would make a profile simpler to read and make a rebrand a job of editing
#: eight of them — and it would lose the case that turns up first in any
#: building with more than three screens, where day and night in one hallway
#: share an appearance and differ only in the dim.
KIOSK_OFF = {"voice_only": True, "look": "", "motion": "", "speech": "",
             "saver": "",
             # Asked for on the first touch, and off is a real answer: a screen
             # somebody also browses on wants its address bar, and a television
             # whose operating system already hides the chrome gains nothing.
             "fullscreen": True,
             # Ask the browser to keep the backlight on. The device's own idea
             # of when to sleep is the one thing between a wall screen and a
             # black rectangle, and a screen that sleeps cannot be walked up to
             # and spoken to — the microphone is behind a page nobody can see.
             # Off is a real answer on a television or a tablet whose operating
             # system is already set never to sleep, where holding the lock
             # gains nothing and costs the battery.
             "keep_awake": True,
             # The line low in the frame that tells a passer-by this listens.
             "prompt": True,
             # …and what it says. EMPTY MEANS the automatic one, built from the
             # wake words this display actually answers to — which is right far
             # more often than anything typed here, and stays right when a wake
             # word is renamed. Typed text is for the deployment where the
             # generated line is not the point: a shop floor that would rather
             # say "ask me about opening hours".
             "prompt_text": ""}

#: One dim line at the foot of a screen, read in passing. Anything longer is a
#: paragraph nobody standing up will finish.
MAX_PROMPT_TEXT = 80


def clean_kiosks(raw):
    """The kiosk profiles, sanitised, in the order the panel put them.

    Ids are minted and kept exactly as they are for a screensaver: a device
    names a profile by id, so a rename must not orphan it and a reorder must
    not move a screen onto somebody else's settings."""
    out, seen = [], set()
    for k in (raw or [])[:MAX_KIOSKS]:
        if not isinstance(k, dict):
            continue
        name = str(k.get("name") or "").strip()[:40]
        if not name:
            continue                     # a profile with no name is unpickable
        kid = str(k.get("id") or "")[:16]
        if not kid or kid in seen:
            kid = "k" + secrets.token_hex(4)
        seen.add(kid)
        out.append({"id": kid, "name": name,
                    "voice_only": bool(k.get("voice_only", KIOSK_OFF["voice_only"])),
                    "look": str(k.get("look") or "")[:16],
                    "motion": str(k.get("motion") or "")[:16],
                    "speech": str(k.get("speech") or "")[:16],
                    "saver": str(k.get("saver") or "")[:16],
                    "fullscreen": bool(k.get("fullscreen", KIOSK_OFF["fullscreen"])),
                    "keep_awake": bool(k.get("keep_awake", KIOSK_OFF["keep_awake"])),
                    "prompt": bool(k.get("prompt", KIOSK_OFF["prompt"])),
                    "prompt_text": str(k.get("prompt_text") or "")
                                   .strip()[:MAX_PROMPT_TEXT]})
    return out


def find_kiosk(kid, kiosks=None, default_id=None):
    """The profile a row names, or the deployment's default where it names
    none — which is what "the admin picks which kiosk is the default" means at
    the point it is read.

    A row naming a profile that has since been deleted falls back to the
    default rather than to nothing, for the same reason a missing screensaver
    falls back to off: a screen must keep working, and the panel is where the
    mistake is visible."""
    pool = display_settings()["kiosks"] if kiosks is None else kiosks
    if default_id is None:
        default_id = display_settings()["kiosk_default"]
    for want in (str(kid or ""), str(default_id or "")):
        if not want:
            continue
        for k in pool:
            if k["id"] == want:
                return k
    return None


def display_settings():
    """Kept beside the displays rather than in the shared settings document,
    which is world readable and belongs to the interface. Who may ask this
    server for something is not an appearance value."""
    cfg = dict(DISPLAY_SETTINGS)
    stored = read_displays_doc().get("settings")
    if isinstance(stored, dict):
        cfg.update({k: v for k, v in stored.items() if k in DISPLAY_SETTINGS})
    for k, (lo, hi) in DISPLAY_LIMITS.items():
        try:
            cfg[k] = min(hi, max(lo, int(cfg[k])))
        except (TypeError, ValueError):
            cfg[k] = DISPLAY_SETTINGS[k]
    cfg["guest_requests"] = bool(cfg["guest_requests"])
    cfg["form"] = clean_form(cfg.get("form"))
    cfg["savers"] = clean_savers(cfg.get("savers"))
    cfg["looks"] = clean_looks(cfg.get("looks"))
    return cfg


def write_display_settings(cfg):
    doc = read_displays_doc()
    doc["settings"] = cfg
    _write_displays_doc(doc)


def panel_settings():
    """display_settings() with the credentials taken out.

    A model profile holds an API key, and the panel has no business receiving
    one — the same rule a route's key has always followed. It is told WHETHER
    there is a key, which is what an admin needs to tell a configured profile
    from an unconfigured one, and never the key itself."""
    cfg = dict(display_settings())
    out = []
    for m in cfg.get("models") or []:
        row = dict(m)
        vals = dict(row.get("values") or {})
        row["has_key"] = bool(vals.pop("api_key", ""))
        row["values"] = vals
        out.append(row)
    cfg["models"] = out
    # The alert sink's token, by the same rule: the panel is told WHETHER one
    # is set, which is what tells a configured sink from an unconfigured one,
    # and never the token.
    cfg["ha_has_token"] = bool(cfg.pop("ha_token", ""))
    cfg["mail_has_pass"] = bool(cfg.pop("mail_pass", ""))
    return cfg


def validate_display_settings(obj, current):
    """Returns (settings, error). The one rule that is not a range: guest
    requests cannot be switched off while there is nowhere for a guest to go —
    see open_default_ok."""
    cfg = dict(current)
    for k, (lo, hi) in DISPLAY_LIMITS.items():
        if k not in obj:
            continue
        try:
            v = int(obj[k])
        except (TypeError, ValueError):
            return None, "%s must be a whole number" % k.replace("_", " ")
        if not (lo <= v <= hi):
            return None, ("%s must be between %d and %d"
                          % (k.replace("_", " "), lo, hi))
        cfg[k] = v
    if cfg["max_pending"] > cfg["max_displays"]:
        return None, ("more waiting than there is room for — the waiting limit "
                      "cannot exceed the total")
    # The syslog sink. Its own block because none of it is a range: a switch, a
    # host that may be blank on purpose, a port, and a name from a fixed list.
    if "syslog_on" in obj:
        cfg["syslog_on"] = 1 if obj["syslog_on"] else 0
    if "syslog_host" in obj:
        cfg["syslog_host"] = str(obj["syslog_host"] or "").strip()[:120]
    if "syslog_port" in obj:
        try:
            port = int(obj["syslog_port"])
        except (TypeError, ValueError):
            return None, "the syslog port must be a whole number"
        if not (1 <= port <= 65535):
            return None, "the syslog port must be between 1 and 65535"
        cfg["syslog_port"] = port
    if "syslog_facility" in obj:
        f = str(obj["syslog_facility"] or "").strip()
        if f not in SYSLOG_FACILITIES:
            return None, "facility must be one of: " + ", ".join(SYSLOG_FACILITIES)
        cfg["syslog_facility"] = f
    if "ha_on" in obj:
        cfg["ha_on"] = 1 if obj["ha_on"] else 0
    if "ha_url" in obj:
        u = str(obj["ha_url"] or "").strip()[:200]
        if u and not u.startswith(("http://", "https://")):
            return None, "Home Assistant needs its full http:// or https:// address"
        cfg["ha_url"] = u
    if "ha_token" in obj:
        # Blank means LEAVE IT, not clear it. A panel that is never sent the
        # token cannot send it back, so an empty field on a save is the field
        # it was never given rather than an instruction to forget.
        t = str(obj["ha_token"] or "").strip()
        if t:
            cfg["ha_token"] = t[:400]
    if "ha_clear_token" in obj and obj["ha_clear_token"]:
        cfg["ha_token"] = ""
    if "ha_service" in obj:
        sv = str(obj["ha_service"] or "").strip()[:80]
        if sv and not re.fullmatch(r"[a-z0-9_]+[./][a-z0-9_]+", sv):
            return None, "a service reads like notify.notify or notify/notify"
        cfg["ha_service"] = sv or "persistent_notification/create"
    if cfg.get("ha_on") and not (cfg.get("ha_url") and cfg.get("ha_token")):
        return None, ("Home Assistant needs its address and a long-lived token "
                      "before it can be switched on")
    if "hook_on" in obj:
        cfg["hook_on"] = 1 if obj["hook_on"] else 0
    if "hook_url" in obj:
        u = str(obj["hook_url"] or "").strip()[:400]
        if u and not u.startswith(("http://", "https://")):
            return None, "a webhook needs a full http:// or https:// address"
        cfg["hook_url"] = u
    if cfg.get("hook_on") and not cfg.get("hook_url"):
        return None, "give the webhook an address before switching it on"
    if "mail_on" in obj:
        cfg["mail_on"] = 1 if obj["mail_on"] else 0
    for k, cap in (("mail_host", 200), ("mail_user", 200),
                   ("mail_from", 200), ("mail_to", 400)):
        if k in obj:
            cfg[k] = str(obj[k] or "").strip()[:cap]
    if "mail_pass" in obj:
        # Blank keeps what is stored, the same rule the HA token follows.
        pw = str(obj["mail_pass"] or "")
        if pw:
            cfg["mail_pass"] = pw[:200]
    if "mail_clear_pass" in obj and obj["mail_clear_pass"]:
        cfg["mail_pass"] = ""
    if "mail_tls" in obj:
        cfg["mail_tls"] = 1 if obj["mail_tls"] else 0
    if "mail_port" in obj:
        try:
            mp = int(obj["mail_port"])
        except (TypeError, ValueError):
            return None, "the mail port must be a whole number"
        if not (1 <= mp <= 65535):
            return None, "the mail port must be between 1 and 65535"
        cfg["mail_port"] = mp
    if cfg.get("mail_on") and not (cfg.get("mail_host") and cfg.get("mail_to")):
        return None, "mail needs a server and somewhere to send to"
    if "digest_on" in obj:
        cfg["digest_on"] = 1 if obj["digest_on"] else 0
    if "digest_minutes" in obj:
        try:
            dm = int(obj["digest_minutes"])
        except (TypeError, ValueError):
            return None, "the digest interval is a whole number of minutes"
        if not (5 <= dm <= 1440):
            return None, "the digest interval runs from 5 minutes to a day"
        cfg["digest_minutes"] = dm
    if "quiet_on" in obj:
        cfg["quiet_on"] = 1 if obj["quiet_on"] else 0
    for k in ("quiet_from", "quiet_to"):
        if k in obj:
            try:
                h = int(obj[k])
            except (TypeError, ValueError):
                return None, "quiet hours are whole hours"
            if not (0 <= h <= 23):
                return None, "quiet hours run 0 to 23"
            cfg[k] = h
    if "form" in obj:
        if not isinstance(obj["form"], (list, tuple)):
            return None, "the request form must be a list of fields"
        if len(obj["form"]) > MAX_FORM_FIELDS:
            return None, "a request form has at most %d fields" % MAX_FORM_FIELDS
        for f in obj["form"]:
            if isinstance(f, dict) and not str(f.get("label") or "").strip():
                return None, "every field needs a label — it is what somebody reads"
        cfg["form"] = clean_form(obj["form"])
    if "savers" in obj:
        if not isinstance(obj["savers"], (list, tuple)):
            return None, "the screensaver profiles must be a list"
        if len(obj["savers"]) > MAX_SAVERS:
            return None, "there is room for %d screensaver profiles" % MAX_SAVERS
        for s in obj["savers"]:
            if not isinstance(s, dict):
                return None, "a screensaver profile must be a set of fields"
            if not str(s.get("name") or "").strip():
                return None, ("every profile needs a name — it is what you pick "
                              "on a device")
            # Refused rather than clamped, because this is somebody typing a
            # number and pressing save: quietly storing 90 where they asked for
            # 900 is the panel lying about what it did. clean_savers clamps
            # instead, and it is reading a file rather than answering a person.
            for k, (lo, hi) in SAVER_LIMITS.items():
                if k not in s:
                    continue
                try:
                    v = int(s[k])
                except (TypeError, ValueError):
                    return None, "%s must be a whole number" % k
                if k == "delay" and v <= 0:
                    continue             # never starts, which is a real answer
                if not (lo <= v <= hi):
                    return None, ("%s must be between %d and %d" % (k, lo, hi)
                                  + (" — or 0 for never" if k == "delay" else "")
                                  + (" (an hour of the day)"
                                     if k.startswith("night_") and k != "night_dim"
                                     else ""))
        cfg["savers"] = clean_savers(obj["savers"])
    if "looks" in obj:
        if not isinstance(obj["looks"], (list, tuple)):
            return None, "the appearance profiles must be a list"
        if len(obj["looks"]) > MAX_LOOKS:
            return None, "there is room for %d appearance profiles" % MAX_LOOKS
        for s in obj["looks"]:
            if not isinstance(s, dict):
                return None, "an appearance profile must be a set of fields"
            if not str(s.get("name") or "").strip():
                return None, ("every profile needs a name — it is what you pick "
                              "on a device")
            for k, allowed in LOOK_VALUES.items():
                if k in s and str(s[k]) not in allowed:
                    return None, ("%s must be one of: %s"
                                  % (k, ", ".join(allowed)))
        cfg["looks"] = clean_looks(obj["looks"])
    # The geometry and speech lists, validated exactly as the appearance one is:
    # a name, and a bag of settings the display checks as it applies them.
    if "models" in obj:
        if not isinstance(obj["models"], (list, tuple)):
            return None, "the model profiles must be a list"
        if len(obj["models"]) > MAX_LOOKS:
            return None, "there is room for %d model profiles" % MAX_LOOKS
        for m in obj["models"]:
            if not isinstance(m, dict):
                return None, "a model profile must be a set of fields"
            if not str(m.get("name") or "").strip():
                return None, ("every profile needs a name — it is what an "
                              "endpoint picks")
        # The panel is never sent a key, so it cannot send one back. A profile
        # arriving without one keeps what is stored rather than blanking it —
        # otherwise every save would forget the credential.
        stored = {p["id"]: dict(p.get("values") or {}) for p in cfg["models"]}
        rows = clean_profiles(obj["models"], "n", MAX_LOOKS)
        for r in rows:
            had = stored.get(r["id"]) or {}
            # Kept only while the provider is the same one. The panel never
            # shows a key, so it sends none unless you type one — and carrying
            # the stored one across a provider change would hand Home
            # Assistant's token to api.anthropic.com, which is the one failure
            # validate_backend exists to refuse. Same provider, no key typed:
            # keep it, or every save would forget the credential.
            if ((r["values"].get("provider") or "demo")
                    == (had.get("provider") or "demo")
                    and not r["values"].get("api_key") and had.get("api_key")):
                r["values"]["api_key"] = had["api_key"]
            # The same connection check routes used to get. It has to run here
            # or nowhere now: an endpoint no longer carries a connection to
            # check, and a profile saved without the key its provider needs
            # would fail silently, in front of somebody, mid-sentence.
            base = dict(BACKEND_DEFAULTS)
            base.update(had)
            _, err = validate_backend(r["values"], base)
            if err:
                return None, "%s: %s" % (r["name"], err)
        cfg["models"] = rows
    if "networks" in obj:
        if not isinstance(obj["networks"], (list, tuple)):
            return None, "the network profiles must be a list"
        if len(obj["networks"]) > MAX_LOOKS:
            return None, "there is room for %d network profiles" % MAX_LOOKS
        rows = clean_profiles(obj["networks"], "w", MAX_LOOKS)
        # Only the admin portal's port is reserved now. The display ports are
        # these profiles — a profile holding what used to be app.json's
        # https_port is the migration doing its job, not a collision.
        adm = read_app()["admin_port"]
        seen = {}
        # Read once for the whole save: the interface list is an ioctl sweep,
        # and it was being taken again for every port of every profile.
        here = local_interfaces()
        have = [a for a, _ in here]
        for r in rows:
            addr = str(r["values"].get("address") or "").strip()
            try:
                pv = int(r["values"].get("port"))
            except (TypeError, ValueError):
                return None, "%s: give it a port number" % r["name"]
            rd = str(r["values"].get("redirect") or "").strip()
            try:
                rv = int(rd) if rd else 0
            except ValueError:
                return None, ("%s: the plain HTTP port must be a whole number, "
                              "or empty for none" % r["name"])
            # Before the collision sweep, or a redirect pointing at its own
            # port reports itself as clashing with itself.
            if rv and rv == pv:
                return None, ("%s: the plain HTTP port cannot be the same as "
                              "the port it redirects to" % r["name"])
            for label, v in (("port", pv), ("plain HTTP port", rv)):
                if not v and label != "port":
                    continue
                if not (PORT_MIN <= v <= PORT_MAX):
                    return None, ("%s: the %s must be between %d and %d — "
                                  "below %d needs root, and this server runs "
                                  "as an ordinary user"
                                  % (r["name"], label, PORT_MIN, PORT_MAX,
                                     PORT_MIN))
                if v == adm:
                    return None, ("%s: %d is the admin portal's port — that "
                                  "one stays under ADMIN SETTINGS, and it is "
                                  "the way back in when something here is "
                                  "wrong" % (r["name"], v))
                # Keyed by address AND port: two profiles on one port do not
                # collide when they answer on different addresses, and
                # refusing that would reject a configuration the machine can
                # carry. ANY collides with everything on that port, because
                # that is what ANY means.
                # `here` is read once for the whole save, above — this used to
                # ask the kernel for the interface list again for every port of
                # every profile.
                akey = addr
                for k in ({(akey, v), ("", v)} if akey else
                          {(a, v) for a in have} | {("", v)}):
                    if k in seen:
                        return None, ("%s and %s are both on port %d%s"
                                      % (seen[k], r["name"], v,
                                         " on " + k[0] if k[0] else ""))
                seen[(akey, v)] = r["name"]
            # WHICH ADDRESS it answers on. Empty is ANY. Checked against what
            # this machine actually has, for the same reason the binding under
            # ADMIN SETTINGS is chosen rather than typed: an address this
            # machine does not have is a listener that will not start.
            if addr and addr not in have:
                return None, ("%s: this machine has no address %s — pick one "
                              "of its own, or ANY" % (r["name"], addr))
            # …and whether the port can actually be had there, BEFORE anything
            # is allowed to use it. A port that passes validation and fails at
            # the next restart is a profile that looks saved and is not, found
            # out at the worst moment.
            #
            # ONLY WHERE IT MOVED. The panel sends every profile on every save,
            # so checking all of them means an edit to one row is refused by
            # the state of another — and a row that has not changed is either
            # already running or already known to be broken. Neither is this
            # save's business.
            was = {p["id"]: (p.get("values") or {})
                   for p in (current.get("networks") or [])}.get(r["id"])
            moved = (not was
                     or str(was.get("address") or "") != addr
                     or int(was.get("port") or 0) != pv
                     or int(was.get("redirect") or 0) != rv)
            for v in ((pv, rv) if moved else ()):
                if not v:
                    continue
                if addr:
                    if not port_free(v, addr):
                        return None, ("%s: %d is already in use on %s"
                                      % (r["name"], v, addr))
                else:
                    ok, taken = port_free_anywhere(v, have or [LOOPBACK])
                    if not ok:
                        # Named, with its interface, because ANY is refused by
                        # ONE address holding the port and the whole question
                        # is which. The fix is either to stop whatever has it,
                        # or to name an address here that is free.
                        by = ", ".join("%s (%s)" % (a, dict(here).get(a) or "?")
                                       for a in taken)
                        return None, ("%s: ANY needs %d free on every address, "
                                      "and it is already in use on %s"
                                      % (r["name"], v, by))
            r["values"]["address"] = addr
            r["values"]["port"] = pv
            r["values"]["redirect"] = rv
        cfg["networks"] = rows
        # There is always a default: it is where an endpoint naming no profile
        # answers, which is the display port. It no longer has to be "shared",
        # because nothing is — it carries ONE endpoint like every other port,
        # and a second endpoint naming no profile is refused at the endpoint.
        want = str(obj.get("network_default") or cfg.get("network_default") or "")
        by_id = {r["id"]: r for r in rows}
        if want not in by_id:
            want = rows[0]["id"] if rows else ""
        cfg["network_default"] = want
    for key, prefix in (("motions", "m"), ("speeches", "p")):
        if key not in obj:
            continue
        if not isinstance(obj[key], (list, tuple)):
            return None, "the %s profiles must be a list" % key[:-1]
        if len(obj[key]) > MAX_LOOKS:
            return None, ("there is room for %d %s profiles"
                          % (MAX_LOOKS, key[:-1]))
        for pr in obj[key]:
            if not isinstance(pr, dict):
                return None, "a profile must be a set of fields"
            if not str(pr.get("name") or "").strip():
                return None, ("every profile needs a name — it is what you pick "
                              "on a kiosk")
        cfg[key] = clean_profiles(obj[key], prefix, MAX_LOOKS)
    if "kiosks" in obj:
        if not isinstance(obj["kiosks"], (list, tuple)):
            return None, "the kiosk profiles must be a list"
        if len(obj["kiosks"]) > MAX_KIOSKS:
            return None, "there is room for %d kiosk profiles" % MAX_KIOSKS
        if not obj["kiosks"]:
            return None, ("there has to be at least one kiosk profile — a "
                          "screen ticked as a kiosk needs something to be")
        for k in obj["kiosks"]:
            if not isinstance(k, dict):
                return None, "a kiosk profile must be a set of fields"
            if not str(k.get("name") or "").strip():
                return None, ("every profile needs a name — it is what you pick "
                              "on a device")
            # Refused rather than truncated, for the reason the screensaver
            # numbers are: this is somebody typing and pressing save, and
            # quietly storing half their sentence is the panel lying about
            # what it did. clean_kiosks truncates instead, and it is reading a
            # file rather than answering a person.
            if len(str(k.get("prompt_text") or "").strip()) > MAX_PROMPT_TEXT:
                return None, ("the prompt line has to fit in %d characters — it "
                              "is one line read in passing" % MAX_PROMPT_TEXT)
            # Named and gone, told rather than swallowed — the same rule as a
            # device naming a deleted profile.
            for key, pool, what in (("saver", cfg["savers"], "screensaver"),
                                    ("look", cfg["looks"], "appearance"),
                                    ("motion", cfg["motions"], "geometry"),
                                    ("speech", cfg["speeches"], "speech")):
                pid = str(k.get(key) or "")
                if pid and not any(p["id"] == pid for p in pool):
                    return None, ("a kiosk profile names a %s that no longer "
                                  "exists — reload the panel to see the "
                                  "current list" % what)
        cfg["kiosks"] = clean_kiosks(obj["kiosks"])
    # Which profile each list hands to a display that names none. Corrected
    # rather than refused when it points at nothing — the deletion was the
    # deliberate act, and a list whose default named a profile that is gone
    # would leave every ordinary screen with no appearance at all.
    #
    # WHICH KEY BELONGS TO WHICH TAB is not known here, and deliberately: that
    # mapping is built in the panel from the sections themselves, so a control
    # moved between tabs cannot leave a stale copy of the answer on the server.
    # Seeding the first profile is the panel's job for the same reason.
    for dkey, lkey in (("look_default", "looks"), ("motion_default", "motions"),
                       ("speech_default", "speeches"), ("model_default", "models")):
        if dkey in obj:
            want = str(obj[dkey] or "")
            if want and not any(p["id"] == want for p in cfg[lkey]):
                return None, "that default is not one of the %s profiles" % lkey[:-1]
            if want:
                cfg[dkey] = want
        if cfg[lkey] and not any(p["id"] == cfg.get(dkey) for p in cfg[lkey]):
            cfg[dkey] = cfg[lkey][0]["id"]
    if "kiosk_default" in obj:
        want = str(obj["kiosk_default"] or "")
        # Empty is "choose for me", not a mistake — it is what a deployment
        # saving its very first profile has to send, since there was nothing to
        # nominate before this request. Only a NAMED default that matches
        # nothing is somebody's stale panel, and that is worth saying.
        if want and not any(k["id"] == want for k in cfg["kiosks"]):
            return None, "the default has to be one of the kiosk profiles"
        if want:
            cfg["kiosk_default"] = want
    # A default that named a profile somebody just deleted is corrected here
    # rather than refused: the deletion was the deliberate act, and leaving the
    # deployment pointing at nothing would take every unconfigured screen with
    # it.
    if cfg["kiosks"] and not any(k["id"] == cfg.get("kiosk_default")
                                 for k in cfg["kiosks"]):
        cfg["kiosk_default"] = cfg["kiosks"][0]["id"]
    if "guest_requests" in obj:
        cfg["guest_requests"] = bool(obj["guest_requests"])
    return cfg, None


def read_displays():
    try:
        with open(DISPLAYS_PATH) as fh:
            doc = json.load(fh)
        stored = doc.get("displays", {}) if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}
    out = {}
    for did, rec in stored.items():
        if not isinstance(rec, dict):
            continue
        row = dict(DISPLAY_DEFAULTS)
        row.update({k: v for k, v in rec.items() if k in DISPLAY_DEFAULTS})
        out[str(did)] = row
    return out


def _write_displays_doc(doc):
    doc["version"] = 1
    doc.setdefault("displays", {})
    with _displays_lock:
        tmp = DISPLAYS_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(doc, fh, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)                     # token hashes
        os.replace(tmp, DISPLAYS_PATH)


def write_displays(displays):
    """Rows only. Read-modify-write of the whole document rather than a
    replacement of it, because the settings live in the same file and a row
    being written must not take the admin's form and limits with it."""
    doc = read_displays_doc()
    doc["displays"] = displays
    _write_displays_doc(doc)


def migrate_models():
    """One-time: lift each endpoint's connection into a model profile.

    Deduplicated by the connection itself, so two endpoints already pointed at
    the same base URL and model come back as one profile that both name —
    which is the whole reason for the list. A profile is named after the first
    endpoint using it, because that is the name somebody will recognise.

    Runs only while the list is empty and something has a connection to lift:
    after that the profiles are the source of truth and a route's own copy is
    vestigial."""
    doc = read_routes()
    routes = doc.get("routes") or {}
    if not routes:
        return
    ddoc = read_displays_doc()
    cfg = ddoc.get("settings")
    cfg = dict(cfg) if isinstance(cfg, dict) else {}
    if clean_profiles(cfg.get("models"), "n", MAX_LOOKS):
        return                              # already imported, or hand-built
    made, order = {}, []
    for rid in route_order(doc):
        rec = routes[rid]
        key = tuple(str(rec.get(k) or "") for k in MODEL_KEYS)
        if key not in made:
            prof = {"id": "n" + secrets.token_hex(4),
                    "name": rec.get("name") or "endpoint",
                    "values": {k: rec.get(k) or "" for k in MODEL_KEYS}}
            made[key] = prof
            order.append(prof)
        rec["model_profile"] = made[key]["id"]
    if not order:
        return
    cfg["models"] = order
    if cfg.get("model_default") not in [p["id"] for p in order]:
        # The default endpoint's connection is the one an endpoint naming
        # nothing should get.
        dflt = routes.get(doc.get("default")) or {}
        cfg["model_default"] = dflt.get("model_profile") or order[0]["id"]
    ddoc["settings"] = cfg
    _write_displays_doc(ddoc)
    doc["routes"] = routes
    write_routes(doc)
    print("model migration: %d endpoint(s) -> %d profile(s) (%s)"
          % (len(routes), len(order), ", ".join(p["name"] for p in order)),
          flush=True)


def migrate_networks():
    """One-time: the display's ports become a network profile.

    They were in app.json beside the admin portal's, which put three ports in
    one place that answer to two different things — the portal an admin signs
    into, and the interface everybody else uses. The portal's stays there,
    because it is the way back in when what is here is wrong. The display's
    becomes a profile named DISPLAY, shared, carrying every endpoint that names
    no other — which is exactly what that port was already doing.

    Nothing is removed from app.json. The keys stay where they are, unread, so
    an install that is rolled back comes up on the ports it always had."""
    ddoc = read_displays_doc()
    cfg = ddoc.get("settings")
    cfg = dict(cfg) if isinstance(cfg, dict) else {}
    rows = clean_profiles(cfg.get("networks"), "w", MAX_LOOKS)
    have = str(cfg.get("network_default") or "")
    if have and any(r["id"] == have for r in rows):
        return                                          # already nominated
    # A profile list built before there was a default is not a reason to
    # invent a second display port. Take the first one there is; otherwise the
    # app's own ports become the profile they always were in everything but
    # name.
    pick = rows[0]["id"] if rows else ""
    if not pick:
        app = read_app()
        prof = {"id": "w" + secrets.token_hex(4), "name": "Display",
                "values": {"port": app["https_port"],
                           "redirect": app["http_port"]}}
        rows = [prof] + rows
        pick = prof["id"]
        print("network migration: display ports %d/%d -> profile "
              "\u201cDisplay\u201d"
              % (app["https_port"], app["http_port"]), flush=True)
    cfg["networks"] = rows
    cfg["network_default"] = pick
    ddoc["settings"] = cfg
    _write_displays_doc(ddoc)
    print("network migration: default port profile is \u201c%s\u201d; ADMIN "
          "SETTINGS now holds the admin portal's port only"
          % next(r["name"] for r in rows if r["id"] == pick), flush=True)


def ensure_default_kiosk():
    """There is always at least one kiosk profile, and always one nominated as
    the default.

    A tickbox whose only companion is an empty list is a control that appears
    broken to the person meeting it first. Seeding one means ticking KIOSK on a
    screen does something immediately, and the admin renames or re-points it
    rather than being made to build one before anything works."""
    doc = read_displays_doc()
    cfg = doc.get("settings")
    cfg = dict(cfg) if isinstance(cfg, dict) else {}
    kiosks = clean_kiosks(cfg.get("kiosks"))
    changed = False
    if not kiosks:
        kiosks = [dict(KIOSK_OFF, id="k" + secrets.token_hex(4), name="Default")]
        changed = True
    if cfg.get("kiosk_default") not in [k["id"] for k in kiosks]:
        cfg["kiosk_default"] = kiosks[0]["id"]
        changed = True
    if not changed:
        return
    cfg["kiosks"] = kiosks
    doc["settings"] = cfg
    _write_displays_doc(doc)


def migrate_kiosks():
    """One-time: fold the old per-row wall settings into kiosk profiles.

    This has to run before anything else reads a display, because
    `read_displays` keeps only the keys in DISPLAY_DEFAULTS — so the moment
    those defaults stopped naming `wall`, `voice_only`, `saver` and `look`, the
    next write of any row would have dropped them on the floor. Nobody would
    have seen it happen; the screen would simply have stopped being a kiosk one
    day.

    One profile per combination that was ACTUALLY IN USE, rather than one for
    every row: a building with a hallway and a reception desk comes back with
    both, and a building where twelve screens were set identically comes back
    with one profile that twelve rows name. Rows that were not on a wall mint
    nothing — their stored settings were never applied, so preserving them as a
    profile would invent a place that never existed."""
    doc = read_displays_doc()
    rows = doc.get("displays")
    if not isinstance(rows, dict):
        return
    legacy = [r for r in rows.values()
              if isinstance(r, dict) and "wall" in r and "kiosk" not in r]
    if not legacy:
        return
    cfg = doc.get("settings")
    cfg = dict(cfg) if isinstance(cfg, dict) else {}
    kiosks = clean_kiosks(cfg.get("kiosks"))
    made = {}
    for rec in legacy:
        was = bool(rec.get("wall"))
        rec["kiosk"] = was
        rec["kiosk_profile"] = ""
        if was:
            key = (bool(rec.get("voice_only", KIOSK_OFF["voice_only"])),
                   str(rec.get("saver") or ""), str(rec.get("look") or ""))
            if key not in made:
                prof = dict(KIOSK_OFF, id="k" + secrets.token_hex(4),
                            name="Default" if not kiosks else
                                 "Kiosk %d" % (len(kiosks) + 1),
                            voice_only=key[0], saver=key[1], look=key[2])
                made[key] = prof
                kiosks.append(prof)
            rec["kiosk_profile"] = made[key]["id"]
        for dead in ("wall", "voice_only", "saver", "look"):
            rec.pop(dead, None)
    cfg["kiosks"] = kiosks
    if cfg.get("kiosk_default") not in [k["id"] for k in kiosks] and kiosks:
        cfg["kiosk_default"] = kiosks[0]["id"]
    doc["settings"] = cfg
    doc["displays"] = rows
    _write_displays_doc(doc)
    print("kiosk migration: %d row(s), %d profile(s) made (%s)"
          % (len(legacy), len(made),
             ", ".join(p["name"] for p in made.values()) or "none"), flush=True)


def display_label(rec):
    """What to call it. The admin's name where there is one, then the name it
    announced itself with, then the first thing the person typed on the request
    form — which on a form that asks for a name is their name, and on one that
    does not is at least something that tells two rows apart.

    Without that last fall-back, everybody who asked for access appears as
    "unnamed display", which makes the list unreadable and the group picker
    unusable — a set of identical entries nobody can choose between."""
    if rec.get("name"):
        return rec["name"]
    if rec.get("asked"):
        return rec["asked"]
    for a in (rec.get("answers") or []):
        if a.get("value"):
            return str(a["value"])[:40]
    return "unnamed display"


KIOSK_FIELDS = ("kiosk", "kiosk_profile")


def kiosk_of(rec, savers=None, looks=None, kiosks=None, default_id=None,
             motions=None, speeches=None):
    """What this display is, resolved and clamped: whether it is a kiosk at
    all, whether the transcript is there, and the numbers of the screensaver
    the profile names.

    Resolved HERE rather than on the display, so a browser is handed three
    numbers and never the list of profiles. That list is a description of a
    building — *hallway*, *ward*, *shop floor* — and no display has any use for
    the names of places it is not in. The same applies to the kiosk profiles
    themselves: a screen is told what it is, never what the others are.

    Everything is off where the row is not a kiosk. The profile stays stored,
    so unticking is not the same as forgetting: a device taken down and put
    back up comes back as what it was."""
    if not rec.get("kiosk"):
        return {"kiosk": False, "voice_only": False, "look": None,
                "saver": dict(SAVER_OFF)}
    # `kiosk` is published in its own right and not merely implied by the
    # settings under it, because being a kiosk means things none of them
    # covers — a rig instrument in the corner of a hallway screen is the first.
    prof = find_kiosk(rec.get("kiosk_profile"), kiosks, default_id) or {}
    # The three snapshots are merged into ONE map of settings before it leaves
    # here. The display already knows how to take a map of settings and apply
    # it; handing it three would make it learn an order of precedence that only
    # ever has one answer. Appearance first, then geometry, then speech —
    # disjoint in practice, since each is the keys of one tab.
    # One read of the settings covers whichever pools the caller did not pass.
    cfg_all = None
    if looks is None or motions is None or speeches is None:
        cfg_all = display_settings()
    pools = {"look":   looks    if looks    is not None else cfg_all["looks"],
             "motion": motions  if motions  is not None else cfg_all["motions"],
             "speech": speeches if speeches is not None else cfg_all["speeches"]}
    merged = {}
    for key in ("look", "motion", "speech"):
        got = find_look(str(prof.get(key) or ""), pools[key] or [])
        if got:
            merged.update(got)
    return {"kiosk": True,
            "voice_only": bool(prof.get("voice_only", KIOSK_OFF["voice_only"])),
            "look": merged or None,
            "saver": find_saver(str(prof.get("saver") or ""), savers),
            "fullscreen": bool(prof.get("fullscreen", KIOSK_OFF["fullscreen"])),
            "keep_awake": bool(prof.get("keep_awake", KIOSK_OFF["keep_awake"])),
            "prompt": bool(prof.get("prompt", KIOSK_OFF["prompt"])),
            # The admin's words where there are any, and the empty string where
            # there are not — the display builds the automatic line itself,
            # because only the browser knows which wake words it is currently
            # answering to.
            "prompt_text": str(prof.get("prompt_text") or "")[:MAX_PROMPT_TEXT]}


def validate_kiosk(obj, rec, kiosks):
    """Returns (the two fields, error). Separate from
    validate_display_settings for the same reason the panel has a SAVE per
    block: these belong to one screen, those to the deployment, and one commit
    writing both would publish an edit somebody was halfway through.

    Two fields now rather than four. What a kiosk DOES moved into the profile,
    so a screen carries which kiosk it is and nothing else — and the settings
    that used to be edited a row at a time are edited once, where they are
    named."""
    out = {k: rec.get(k, DISPLAY_DEFAULTS[k]) for k in KIOSK_FIELDS}
    if "kiosk" in obj:
        out["kiosk"] = bool(obj["kiosk"])
    # Named and gone is an ERROR here, where it is merely a fall-back in
    # kiosk_of. The two are not inconsistent: a screen must fail quiet, and a
    # person pressing save must be told, or a panel left open while somebody
    # else deleted a profile silently sets a device to something it did not
    # choose.
    if "kiosk_profile" in obj:
        pid = str(obj["kiosk_profile"] or "")[:16]
        if pid and not any(p["id"] == pid for p in kiosks):
            return None, ("that kiosk profile no longer exists — reload the "
                          "panel to see the current list")
        out["kiosk_profile"] = pid
    # There is no "network" here. A screen does not choose a port: it is
    # loaded from the port its endpoints answer on, which display_network
    # reads back off the grant.
    return out, None


#: Last computed displays stamp, keyed by the file's modification time in
#: nanoseconds. Seconds are too coarse — two writes inside one second would
#: read as no change at all.
#: Keyed by display, because the stamp is. One slot held the last row asked
#: about and missed on every poll from every other screen — which turned "one
#: stat each rather than one hash each" into a hash each, for a building.
_DISPLAYS_STAMP = {}


def _displays_stamp(did=None):
    """A digest of the parts of displays.json a screen actually renders from —
    ITS OWN row, plus the settings every screen shares.

    NOT the file's modification time, and this is the whole reason this
    function exists: `last_seen` is written every few minutes by the very poll
    that reads this, so a stamp based on mtime would change on its own and
    order every display in the building to reload itself for ever. Only the
    fields an admin can change are in the digest — `asked`, `hint` and
    `expires` move without an admin (the last one every time a guest renews),
    and are nobody else's business either.

    PER DISPLAY, and it was not to begin with. Digesting every row meant any
    row appearing or disappearing changed the stamp for everybody: one device
    opening the display page reloaded every screen in the building, and
    deleting a row reloaded the very screens that had nothing to do with it —
    including, immediately, whichever browser had just created the row, which
    then said hello and made another. A screen reloads when ITS configuration
    moves. Another device arriving is not that.

    Recomputed only when the file has actually been written, so a poll from a
    building full of screens costs one stat each rather than one hash each."""
    try:
        st = os.stat(DISPLAYS_PATH)
    except OSError:
        return "0"                       # absent is a stamp of its own
    slot = _DISPLAYS_STAMP.get(did or "")
    key = (st.st_mtime_ns, st.st_size)
    if slot and slot[0] == key:
        return slot[1]
    try:
        raw = read_displays_doc()
    except Exception:
        return slot[1] if slot else "0"
    rows = raw.get("displays") or {}
    if isinstance(rows, dict):
        rows = [dict(r, id=k) for k, r in rows.items()]
    facts = sorted(
        "%s|%s|%s|%s|%s|%s" % (r.get("id"), bool(r.get("approved")),
                               bool(r.get("denied")), bool(r.get("kiosk")),
                               r.get("kiosk_profile") or "", r.get("name") or "")
        for r in rows
        if isinstance(r, dict) and (did is None or r.get("id") == did))
    facts.append(json.dumps(raw.get("settings") or {}, sort_keys=True))
    val = hashlib.sha256("\n".join(facts).encode()).hexdigest()[:16]
    # Bounded, because the key is a display id and a register can be long.
    # Oldest out; the cost of a miss is one hash, not a fault.
    if len(_DISPLAYS_STAMP) > 200:
        _DISPLAYS_STAMP.clear()
    _DISPLAYS_STAMP[did or ""] = (key, val)
    return val


def config_gen(did=None):
    """A stamp that changes whenever anything a display renders from changes.

    The display keeps the value it booted with and reloads when it moves,
    which is how a route or an appearance edited during an outage reaches a
    screen nobody is standing at.

    Coarse on purpose. It cannot say WHAT changed and does not need to — the
    answer to all of them is the same reload."""
    parts = []
    for p in (ROUTES_PATH, SETTINGS_PATH, APP_PATH):
        try:
            parts.append(str(os.stat(p).st_mtime_ns))
        except OSError:
            parts.append("0")
    parts.append(_displays_stamp(did))
    return ".".join(parts)


def refresh_offset(did, stagger_minutes):
    """How many seconds after the refresh time THIS screen reloads.

    Derived from the display's id rather than rolled at random, so a screen
    keeps the same slot across reloads and restarts — twelve tablets spread
    over the window stay spread, instead of re-shuffling every night until two
    of them land on the same second anyway.

    Computed here rather than in the browser because the id is the one stable
    thing a display has, and it is deliberately not readable from page script:
    the cookie carrying it is HttpOnly."""
    try:
        span = int(stagger_minutes) * 60
    except (TypeError, ValueError):
        return 0
    if span <= 0:
        return 0
    return int(hashlib.sha256(str(did).encode()).hexdigest()[:8], 16) % span


def find_display(token):
    """The display this token belongs to, or None. Same shape as an embed key:
    the id addresses the record and the secret proves it, so a wrong token
    costs one hash rather than a scan."""
    did, _, secret = str(token or "").partition(".")
    if not did or not secret:
        return None
    rec = read_displays().get(did)
    if not rec or not rec.get("hash"):
        # A row that exists but holds no token: invited and not yet enrolled,
        # or one whose token was killed by a reissue. Neither is something a
        # cookie can be.
        return None
    try:
        ok = hmac.compare_digest(
            hash_key(secret, bytes.fromhex(rec["salt"]))[1], rec["hash"])
    except (KeyError, TypeError, ValueError):
        return None                              # a record edited by hand
    return dict(rec, id=did) if ok else None


def new_display(asked, hint):
    """Mint one, and hand back (token, record) — or (None, error).

    Nothing is approved here. A device that has just arrived is a row in a
    list, and it stays inert until somebody says otherwise."""
    cfg = display_settings()
    displays = read_displays()
    pending = sorted((d for d, r in displays.items() if not r["approved"]),
                     key=lambda d: displays[d]["created"])
    # The oldest unapproved goes first, and only ever an unapproved one: the
    # queue is a queue, and nothing arriving at the door may evict a display
    # somebody hung on a wall.
    while pending and (len(pending) >= cfg["max_pending"]
                       or len(displays) >= cfg["max_displays"]):
        displays.pop(pending.pop(0), None)
    if len(displays) >= cfg["max_displays"]:
        return None, ("that is %d displays already — remove one, or raise the "
                      "limit on the DISPLAYS tab" % cfg["max_displays"])
    did = "d" + secrets.token_hex(6)
    secret = secrets.token_urlsafe(32)
    salt, dk = hash_key(secret)
    rec = dict(DISPLAY_DEFAULTS)
    rec.update(origin="page", asked=asked, hint=hint, salt=salt, hash=dk,
               created=int(time.time()), last_seen=int(time.time()))
    displays[did] = rec
    write_displays(displays)
    return did + "." + secret, dict(rec, id=did)


def display_network(did, doc=None):
    """WHICH PORT A SCREEN BELONGS ON, derived rather than set.

    It was a field on the display row, chosen when the code was minted, and it
    was the second setting in this product called "network" — one on the screen
    and one on the endpoint, meaning different things. A row could say HA
    Display while every endpoint answered on Default, so the screen loaded, drew
    correctly, and answered to nothing: a port carries the endpoints that NAME
    it, and nothing a display says about itself changes that.

    So there is one setting now, on the endpoint, and this reads it back: the
    profile named by the endpoints this display is granted. Returns (nid, clash)
    — `clash` is the set of profiles when the grant spans more than one, which
    is a screen that cannot be loaded from a single address and is refused
    where it is made rather than discovered later."""
    doc = doc or read_routes()
    nids = {str(r.get("network") or "")
            for r in doc["routes"].values()
            if did in (r.get("displays") or [])}
    if len(nids) > 1:
        return "", nids
    return (nids.pop() if nids else ""), None


def display_network_clash(rids, doc=None):
    """The message for a grant that spans two ports, or "" where it does not.

    One screen is one address. Two endpoints on two ports cannot both be
    reached from it, so this is refused at the moment the ticks are made — the
    alternative is a code that works and an assistant that silently never
    answers, which is the failure this whole setting was renamed away from."""
    doc = doc or read_routes()
    seen = {str((doc["routes"].get(rid) or {}).get("network") or "")
            for rid in rids or []}
    if len(seen) < 2:
        return ""
    # His words, and short on purpose: the panel is not the place to teach the
    # port model, and the ticks that caused it are on screen above the message.
    return "Unable to use AI Assistants that run on different network ports"


def enrol_base_for(rec, host, secure, nid=""):
    """Where the code for this row is typed — an address and a port, because a
    code without them is six characters and no idea where to put them. The
    profile comes from display_network: what this screen was granted decides
    where it is loaded from."""
    if nid:
        prof = net_profile(nid)
        vals = (prof or {}).get("values") or {}
        try:
            port = int(vals.get("port"))
        except (TypeError, ValueError):
            port = 0
        if port:
            addr = str(vals.get("address") or "").strip() or host
            return "https://%s:%d/e/" % (addr, port)
    return "%s://%s:%d/e/" % ("https" if secure else "http", host,
                              secure or RUNNING.get("http_port") or 0)


def invite_display(name, by, setup=None):
    """A row created from the panel, before the device it is for has ever been
    switched on. It holds a code and NOTHING ELSE: no token, and not approved.

    It used to be approved from the moment it existed, on the reasoning that an
    admin naming a screen and ticking its endpoints IS the approval. That reads
    well and it is wrong in the one place it matters — the row then sits
    `approved` with no device behind it, so anything asking "is this a display
    that works" is told yes about a television nobody has switched on. It gets
    offered as a member of a group, and it would be counted as a grant that had
    landed. Enrolment is what completes it, so enrolment is what approves it:
    see redeem_code."""
    displays = read_displays()
    limit = display_settings()["max_displays"]
    if len(displays) >= limit:
        return None, ("that is %d displays already — remove one, or raise the "
                      "limit on the DISPLAYS tab" % limit)
    did = "d" + secrets.token_hex(6)
    now_ = int(time.time())
    rec = dict(DISPLAY_DEFAULTS)
    # `approved_by` is who INVITED it, recorded now because that is when it is
    # known; `approved_at` waits for the moment it is true.
    rec.update(name=name, approved=False, approved_by=by, approved_at=0,
               created=now_, code=new_code(), code_expires=code_deadline(now_),
               origin="code")
    # What the admin already knows about the screen, set while creating it
    # rather than found and filled in afterwards on a row among fifty.
    if isinstance(setup, dict):
        rec["kiosk"] = bool(setup.get("kiosk"))
        rec["kiosk_profile"] = str(setup.get("kiosk_profile") or "")[:16]
        # `network` is NOT set here any more. Where a screen is loaded from is
        # derived from the endpoints it is granted — see display_network.
    displays[did] = rec
    write_displays(displays)
    return dict(rec, id=did), None


def reissue_display(did):
    """A new code for a row that already exists — a browser wiped its data, a
    screen replaced in the same place, a television swapped for a bigger one.

    The row is the PLACE. Its name survives, and so does every endpoint that
    names it, so nothing has to be ticked again.

    The live token dies HERE, not when the new code is used. A place is one
    device; the moment you decide to move it, the old one stops being that
    place. Leaving it working until somebody got round to typing the code would
    mean two devices holding one place for as long as that took."""
    displays = read_displays()
    rec = displays.get(did)
    if not rec:
        return None, "no such display"
    now_ = int(time.time())
    # Back to an invitation: no token, and not approved until the new code is
    # used. The row is the place and keeps its name and its grants, but it is
    # not a working display again until a device is behind it.
    rec.update(salt="", hash="", approved=False, approved_at=0,
               code=new_code(), code_expires=code_deadline(now_))
    write_displays(displays)
    return dict(rec, id=did), None


def code_deadline(now_):
    """When a code minted now stops working, or 0 for never.

    Zero rather than a far-future stamp, so "never" is a state the panel can
    read rather than a number it has to recognise as absurd — and it is the
    same convention `expires` already uses for a grant that does not run out."""
    mins = display_settings()["code_minutes"]
    return now_ + mins * 60 if mins else 0


def redeem_code(raw):
    """Somebody typed the code into the screen. Returns (token, record), or
    (None, reason) where the reason is one of `expired` or `unknown` — which
    the display turns into words, because a code typed on a television with a
    remote is mistyped often enough that "no" is not a useful answer."""
    code = norm_code(raw)
    if len(code) != CODE_LEN:
        return None, "unknown"
    displays = read_displays()
    now_ = int(time.time())
    for did, rec in displays.items():
        if not rec.get("code") or not hmac.compare_digest(rec["code"], code):
            continue
        # Zero is never — a deployment that turned the clock off. Anything
        # else is a deadline.
        deadline = rec.get("code_expires") or 0
        if deadline and deadline < now_:
            return None, "expired"
        secret = secrets.token_urlsafe(32)
        salt, dk = hash_key(secret)
        # Spent. The code is gone from the record before the token exists
        # anywhere else, so the same six characters cannot enrol a second
        # device however quickly somebody types them.
        # Approved HERE, because this is the moment the row becomes a device.
        # Before it, the code was an invitation nobody had taken up.
        rec.update(salt=salt, hash=dk, code="", code_expires=0,
                   last_seen=now_, approved=True, approved_at=now_)
        write_displays(displays)
        return did + "." + secret, dict(rec, id=did)
    return None, "unknown"


def note_display_seen(did, asked=None, hint=None):
    """Last seen, written at most once every few minutes. A display asks and
    answers all day; a file write per utterance would be a lot of disk for a
    column nobody reads to the second."""
    displays = read_displays()
    rec = displays.get(did)
    if not rec:
        return
    now_ = int(time.time())
    fresh = now_ - (rec.get("last_seen") or 0) < SEEN_INTERVAL
    # A display that has started declaring a different name is worth writing
    # immediately: it is the one change in this record that somebody might have
    # to explain, and it is what the panel shows beside the name.
    if fresh and (asked is None or asked == rec.get("asked")) \
            and (hint is None or hint == rec.get("hint")):
        return
    rec["last_seen"] = now_
    if asked is not None:
        rec["asked"] = asked
    if hint is not None:
        rec["hint"] = hint
    write_displays(displays)


def note_display_refused(disp, route_name):
    rec = _display_refusals.setdefault(disp["id"] if disp else "(no token)",
                                       [0, 0, ""])
    rec[0] += 1
    rec[1] = int(time.time())
    rec[2] = route_name


def display_expired(disp):
    """Guest access runs out. An admin-issued display's `expires` is zero and
    never does — see the field."""
    e = (disp or {}).get("expires") or 0
    return bool(e) and e < time.time()


def is_guest(rec):
    """A row that asked to be here, as opposed to one an admin created and sent
    a code for. Only the first kind expires."""
    return bool(rec.get("requested_at"))


def request_access(did, answers):
    """A device putting its hand up. Runs against the row it already has, so a
    second ask is a RENEWAL of one row rather than a second device — what
    somebody typed the first time survives, and how often they have asked is
    visible to whoever decides."""
    displays = read_displays()
    rec = displays.get(did)
    if not rec:
        return None, "no such display"
    if rec.get("denied") and not rec.get("deny_repeat", True):
        return None, "this device was refused, and may not ask again"
    if rec.get("approved") and not display_expired(rec):
        # It already has what it would be asking for. Refused rather than
        # accepted quietly, because accepting would take its access away and
        # put it back at the end of a queue for no reason anybody chose.
        return None, "this device already has access"
    rec["requested_at"] = int(time.time())
    # Asking puts the row back in front of somebody, which means it is no
    # longer granted anything: an expired grant that still read `approved`
    # showed in the panel as "access expired" when what had actually just
    # happened was that they asked again. Waiting on a decision is a state of
    # its own and has to look like one, at both ends.
    rec["approved"] = False
    rec["expires"] = 0
    # The refusal comes off the row's face — it is being asked again — but the
    # reason and the internal note stay as history, because whoever decides
    # this time is better off knowing it was turned down before and why.
    rec["denied"] = False
    if answers is not None:
        rec["answers"] = answers
    write_displays(displays)
    # The one alert with a PERSON attached: somebody is standing at a screen
    # waiting to be let in. It depends on nothing this phase collects, and it
    # is why it arrives immediately rather than in a digest.
    raise_alert("asked_in", did, display_label(rec))
    return dict(rec, id=did), None


def set_identity_endpoints(pid, rids):
    """Which endpoints this PERSON may use. The identity half of
    set_display_endpoints, and deliberately its twin: added where it is named,
    removed everywhere else, allow-lists only.

    It exists because approving a request now creates a person rather than a
    device, and the ticks beside APPROVE have to land somewhere. Sending them
    to the display half would have written the browser's id into a list that
    is read for people — a grant that looks made and reaches nobody."""
    doc = read_routes()
    want = set(rids or [])
    changed = False
    for rid, rec in doc["routes"].items():
        has = pid in (rec.get("identities") or [])
        if rid in want and not has:
            rec["identities"] = list(rec.get("identities") or []) + [pid]
            changed = True
        elif rid not in want and has:
            rec["identities"] = [p for p in rec["identities"] if p != pid]
            changed = True
    if changed:
        write_routes(doc)


def set_display_endpoints(did, rids):
    """Which endpoints this display may use, as one gesture: added where it is
    named, removed everywhere else. The ticks are the whole truth rather than
    an addition to something invisible.

    Only ever the allow-lists. Naming an endpoint that is open to any display
    does not restrict it — that would lock everybody else out as a side effect
    of granting one person access, which is the opposite of what was asked."""
    doc = read_routes()
    want = set(rids or [])
    changed = False
    for rid, rec in doc["routes"].items():
        has = did in (rec.get("displays") or [])
        if rid in want and not has:
            rec["displays"] = list(rec.get("displays") or []) + [did]
            changed = True
        elif rid not in want and has:
            rec["displays"] = [d for d in rec["displays"] if d != did]
            changed = True
    if changed:
        write_routes(doc)
    return changed


def open_default(doc):
    """The endpoint a device with no grant of any kind reaches: the default, if
    it is answering and open to any display. Blank means a guest has nowhere to
    go — fine while they can ask for access, and a server that answers nobody
    the moment they cannot."""
    rid = doc.get("default")
    rec = doc["routes"].get(rid)
    return rid if rec and rec.get("enabled", True) and not rec.get("restricted") else ""


#: Said in both directions, because the rule has two ends: it refuses to switch
#: guest requests off with nothing open, and refuses to close the last open
#: default while they are off. Enforced only in one, it holds until the next
#: edit and then breaks silently — approval off, guests reaching nothing, and
#: no error anywhere to say why.
GUEST_PATH_MSG = ("guest requests are switched off, so the default endpoint is "
                  "the only thing an uninvited device can reach — it has to "
                  "stay answering and open to any display. Turn guest requests "
                  "back on under SECURITY \u25b8 AI Requires Permission "
                  "first, or make another endpoint the "
                  "default.")


def guest_path_broken(doc):
    """Whether this route document would leave a guest with nowhere to go.
    Asked of the RESULT of an edit rather than of the edit itself: the default
    moves on its own when one is switched off or deleted, so the only honest
    question is what the document says once the change has been applied."""
    return not display_settings()["guest_requests"] and not open_default(doc)


def subject_may(route, disp=None, ident=None):
    """May this caller use this endpoint?

    The caller is a DEVICE or a PERSON, never both — see `_subject`, which is
    where that is decided — so this takes one of the two and answers about it.
    A person's grant is their own and does not depend on what the machine they
    are sitting at was approved for; a device's is the machine's and owes
    nothing to whoever happens to be standing in front of it.

    An endpoint with no allow-list is reachable by anything that can reach the
    port, which is what every endpoint was before displays existed — so an
    upgrade changes nothing until somebody restricts one, and the restriction
    is a thing you can see rather than a default nobody was told about.

    Where there IS one: approval is the floor for a device. An unapproved one
    holding a freshly minted token is exactly the phone somebody typed the URL
    into. A person has no equivalent test, because an identity only exists at
    all if an admin made it — creation IS the approval, and there is no way to
    turn up asking to be one."""
    # THE PANEL'S PREVIEW, first of all. It is an admin looking at a display,
    # already signed in, and one that refused to demonstrate half the endpoints
    # would be lying in the other direction. Hoisted above the sign-in test for
    # that reason — it has no person on it either.
    if disp and disp.get("preview"):
        return True
    # MUST THERE BE A PERSON. Above the allow-list test, because it applies to
    # an endpoint that has no allow-list at all: "open to anyone who signs in"
    # is a real and useful thing to say, and checking this after the
    # unrestricted early-return would have made it unsayable.
    #
    # `ident` is only ever set for a browser holding a PROVED session — see
    # _identity — so a device is refused here whatever it was approved for.
    if route.get("needs_signin") and not ident:
        return False
    if not route.get("restricted"):
        return True
    if ident:
        # Named directly, or named by a group of people. Grants add up here
        # exactly as they do for a display, and only GROUPS OF PEOPLE count: a
        # group of screens on the same allow-list says nothing about who may
        # use this, and the two files mint ids independently.
        if ident["id"] in (route.get("identities") or []):
            return True
        return ident["id"] in group_members(route.get("groups"),
                                            kinds=IDENTITY_GROUP_KINDS)
    if not disp:
        return False
    # Expiry is checked here rather than at the door, which is what makes a
    # grant run out cleanly mid-conversation: the turn already in flight was
    # allowed when it started and finishes, and the next one is refused.
    if not disp.get("approved") or display_expired(disp):
        return False
    if disp["id"] in (route.get("displays") or []):
        return True
    # Grants add up: named directly, or named by a group it is in — and only
    # by a group of DISPLAYS. Both of those kinds hold display rows; the third
    # holds people, and a screen is not let through by a grant made to them.
    return disp["id"] in group_members(route.get("groups"),
                                       kinds=DISPLAY_GROUP_KINDS)


def admin_displays():
    """The list, less the credential. What a token IS never leaves this server
    — the panel shows the id, which says which device a row is about without
    being the thing that proves it."""
    out = []
    displays = read_displays()
    now_ = int(time.time())
    # WHICH ENDPOINTS EACH ROW IS ON, read once for the whole list. It lives on
    # the endpoint rather than on the display — an allow-list is a property of
    # the thing being protected — so a panel drawing a row had to have the
    # routes document to know, and the tabs that draw these rows never fetch
    # it. The grant was made, stored and invisible: ticks that could only ever
    # be empty on the one page that shows a device's settings.
    granted = {}
    for rid, rrec in read_routes()["routes"].items():
        for member in (rrec.get("displays") or []):
            granted.setdefault(member, []).append(rid)
    for did, rec in sorted(displays.items(), key=lambda kv: kv[1]["created"]):
        row = {k: rec.get(k) for k in
               ("name", "asked", "approved", "hint", "created", "last_seen",
                "approved_by", "approved_at", "answers", "requested_at",
                "expires", "renewals", "denied", "deny_reason", "deny_note",
                "deny_repeat")}
        # The row's own three fields, NOT the resolved numbers: the panel is
        # editing what this device names, and the numbers behind that name are
        # on the profile where they can be changed once for every screen.
        row.update({k: rec.get(k, DISPLAY_DEFAULTS[k]) for k in KIOSK_FIELDS})
        ref = _display_refusals.get(did)
        # A code with no deadline is live; one whose deadline has passed is
        # not. Both have to be tellable apart from "there is no code", which
        # is what the panel used to read a zero as.
        deadline = rec.get("code_expires") or 0
        live = bool(rec.get("code")) and (not deadline or deadline > now_)
        row.update(id=did, label=display_label(rec),
                   network=str(rec.get("network") or ""),
                   # Approved into an ACCOUNT rather than into a device. The
                   # live row for this person is on the identity list; this
                   # one is the browser they asked from and has nothing left
                   # to decide, so the panel drops it out of every queue.
                   converted=bool(rec.get("setup")),
                   guest=is_guest(rec), expired=display_expired(rec),
                   # What it was SET to, and what it resolves to. The panel
                   # needs both: one is the control's value, the other is the
                   # answer a blank control is currently getting.
                   kind=str(rec.get("kind") or ""), arrived=enrolled_as(rec),
                   # Three states, and the panel needs to tell them apart:
                   # INVITED is a row waiting for somebody to type its code
                   # into a screen, WAITING is a device that turned up on its
                   # own, and the rest are working.
                   enrolled=bool(rec.get("hash")),
                   code=rec["code"] if live else "",
                   code_left=max(0, deadline - now_) if live and deadline else 0,
                   code_forever=bool(live and not deadline),
                   refused=ref[0] if ref else 0,
                   refused_at=ref[1] if ref else 0,
                   refused_from=ref[2] if ref else "",
                   # Named as granted whether or not the endpoint is currently
                   # restricted: this says what is STORED about this row. What
                   # a grant is worth on an endpoint open to everybody is said
                   # beside the tick, in words, rather than by drawing it
                   # empty — a tick that goes back to unticked when you save is
                   # a control arguing with the file.
                   granted=granted.get(did, []))
        out.append(row)
    return out


# --------------------------------------------------------------- diagnostics
# TECHNICAL EVENTS, KEYED TO A DEVICE. The microphone would not open,
# transcription took four seconds, the voice service returned an error, this
# browser has no recorder at all. The useful key is the screen with the failing
# microphone, not whoever happened to be standing at it.
#
# Most of this is already computed and thrown away. The display says
# `woke on "hows" (near "house")` as a note that fades, and on a wall tablet
# nobody is ever there to read it. A good deal of this is "stop discarding
# that" plus somewhere to put it.
#
# ITS OWN FILE, and a small one. It is the only document here that grows on its
# own — everything else grows when an admin does something — so it is capped
# two ways: a hard ceiling on rows, and a window in days that an admin sets.
EVENTS_PATH = os.path.join(ROOT, "events.json")
_events_lock = threading.RLock()
#: The hard ceiling, and not a setting. It stops the file becoming a problem
#: of its own on a busy day; the WINDOW is the control an admin has, and it is
#: the one that decides what is kept rather than how much.
MAX_EVENTS = 2000
#: What a display may send in one poll. A screen with a broken microphone
#: generates the same event every second it tries, and the cap is what stops
#: one fault filling the store before anybody reads it.
MAX_EVENTS_PER_POLL = 12
#: Kinds this server will store. An ALLOW-list for the same reason the served
#: files are one: this is written by a browser, and a document shaped by
#: whatever a page decided to send is one nobody can reason about later.
EVENT_KINDS = (
    "mic_denied",        # the microphone would not open
    "no_recorder",       # this browser has no recorder at all — a fact, once
    "stt_slow",          # transcription took longer than it should
    "stt_error",         # the recogniser returned an error
    "tts_fallback",      # the neural voice fell back to the browser's
    "wake_fuzzy",        # woke on a near miss, and on which word
    "no_intent",         # the house was asked for something it cannot do
    "backend_error",     # what answers a route returned an error
    "backend_slow",      # …or took longer than that route allows for
)
#: Where an event came from. A display sends its own; the server records the
#: legs it can see, which a browser cannot.
EVENT_LEVELS = ("info", "warn", "error")


def read_events():
    try:
        with open(EVENTS_PATH) as fh:
            doc = json.load(fh)
        rows = doc.get("events") if isinstance(doc, dict) else None
    except (OSError, ValueError):
        return []
    if not isinstance(rows, list):
        return []
    out = []
    for r in rows:
        if isinstance(r, dict) and r.get("kind") in EVENT_KINDS:
            out.append(r)
    return out


def write_events(rows):
    with _events_lock:
        tmp = EVENTS_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"version": 1, "events": rows[-MAX_EVENTS:]}, fh)
        os.chmod(tmp, 0o600)          # it holds what was said to a display
        os.replace(tmp, EVENTS_PATH)


def event_window_days():
    return int(display_settings().get("event_days") or EVENT_DAYS_DEFAULT)


def note_event(kind, did="", level="info", detail="", route="", ms=0):
    """One event, kept. Silent about anything it does not recognise rather than
    refusing: this is called from the paths that ARE the fault being reported,
    and a diagnostic that raises inside a failure is a second fault on top of
    the first."""
    if kind not in EVENT_KINDS:
        return
    with _events_lock:
        rows = read_events()
        rows.append({"kind": kind, "did": str(did or "")[:32],
                     "level": level if level in EVENT_LEVELS else "info",
                     "detail": str(detail or "")[:300],
                     "route": str(route or "")[:60],
                     "ms": max(0, int(ms or 0)), "at": int(time.time())})
        write_events(rows)


def take_events(did, rows):
    """Events a display sent up with its poll. Returns how many were kept.

    Capped per poll, because a screen whose microphone is broken produces the
    same event every second it tries and one fault must not fill the store
    before anybody reads it. The device id comes from the TOKEN, never from the
    body: a display saying which display it is would be a display able to file
    a fault against another one."""
    if not isinstance(rows, list):
        return 0
    kept = 0
    with _events_lock:
        have = read_events()
        for r in rows[:MAX_EVENTS_PER_POLL]:
            if not isinstance(r, dict) or r.get("kind") not in EVENT_KINDS:
                continue
            have.append({"kind": r["kind"], "did": did,
                         "level": r.get("level") if r.get("level") in EVENT_LEVELS
                                  else "info",
                         "detail": str(r.get("detail") or "")[:300],
                         "route": str(r.get("route") or "")[:60],
                         "ms": max(0, min(600000, int(r.get("ms") or 0))),
                         "at": int(time.time())})
            kept += 1
        if kept:
            write_events(have)
    return kept


def display_health(did, rows=None, now_=None):
    """What this screen has been reporting, summarised. The list an admin
    reads is per device, because the useful question is which screen is
    failing rather than how many faults there were."""
    rows = read_events() if rows is None else rows
    now_ = int(time.time()) if now_ is None else now_
    mine = [r for r in rows if r.get("did") == did]
    by_kind = {}
    for r in mine:
        k = by_kind.setdefault(r["kind"], {"kind": r["kind"], "n": 0, "last": 0,
                                           "level": "info", "detail": ""})
        k["n"] += 1
        if r["at"] >= k["last"]:
            k["last"], k["level"], k["detail"] = r["at"], r["level"], r["detail"]
    worst = "info"
    for k in by_kind.values():
        if k["level"] == "error" or (k["level"] == "warn" and worst == "info"):
            worst = k["level"]
    return {"events": sorted(by_kind.values(), key=lambda k: -k["last"]),
            "n": len(mine), "worst": worst if mine else "",
            "last": max([r["at"] for r in mine], default=0)}


# THE CONVERSATION RECORD. This entry used to promise "no conversation
# content", and that boundary has moved — stated plainly rather than quietly
# broken, because a promise like that is worth only what it is kept to:
#
#   What was addressed to the device — from the wake word to the end of the
#   conversation — and the routing decision that followed, retained for a
#   window. Nothing outside an active conversation is recorded.
#
# The reasoning: a voice-only display shows nobody anything, so when it
# mishears there is no record at all and nothing to fix. And the captured text
# is exactly what already leaves the machine — it goes to a house or a model
# regardless — so this adds retention, not disclosure. Nothing is captured
# unless somebody said a wake word.
#
# THE WORDS ARE THE LEAST USEFUL PART. What makes a voice fault diagnosable is
# the decision trail beside them, and "it didn't work" resolves into: the
# recogniser heard "hows" and matched it fuzzily to the house route.
TURNS_PATH = os.path.join(ROOT, "turns.json")
_turns_lock = threading.RLock()
MAX_TURNS = 500


def read_turns():
    try:
        with open(TURNS_PATH) as fh:
            doc = json.load(fh)
        rows = doc.get("turns") if isinstance(doc, dict) else None
    except (OSError, ValueError):
        return []
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def write_turns(rows):
    with _turns_lock:
        tmp = TURNS_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"version": 1, "turns": rows[-MAX_TURNS:]}, fh)
        os.chmod(tmp, 0o600)          # it holds what was said to a display
        os.replace(tmp, TURNS_PATH)


def note_turn(did, route, heard, sent, reply, trail=None, ms=0, error="",
              fell_to=""):
    """One turn, with the trail that explains it. Only ever called where an
    utterance has already been decided to be this screen's business."""
    if not did:
        # A turn with no screen to attach it to is a turn nobody can act on,
        # and the embed is not a screen. Recording it would be collecting for
        # its own sake.
        return
    t = trail if isinstance(trail, dict) else {}
    with _turns_lock:
        rows = read_turns()
        rows.append({
            "did": str(did)[:32], "route": str(route or "")[:60],
            # BEFORE the wake word came off, which is the whole point: it is
            # the only field that can show a near miss.
            "heard": str(heard or "")[:400],
            "sent": str(sent or "")[:400],
            "reply": str(reply or "")[:400],
            "via": str(t.get("via") or "")[:12],
            "word": str(t.get("word") or "")[:40],
            "as": str(t.get("as") or "")[:40],
            "ms": max(0, int(ms or 0)), "error": str(error or "")[:300],
            "fell_to": str(fell_to or "")[:60],
            "at": int(time.time()),
        })
        write_turns(rows)


def prune_turns():
    cutoff = int(time.time()) - event_window_days() * 86400
    rows = read_turns()
    keep = [r for r in rows if int(r.get("at") or 0) >= cutoff]
    if len(keep) != len(rows):
        write_turns(keep)
    return len(rows) - len(keep)


def prune_events():
    """Past the window, gone. Read at startup and after each poll that wrote
    anything, which is often enough on a server that only grows this file when
    a display is talking to it."""
    cutoff = int(time.time()) - event_window_days() * 86400
    rows = read_events()
    keep = [r for r in rows if int(r.get("at") or 0) >= cutoff]
    if len(keep) != len(rows):
        write_events(keep)
    return len(rows) - len(keep)


# -------------------------------------------------------------------- alerts
# Diagnostics is a PULL — events collected, a health view somebody goes and
# looks at. An alert is a PUSH: it comes and finds you. Those are genuinely
# different things, and the only reason they are one entry is that building a
# health view and then separately building the thing that watches it is two
# passes over the same data.
#
# FOUR STATES, NOT TWO: open or resolved, acknowledged or not. The cell that
# matters is resolved-but-unacknowledged — a screen that dropped off at two in
# the morning and came back four minutes later leaves something in the list
# until a person reads it. Self-healing nobody ever hears about is
# indistinguishable from nothing having happened, and a display that heals
# itself every night is a fault rather than a success.
ALERTS_PATH = os.path.join(ROOT, "alerts.json")
_alerts_lock = threading.RLock()
MAX_ALERTS = 300

#: What can raise one, and what it means. `once` fires a single time per
#: device however often the fact is reported — no recorder in this browser
#: will be just as true tomorrow.
ALERT_KINDS = {
    "offline":      {"level": "error", "words": "has not checked in"},
    "still_gone":   {"level": "error", "words": "did not come back after a reload"},
    "mic_denied":   {"level": "error", "words": "its microphone was refused"},
    "no_recorder":  {"level": "error", "words": "has no recorder at all", "once": True},
    "stt_slow":     {"level": "warn",  "words": "transcription is running long"},
    "tts_fallback": {"level": "warn",  "words": "fell back to the browser voice"},
    "wake_fuzzy":   {"level": "warn",  "words": "is waking on near misses"},
    "no_intent":    {"level": "warn",  "words": "is being asked for what it cannot do"},
    "backend_error": {"level": "error", "words": "the assistant it uses is failing"},
    # The one that depends on none of the rest and could have shipped alone: a
    # device asking to be here is already recorded by the displays entry. It
    # arrives immediately rather than in a digest, because it is the only
    # alert with a person attached — somebody is standing at a screen waiting
    # to be let in.
    "asked_in":     {"level": "warn",  "words": "is asking to be let in",
                     "now": True},
}


#: The server's own log, as an admin reads it. NOT a served file — the whole
#: reason SERVABLE is an allow-list is that this used to be handed out by the
#: base class, unauthenticated, on every interface. This reads a bounded tail
#: through the admin listener, behind the same session as everything else.
LOG_PATH = os.path.join(ROOT, "server.log")
#: Bytes read from the end. Enough to cover a start and a busy hour after it,
#: small enough that asking for it is never the thing that makes a server slow.
#: This one is NOT a setting: it bounds what this process reads off a disk,
#: which is a property of the machine rather than a preference, and a field
#: that could be set to a gigabyte would be a field that stalls the panel.
LOG_TAIL_BYTES = 256 * 1024
#: How many of those lines are answered with, when nothing is configured. The
#: live number is app.json's `log_lines`; this is its default and its floor if
#: the file says something impossible.
LOG_MAX_LINES = 800


def log_max_lines():
    """The configured tail length, or the default if it is unreadable.

    Clamped to the same pair the panel's save is clamped to, and read from that
    pair rather than from a second copy of the numbers: what arrives through
    the panel cannot be out of range, but app.json is a file on a disk and
    somebody editing it by hand is exactly who would put a million in it."""
    lo, hi = UNATTENDED_LIMITS["log_lines"]
    try:
        return min(hi, max(lo, int(read_app().get("log_lines", LOG_MAX_LINES))))
    except (TypeError, ValueError):
        return LOG_MAX_LINES


def read_log_tail(match=""):
    """The end of the log, newest last. Returns (lines, truncated, size).

    Seeks rather than reads: this file is truncated at every start but a busy
    day still puts megabytes in it, and reading the whole thing to show the
    last screenful is the kind of thing that works until the day it matters."""
    try:
        size = os.path.getsize(LOG_PATH)
        with open(LOG_PATH, "rb") as fh:
            if size > LOG_TAIL_BYTES:
                fh.seek(size - LOG_TAIL_BYTES)
                fh.readline()                # drop the half line seeking landed in
            raw = fh.read()
    except OSError:
        return [], False, 0
    lines = raw.decode("utf-8", "replace").splitlines()
    if match:
        m = match.lower()
        lines = [ln for ln in lines if m in ln.lower()]
    keep = log_max_lines()
    cut = len(lines) > keep
    return lines[-keep:], cut, size


def read_alerts():
    try:
        with open(ALERTS_PATH) as fh:
            doc = json.load(fh)
        rows = doc.get("alerts") if isinstance(doc, dict) else None
    except (OSError, ValueError):
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("kind") in ALERT_KINDS] \
        if isinstance(rows, list) else []


def write_alerts(rows):
    with _alerts_lock:
        tmp = ALERTS_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"version": 1, "alerts": rows[-MAX_ALERTS:]}, fh)
        os.chmod(tmp, 0o600)
        os.replace(tmp, ALERTS_PATH)


def raise_alert(kind, did="", detail=""):
    """Open one, or touch the one already open.

    An alert has an IDENTITY — its kind and its device — rather than being a
    row appended per occurrence. A screen offline for a day is one alert that
    has been true for a day, not two hundred and forty of them, and a list that
    said otherwise would be a list nobody reads to the bottom of."""
    spec = ALERT_KINDS.get(kind)
    if not spec:
        return None
    now_ = int(time.time())
    with _alerts_lock:
        rows = read_alerts()
        for r in rows:
            if r["kind"] == kind and r["did"] == did and not r["resolved"]:
                r["last"], r["n"] = now_, r.get("n", 1) + 1
                if detail:
                    r["detail"] = str(detail)[:300]
                write_alerts(rows)
                return r
            # A fact fires once per device, ever — even after somebody has
            # acknowledged and it has been resolved.
            if spec.get("once") and r["kind"] == kind and r["did"] == did:
                return None
        row = {"id": "a" + secrets.token_hex(5), "kind": kind, "did": did,
               "level": spec["level"], "detail": str(detail or "")[:300],
               "opened": now_, "last": now_, "n": 1,
               "resolved": 0, "acked": 0, "sent": 0}
        rows.append(row)
        write_alerts(rows)
        print("ALERT %s %s%s" % (kind, did or "(server)",
                                 ": " + detail if detail else ""), flush=True)
    # Outside the lock: a sink is a network call, and holding the alert file
    # while one of them times out would stop every other alert being written.
    if deliver_alert(row):
        mark_sent([row["id"]])
    return row


def clear_alert(kind, did=""):
    """It stopped being true. RESOLVED, not gone: it stays in the list until
    somebody has read it, because a fault that healed itself unobserved is
    indistinguishable from one that never happened."""
    now_ = int(time.time())
    with _alerts_lock:
        rows, hit = read_alerts(), False
        for r in rows:
            if r["kind"] == kind and r["did"] == did and not r["resolved"]:
                r["resolved"], hit = now_, True
        if hit:
            write_alerts(rows)
            print("alert cleared: %s %s" % (kind, did or "(server)"), flush=True)
    if hit:
        # Recovery is news too. A screen that came back at four in the morning
        # is exactly what somebody reading a log at nine wants to see beside
        # the line saying it went.
        for r in rows:
            if r["kind"] == kind and r["did"] == did and r["resolved"] == now_:
                deliver_alert(r, resolved=True)
                break
    return hit


# ------------------------------------------------------------- alert sinks
# CHEAPEST REACH FIRST. The admin list is the baseline and is not optional,
# because acknowledgement has to live somewhere. Syslog is the next cheapest by
# a distance: the standard library speaks it, every operator already has
# somewhere it goes, and it costs one socket and no credentials — which is more
# than can be said for anything else on this list.
#
# It is FIRE AND FORGET on purpose. A sink that raises, retries or blocks would
# make reporting a fault into a second fault, and the alert it failed to send
# is still sitting in the panel where acknowledgement lives.
SYSLOG_FACILITIES = ("user", "local0", "local1", "local2", "local3",
                     "local4", "local5", "local6", "local7")
#: alert level -> syslog severity, by name rather than number so the mapping is
#: readable where it is decided rather than in a table somewhere else.
SYSLOG_SEVERITY = {"error": 3, "warn": 4, "info": 6}   # err, warning, info


def syslog_send(level, text):
    """One line, to wherever an admin pointed it. Silent on every failure: this
    is called from the path that IS the fault being reported."""
    cfg = display_settings()
    if not cfg.get("syslog_on"):
        return
    host = str(cfg.get("syslog_host") or "").strip()
    try:
        fac = SYSLOG_FACILITIES.index(cfg.get("syslog_facility") or "user")
        fac = 1 if fac == 0 else 15 + fac        # user=1, local0..7 = 16..23
        pri = fac * 8 + SYSLOG_SEVERITY.get(level, 6)
        line = "<%d>resonance: %s" % (pri, str(text)[:900])
        if host:
            port = int(cfg.get("syslog_port") or 514)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.settimeout(1.0)
                sock.sendto(line.encode("utf-8", "replace"), (host, port))
            finally:
                sock.close()
        else:
            # The local daemon. Two names because they differ by platform and
            # trying both is cheaper than asking which one this is.
            for path in ("/dev/log", "/var/run/syslog"):
                if not os.path.exists(path):
                    continue
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                try:
                    sock.connect(path)
                    sock.send(line.encode("utf-8", "replace"))
                    return
                except OSError:
                    continue
                finally:
                    sock.close()
    except Exception:                            # noqa: BLE001
        pass


def in_quiet_hours(now_=None):
    """Whether the house is asleep, on the DEVICE clock — the same clock dark
    hours already run on, and for the same reason. Announcing a dead hallway
    screen through the house speakers at three in the morning is how alerting
    gets switched off in its first week.

    Spans midnight, because that is the only shape anybody ever sets: 22 to 7
    is a night, and read as a plain range it would be nineteen hours of
    daylight and no quiet at all."""
    cfg = display_settings()
    if not cfg.get("quiet_on"):
        return False
    # `or` would be wrong here and was: midnight is 0, which is falsy, so a
    # night set to start at 00 silently became 22 — the one hour a quiet
    # period is most likely to involve, quietly replaced by a default.
    def _hour(key, fallback):
        try:
            return int(cfg[key]) % 24
        except (KeyError, TypeError, ValueError):
            return fallback
    start, end = _hour("quiet_from", 22), _hour("quiet_to", 7)
    hour = time.localtime(now_ or time.time()).tm_hour
    if start == end:
        return False                       # a zero-length night is no night
    # Inclusive of the start hour, exclusive of the end, both ways round.
    # They disagreed once: the wrapping branch counted 22:30 as quiet for a
    # night starting at 22 while the plain one did not count 09:30 as quiet for
    # one starting at 09 — the same setting meaning two things.
    return start <= hour < end if start < end else (hour >= start or hour < end)


def post_home_assistant(text, level, row):
    """Announced by the building the screen is part of.

    One service call, and which service is the deployment's business:
    persistent_notification.create needs nothing configured and always exists,
    notify.notify or a tts service is the one that actually speaks. Both take
    a title and a message, so one body serves either."""
    cfg = display_settings()
    base = str(cfg.get("ha_url") or "").strip()
    token = str(cfg.get("ha_token") or "").strip()
    if not (cfg.get("ha_on") and base and token):
        return
    svc = str(cfg.get("ha_service") or "persistent_notification/create").strip()
    svc = svc.replace(".", "/").strip("/")
    try:
        _post_json(ha_url(base, "/api/services/" + svc),
                   {"title": "Resonance", "message": text},
                   {"Authorization": "Bearer " + token}, 5)
    except Exception as exc:                     # noqa: BLE001
        print("home assistant alert failed: %s" % exc, flush=True)


def send_mail(subject, body):
    """One message, or nothing. Costs no dependency and is still last on the
    list: it wants a server and credentials, and when it fails it usually
    fails somewhere this process cannot see."""
    cfg = display_settings()
    host = str(cfg.get("mail_host") or "").strip()
    to = [a.strip() for a in str(cfg.get("mail_to") or "").split(",") if a.strip()]
    if not (cfg.get("mail_on") and host and to):
        return
    frm = str(cfg.get("mail_from") or "").strip() or "resonance@localhost"
    try:
        import smtplib
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["Subject"] = subject[:200]
        msg["From"] = frm
        msg["To"] = ", ".join(to)
        msg.set_content(body)
        port = int(cfg.get("mail_port") or 587)
        with smtplib.SMTP(host, port, timeout=10) as sm:
            if cfg.get("mail_tls"):
                sm.starttls()
            user = str(cfg.get("mail_user") or "").strip()
            if user:
                sm.login(user, str(cfg.get("mail_pass") or ""))
            sm.send_message(msg)
    except Exception as exc:                     # noqa: BLE001
        print("mail failed: %s" % exc, flush=True)


def post_webhook(text, level, row):
    """One JSON POST. Reaches ntfy, Slack, Discord, Gotify and whatever else
    somebody already runs — the most reach per line of code available here,
    because they all accept a body with a message in it."""
    cfg = display_settings()
    url = str(cfg.get("hook_url") or "").strip()
    if not cfg.get("hook_on") or not url:
        return
    try:
        _post_json(url, {"text": text, "message": text, "content": text,
                         "title": "Resonance",
                         "level": level, "kind": row.get("kind"),
                         "device": row.get("did") or "",
                         "at": row.get("last") or int(time.time())},
                   {}, 5)
    except Exception as exc:                     # noqa: BLE001
        # Said once, in the log, and never retried. A sink that retried would
        # be a fault reporting a fault.
        print("webhook failed: %s" % exc, flush=True)


def deliver_alert(row, resolved=False):
    """Out to every sink that is switched on. The list is not one of them: it
    already has the row, which is how it can be the thing that is never
    missed."""
    displays = read_displays()
    who = display_label(displays[row["did"]]) if row.get("did") in displays \
        else (row.get("did") or "this server")
    spec = ALERT_KINDS.get(row["kind"]) or {}
    level = "info" if resolved else row.get("level", "info")
    text = "%s %s%s%s" % (who, spec.get("words", row["kind"]),
                          " — RESOLVED" if resolved else "",
                          (": " + row["detail"]) if row.get("detail") else "")
    # SYSLOG IGNORES QUIET HOURS. It is a file somebody reads later, not a
    # thing that makes a noise in a house at three in the morning — and a log
    # with a hole in it every night is worse than useless for the one fault
    # that only ever happens at night.
    syslog_send(level, text)
    # HELD, NOT DROPPED — and this is where the difference is made real. Quiet
    # hours and digest mode both leave the row unsent; flush_digest carries it
    # at a civilised hour, or on the timer. The exception is the alert with a
    # person standing at a screen: they are waiting now, whatever time it is.
    cfg = display_settings()
    if not spec.get("now") and (in_quiet_hours() or cfg.get("digest_on")):
        return False
    post_webhook(text, level, row)
    post_home_assistant(text, level, row)
    send_mail("Resonance: " + text[:120], text)
    return True


#: How many missed polls before a screen is called gone. Three rather than one:
#: a single dropped poll is a network hiccup, and an alert that fires on one is
#: an alert somebody turns off in a week.
ALERT_MISSES = 3
#: How many of a thing inside the window before it is worth telling somebody.
#: A near miss now and then is how speech works; a rate of them is two wake
#: words cross-triggering.
ALERT_RATES = {"stt_slow": 5, "tts_fallback": 3, "wake_fuzzy": 5,
               "no_intent": 5, "backend_error": 3}
#: The window those rates are counted over.
ALERT_WINDOW = 3600


def evaluate_alerts():
    """Everything worth a threshold, judged from what is already collected.

    Called from the poll, which is the only clock this server has that a
    display keeps wound — and the poll is also the fact that liveness is read
    from, so the thing being measured and the thing doing the measuring arrive
    together."""
    now_ = int(time.time())
    app = read_app()
    every = int(app.get("poll_seconds") or APP_DEFAULTS["poll_seconds"])
    gone_after = every * ALERT_MISSES
    displays = read_displays()

    for did, rec in displays.items():
        # Only screens that ever worked. An invited row that has never taken
        # its code is not a screen that has gone quiet; it is a screen that was
        # never switched on, and it is already visible as one.
        if not (rec.get("approved") and rec.get("hash")):
            continue
        seen = int(rec.get("last_seen") or 0)
        if seen and now_ - seen > gone_after:
            raise_alert("offline", did,
                        "last seen %d seconds ago" % (now_ - seen))
        else:
            # RETURNED. Resolving is what makes the resolved-but-unread cell
            # exist, which is the one that matters: a screen that dropped at
            # two in the morning and came back leaves something to read.
            clear_alert("offline", did)

    rows = [r for r in read_events() if r["at"] >= now_ - ALERT_WINDOW]
    counts = {}
    for r in rows:
        counts[(r["kind"], r["did"])] = counts.get((r["kind"], r["did"]), 0) + 1
    for (kind, did), n in counts.items():
        if kind in ("mic_denied", "no_recorder"):
            # Hard faults, not rates. One is enough: a microphone that will not
            # open is not a thing that gets better by happening less often.
            raise_alert(kind, did, "reported %d time(s) in the last hour" % n)
        elif kind in ALERT_RATES and n >= ALERT_RATES[kind]:
            raise_alert(kind, did, "%d in the last hour" % n)
    # …and the ones that stopped happening.
    for kind in list(ALERT_RATES) + ["mic_denied"]:
        for did in displays:
            if counts.get((kind, did), 0) == 0:
                clear_alert(kind, did)


def mark_sent(ids):
    with _alerts_lock:
        rows = read_alerts()
        now_ = int(time.time())
        hit = False
        for r in rows:
            if r["id"] in ids and not r.get("sent"):
                r["sent"], hit = now_, True
        if hit:
            write_alerts(rows)


def flush_digest(force=False):
    """Everything held, in one message.

    This is what makes quiet hours a HOLD rather than a drop, and what digest
    mode is. Nothing goes out during the quiet: the whole point is that the
    house is asleep, and a digest that fired at three would be the thing it
    exists to prevent."""
    cfg = display_settings()
    if in_quiet_hours():
        return 0
    waiting = [r for r in read_alerts() if not r.get("sent")]
    if not waiting:
        return 0
    if not force:
        every = max(5, int(cfg.get("digest_minutes") or 60)) * 60
        oldest = min(r["last"] for r in waiting)
        # Counted from the OLDEST held thing rather than from the last digest:
        # what matters is how long something has gone unsaid, not how long it
        # has been since a message that may have carried nothing.
        if int(time.time()) - oldest < every:
            return 0
    displays = read_displays()
    lines = []
    for r in sorted(waiting, key=lambda r: r["last"]):
        spec = ALERT_KINDS.get(r["kind"]) or {}
        who = display_label(displays[r["did"]]) if r.get("did") in displays \
            else (r.get("did") or "this server")
        lines.append("%s %s%s%s" % (who, spec.get("words", r["kind"]),
                                    " — RESOLVED" if r["resolved"] else "",
                                    (": " + r["detail"]) if r.get("detail") else ""))
    text = "%d thing%s to report:\n" % (len(lines), "" if len(lines) == 1 else "s")
    text += "\n".join("  · " + ln for ln in lines)
    worst = "error" if any(r["level"] == "error" for r in waiting) else "warn"
    post_webhook(text, worst, waiting[0])
    post_home_assistant(text, worst, waiting[0])
    send_mail("Resonance: %d thing%s to report"
              % (len(lines), "" if len(lines) == 1 else "s"), text)
    mark_sent([r["id"] for r in waiting])
    print("digest sent: %d alert(s)" % len(waiting), flush=True)
    return len(waiting)


def ack_alerts(ids):
    """Read by a person. An alert that is both resolved and acknowledged has
    nothing left to say, so it leaves — everything else stays visible."""
    now_ = int(time.time())
    with _alerts_lock:
        rows = read_alerts()
        for r in rows:
            if r["id"] in ids and not r["acked"]:
                r["acked"] = now_
        keep = [r for r in rows if not (r["resolved"] and r["acked"])]
        write_alerts(keep)
        return len(rows) - len(keep)


# ---------------------------------------------------------------- identities
# A PERSON, as distinct from a place. A display is one physical object standing
# in one room; an identity is somebody who moves between a phone, a laptop and
# a borrowed browser and is the same person in all three.
#
# A SESSION IS A USER OR A DEVICE, NEVER BOTH, and the URL decides which. A
# device added as a device operates as a device — a kiosk, a wall tablet — and
# no person exists inside that session. An identity's URL travels, and the
# machine it was opened on contributes nothing to what that session may reach.
# They are separate namespaces for that reason: a place is named by ?display=
# and a person by a minted path, and neither can be spelled in the other's
# notation. One parameter holding either kind would hang everything a place
# owns — appearance, kiosk mode, route bindings, session length — off a person,
# who has no place to hang any of it on.
#
# CREATED IN THE PANEL AND NOWHERE ELSE. No email, no verification and nothing
# here to vouch for a name, so anybody who could mint their own identity could
# mint somebody else's.
#
# THE URL CARRIES A MINTED SECRET rather than a readable name. A name is
# guessable, and a guessable URL that grants reach is a password written on a
# wall — the same fault that made display tokens necessary, arriving through
# the front door. The first visit exchanges it for a cookie, so the secret
# leaves the address bar after one use and a shoulder-read of somebody's
# browser history is spent rather than live.
IDENTITIES_PATH = os.path.join(ROOT, "identities.json")
_identities_lock = threading.Lock()
IDENTITY_COOKIE = "rsn_pid"
#: The same ten years a display gets, for the same reason: an identity is
#: issued once and then somebody just uses it, and an expiring one would lock
#: somebody out for a reason they could not see. Revocation is deleting the
#: record or reissuing the URL, and both are immediate.
IDENTITY_MAX_AGE = DISPLAY_MAX_AGE
#: A ceiling rather than a setting. It bounds a list an admin fills in by hand
#: and nobody creates five thousand people one at a time; if a deployment ever
#: needs this to scale it belongs beside max_displays, where the numbers that
#: DO scale with the deployment already live.
MAX_IDENTITIES = 500

IDENTITY_DEFAULTS = {
    "name": "",                  # what an admin called them
    # The URL secret, hashed the way a display token is: the id addresses the
    # record and the secret proves it, so a wrong URL costs one hash rather
    # than a scan of everybody in the building. SHA-256 rather than the PBKDF2
    # the passwords get, because this secret is 32 bytes from the system
    # generator and there is no dictionary to run against it.
    "salt": "", "hash": "",
    "created": 0, "last_seen": 0,
    "created_by": "",
    # THE LOGIN. An email address, because it is the one handle a person
    # already has that is unique without anybody administering a namespace,
    # and because it is somewhere to send a fresh setup link the day they
    # forget the password. It is what they type to sign in; `name` stays what
    # the panel calls their row.
    "email": "",
    # THE PASSWORD. PBKDF2, and chosen by THEM: the setup link is spent
    # forcing one, and an admin never sets or sees it. This replaced a PIN,
    # which was six digits keyed into a screen — fine for a lock on a browser
    # that had already proved who it was, and not what a credential typed on a
    # login page can be.
    "pw_salt": "", "pw_hash": "", "pw_set_at": 0,
    # PER-IDENTITY SETTINGS: the tier signing in unlocks, and the one this
    # server did not have. There was shared configuration, a per-browser
    # preference and a per-embed grant; a setting belonging to a PERSON had
    # nowhere to live, so it lived in whichever browser they happened to be
    # using and did not follow them anywhere.
    "settings": {},
    # THEIR OWN WAKE WORD. Two people in a room with their own devices, one of
    # them says the name that reaches the model, and both answer — route
    # binding cannot help, because both are legitimately allowed that route.
    # A word of their own stops the collision happening rather than
    # reconciling it afterwards, and it is what people expect anyway: an
    # assistant answers to a name you chose.
    "wakeword": "",
    # How long a sign-in lasts on this person's own device, in hours. Theirs
    # rather than the deployment's: a password is entered at a login page, not
    # at a screen standing in a room, so there is no place carrying the risk to
    # set it from. Zero takes the deployment default.
    "session_hours": 0,
}

#: What a person is allowed to keep. An ALLOW-list, not a filter: this store is
#: written from a browser, and a document shaped by whatever a page decided to
#: send is one nobody can reason about a year from now. These three are exactly
#: what the display has always kept per browser — push-to-talk, muted, and
#: whether the transcript is showing.
IDENTITY_PREF_KEYS = ("ptt", "muted", "text")
#: Hours, where an identity names none. Long enough that somebody is not asked
#: again in a working day, short enough to matter on a machine they borrowed.
SESSION_HOURS_DEFAULT = 12
SESSION_HOURS_LIMITS = (1, 720)
#: A browser that has SIGNED IN. Its own cookie, separate from the identity
#: cookie: that one says which person this browser claims to be and is set by
#: the setup link, this one says the claim has been proved with a password.
#: Signing in on the laptop must not sign in the phone. In memory, like the
#: admin sessions: a restart asks again, and that is the same bargain the rest
#: of this server makes.
_user_sessions = {}              # token -> {"pid": str, "expires": float}
_user_lock = threading.Lock()
USER_COOKIE = "rsn_user"


def clean_identity_settings(obj):
    """Only the keys that exist, only as booleans. Everything a person may keep
    today is a switch; the day one is not, this is where that is decided rather
    than wherever the page happened to send it."""
    out = {}
    if isinstance(obj, dict):
        for k in IDENTITY_PREF_KEYS:
            if k in obj:
                out[k] = bool(obj[k])
    return out


def identity_settings(pid):
    rec = read_identities().get(pid)
    return clean_identity_settings((rec or {}).get("settings"))


def write_identity_settings(pid, obj):
    rows = read_identities()
    if pid not in rows:
        return None
    rows[pid]["settings"] = clean_identity_settings(obj)
    write_identities(rows)
    return rows[pid]["settings"]


def identity_hours(rec):
    h = int(rec.get("session_hours") or 0)
    return h if h > 0 else SESSION_HOURS_DEFAULT


def open_user_session(pid, hours):
    token = secrets.token_urlsafe(32)
    with _user_lock:
        # Swept here rather than on a timer: this runs when somebody signs in,
        # which is the only moment the map grows.
        now_ = time.time()
        for t in [t for t, v in _user_sessions.items() if v["expires"] <= now_]:
            _user_sessions.pop(t, None)
        _user_sessions[token] = {"pid": pid, "expires": now_ + hours * 3600}
    return token


def user_session_pid(token):
    """Which person this browser has signed in as, or "". Expiry is read HERE
    rather than swept on a clock, so a session that has run out is over the
    moment it is asked about rather than whenever a timer next fired."""
    rec = _user_sessions.get(str(token or ""))
    if not rec:
        return ""
    if rec["expires"] <= time.time():
        _user_sessions.pop(str(token), None)
        return ""
    return rec["pid"]


def close_user_sessions(pid):
    """Every signed-in browser for one person, ended. Called where their
    password changes hands — them setting a new one, or an admin reissuing the
    setup link — because a session opened by a credential that no longer
    exists is a door left open behind a lock somebody just changed."""
    with _user_lock:
        for t in [t for t, v in _user_sessions.items() if v["pid"] == pid]:
            _user_sessions.pop(t, None)

#: Guessing is per ACCOUNT rather than per address: an attacker who changes
#: address between guesses must not get a fresh budget. Its own ledger, and its
#: own NAMES — the panel keeps one of exactly this shape further down the file,
#: keyed by client address. Sharing a name would mean whichever was defined
#: second silently answered for both, and somebody fumbling their password
#: would be charged against the ledger that locks admins out of the panel.
_user_fails = {}                 # identity id -> [count, blocked_until]


def user_login_blocked(pid):
    rec = _user_fails.get(pid)
    return bool(rec and rec[1] > time.time())


def note_user_login_failure(pid):
    rec = _user_fails.setdefault(pid, [0, 0])
    rec[0] += 1
    if rec[0] >= 5:
        rec[1] = time.time() + min(300, 15 * (2 ** (rec[0] - 5)))


def clean_email(v):
    """The address as it will be stored, or "". Lowercased, because somebody
    typing their own address at a login box does not remember which case they
    used the day they were enrolled.

    Deliberately NOT a grammar. Every regex anybody writes for this refuses
    somebody's real address, and there is nothing here that sends mail, so
    there is nothing to bounce: it is a handle that must be unique, must be
    typeable, and must look enough like an address that a person recognises
    it as the thing to type."""
    v = str(v or "").strip().lower()
    if len(v) > 160 or " " in v:
        return ""
    name, at, host = v.partition("@")
    if not at or not name or "." not in host or host.startswith("."):
        return ""
    return v


def identity_by_email(email):
    """The person who logs in with this address, or None. The comparison is on
    the stored value, which is already lowercased, so two rows cannot differ by
    case alone — see check_email."""
    want = clean_email(email)
    if not want:
        return None
    for pid, rec in read_identities().items():
        if (rec.get("email") or "") == want:
            return dict(rec, id=pid)
    return None


def check_email(email, skip_pid=""):
    """The address, or ("", reason). Unique across identities: it is what
    somebody types to sign in, so two rows holding one address is a login with
    no answer rather than a duplicate somebody can tidy up later."""
    v = clean_email(email)
    if not v:
        return "", "that does not look like an email address"
    other = identity_by_email(v)
    if other and other["id"] != skip_pid:
        return "", "somebody here already uses that address"
    return v, ""


def check_user_password(pw):
    """What is wrong with this password, or "" if nothing is. The same floor an
    admin account gets: there is one rule in this product for how long a
    password has to be, and a second number for a second population would be
    two answers to one question."""
    pw = str(pw or "")
    if len(pw) < MIN_PASSWORD:
        return "password must be at least %d characters" % MIN_PASSWORD
    if len(pw) > 512:
        return "that is longer than a password needs to be"
    return ""


def set_identity_password(pid, pw):
    """The person choosing their OWN. Returns "" or the reason it was refused.

    An admin never passes through here. They mint a setup link and the person
    at the other end of it sets the password — an admin who chose it would
    know it, and the whole point of the link is that nobody but its holder
    ever does."""
    rows = read_identities()
    if pid not in rows:
        return "no such identity"
    bad = check_user_password(pw)
    if bad:
        return bad
    salt, dk = hash_password(str(pw))
    rows[pid].update(pw_salt=salt, pw_hash=dk, pw_set_at=int(time.time()))
    write_identities(rows)
    _user_fails.pop(pid, None)
    close_user_sessions(pid)
    return ""


def verify_identity_password(pid, pw):
    """True where it matches. Compared HERE and never in the browser, and the
    back-off is charged on the way out rather than the way in, so a correct
    password entered after four wrong ones still works."""
    rec = read_identities().get(pid)
    if not rec or not rec.get("pw_hash"):
        return False
    ok = verify_password(str(pw or ""), rec["pw_salt"], rec["pw_hash"])
    if ok:
        _user_fails.pop(pid, None)
    else:
        note_login_failure(pid)
    return bool(ok)


def wake_words_in_use(skip_pid=""):
    """Every word that already wakes something, as (word, what it belongs to).

    Both populations, because a collision does not care which list it came
    from: a person whose word is near the house's is a person who turns the
    lights off by saying their own name."""
    out = []
    doc = read_routes()
    for rid in route_order(doc):
        rec = doc["routes"][rid]
        prof = find_look(str(rec.get("speech") or ""), _speech_pool()) \
               or find_look(_speech_default(), _speech_pool()) or {}
        for w in [prof.get("wakeword") or rec.get("wakeword") or ""] \
                 + list(prof.get("aliases") or rec.get("aliases") or []):
            if w:
                out.append((w, rec.get("name") or rid))
    for pid, rec in read_identities().items():
        if pid != skip_pid and rec.get("wakeword"):
            out.append((rec["wakeword"], identity_label(rec)))
    return out


def check_wake_word(word, skip_pid=""):
    """"" if this word is somebody's to take, or why it is not.

    Refused HERE, against the matcher that does the waking, rather than by
    comparing strings: a word acoustically close to the house name puts you
    back where you started, and it would pass any comparison of letters. What
    gets through is exactly what will not cross-trigger, because the same
    rules decided both."""
    w = wake_norm(word)
    if not w:
        return "give them a word"
    if len(w) < 3:
        return "too short to hear reliably — three letters or more"
    if len(w.split(" ")) > 2:
        return "one word, or two at most"
    for other, whose in wake_words_in_use(skip_pid):
        if wake_collides(w, other):
            same = wake_norm(other) == w
            return ('"%s" is already %s\'s word' % (other, whose) if same else
                    '"%s" is too close to "%s", which is %s\'s — they would '
                    'wake each other' % (word.strip(), other, whose))
    return ""


def set_identity_wake(pid, word):
    rows = read_identities()
    if pid not in rows:
        return "no such identity"
    w = str(word or "").strip()
    if not w:                                    # clearing it is always allowed
        rows[pid]["wakeword"] = ""
        write_identities(rows)
        return ""
    bad = check_wake_word(w, skip_pid=pid)
    if bad:
        return bad
    rows[pid]["wakeword"] = wake_norm(w)
    write_identities(rows)
    return ""


def identity_ready(rec):
    """Has this person finished arriving? True once they have set a password.

    It is the whole of what divides the two lists in the panel: a row without
    one is a setup link outstanding and sits on ENROLLMENTS, a row with one is
    somebody who is here and sits under IDENTITY. Nothing else decides it and
    no admin can set it by hand — only the person at the far end of the link,
    by using it."""
    return bool(rec.get("pw_hash"))


def read_identities():
    try:
        with open(IDENTITIES_PATH) as fh:
            doc = json.load(fh)
        stored = doc.get("identities", {}) if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}
    out = {}
    for pid, rec in stored.items():
        if not isinstance(rec, dict):
            continue
        row = dict(IDENTITY_DEFAULTS)
        row.update({k: v for k, v in rec.items() if k in IDENTITY_DEFAULTS})
        out[str(pid)] = row
    return out


def write_identities(rows):
    with _identities_lock:
        tmp = IDENTITIES_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"version": 1, "identities": rows}, fh,
                      indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)                     # URL secret hashes
        os.replace(tmp, IDENTITIES_PATH)


def identity_label(rec):
    return rec.get("name") or "unnamed person"


def new_identity(name, email, by):
    """Mint one, and hand back (setup token, record) — or (None, error).

    The token is shown once, in the URL an admin hands over. What is stored is
    its hash, so a panel that has been closed cannot show it again and a copy
    of this file cannot be read back into a working URL. It buys ONE thing:
    the page that asks them to choose a password. After that the account is
    reached by signing in, and the link is spent."""
    name = str(name or "").strip()[:60]
    if not name:
        return None, "a name is required"
    email, bad = check_email(email)
    if bad:
        return None, bad
    rows = read_identities()
    if len(rows) >= MAX_IDENTITIES:
        return None, ("that is %d identities already — remove one first"
                      % MAX_IDENTITIES)
    if any(r["name"].lower() == name.lower() for r in rows.values()):
        # Not a security property — the email is the handle and two people
        # called Sam are still told apart by it. It is that a list with two
        # identical rows is one an admin cannot act on.
        return None, "there is already an identity with that name"
    pid = "p" + secrets.token_hex(6)
    secret = secrets.token_urlsafe(32)
    salt, dk = hash_key(secret)
    rows[pid] = dict(IDENTITY_DEFAULTS, name=name, email=email,
                     salt=salt, hash=dk,
                     created=int(time.time()), created_by=str(by or "")[:60])
    write_identities(rows)
    # Filed with their own population the moment they exist, and the group is
    # minted if there is not one — the same rule every other kind follows. A
    # row belonging to no group is one an allow-list cannot name, so the first
    # grant to everybody would be a tick per person, which is the data entry
    # groups exist to remove.
    join_group(pid, default_group("identity", by))
    return pid + "." + secret, dict(rows[pid], id=pid)


def reissue_identity(pid):
    """A fresh setup link, and everything the old credentials opened is shut.

    This is the ONLY recovery path, and it is deliberately the same gesture as
    creating somebody: a forgotten password and a leaked URL want the same
    answer, which is a new link and a password only its holder ever chooses.
    An admin who could set one would know it.

    So it clears the password as well as minting a new secret. Leaving it in
    place would hand out a link that the setup page then refuses — the account
    already has a password — which is a dead end wearing the shape of a fix.
    Every signed-in browser is dropped with it: an account being recovered is
    one whose open doors are the problem."""
    rows = read_identities()
    rec = rows.get(pid)
    if not rec:
        return None
    secret = secrets.token_urlsafe(32)
    rec["salt"], rec["hash"] = hash_key(secret)
    rec.update(pw_salt="", pw_hash="", pw_set_at=0)
    write_identities(rows)
    _user_fails.pop(pid, None)
    close_user_sessions(pid)
    return pid + "." + secret


def find_identity(token):
    """The person this token belongs to, or None. Same shape as a display
    token and an embed key: id, a dot, and the secret."""
    pid, _, secret = str(token or "").partition(".")
    if not pid or not secret:
        return None
    rec = read_identities().get(pid)
    if not rec or not rec.get("hash"):
        return None
    try:
        ok = hmac.compare_digest(
            hash_key(secret, bytes.fromhex(rec["salt"]))[1], rec["hash"])
    except (KeyError, TypeError, ValueError):
        return None                              # a record edited by hand
    return dict(rec, id=pid) if ok else None


def note_identity_seen(pid):
    """Last seen, at most once every SEEN_INTERVAL. A person's browser talks to
    this server as often as a display's does, and writing on every request
    would make a list nobody is reading the busiest file on the box."""
    rows = read_identities()
    rec = rows.get(pid)
    now_ = int(time.time())
    if not rec or now_ - int(rec.get("last_seen") or 0) < SEEN_INTERVAL:
        return
    rec["last_seen"] = now_
    write_identities(rows)


def admin_identities():
    """The list, less the credentials. Neither the setup secret nor the
    password leaves this server — the first after the one moment it was
    minted, the second ever."""
    rows = read_identities()
    # WHETHER, never what. That they have set a password is the fact the panel
    # is built on: it is what moves a row from the enrolment queue to the
    # register, and it is the one thing an admin cannot do for them.
    return [dict({k: rec.get(k) for k in
                  ("name", "email", "created", "last_seen", "created_by",
                   "pw_set_at")},
                 id=pid, label=identity_label(rec),
                 wakeword=rec.get("wakeword") or "",
                 ready=identity_ready(rec))
            for pid, rec in sorted(rows.items(), key=lambda kv: kv[1]["created"])]


# -------------------------------------------------------------------- groups
# A name for a set of them, so a grant can be made once instead of ticked
# twelve times and re-ticked every time somebody gets a new phone.
#
# TWO KINDS, and they do not mix. A group of PEOPLE holds rows that asked to be
# here; a group of DEVICES holds rows an admin created and sent a code for.
# They are different populations answering different questions — "the physics
# department" and "the screens in the east wing" — and a group that could hold
# both would be a list nobody could describe.
#
# Groups are named wherever access is granted. Today that is an endpoint's
# allow-list; anything later that grants something can name them the same way,
# which is the point of them living in a file of their own rather than inside
# the thing that currently uses them.
GROUPS_PATH = os.path.join(ROOT, "groups.json")
#: Re-entrant, because a mutation holds it across read-modify-WRITE and
#: write_groups takes it again on the way out.
_groups_lock = threading.RLock()
#: THREE populations now, and the third is the only one that is not a display.
#: `user` and `device` both hold DISPLAY rows — one arrived by asking, the
#: other by taking a code — which is what "people" meant here while a refusal
#: was per device and nothing issued a person anything. `identity` holds people
#: proper: rows from identities.json, reached by their own URL from whatever
#: machine they open it on.
#:
#: The obvious move was to repurpose `user` and it is the one to refuse. A
#: group's kind is fixed at creation BECAUSE changing it silently empties it,
#: and repurposing the kind does that to every existing group of it at once, on
#: upgrade, with nothing to migrate into — the identities those laptops belong
#: to do not exist. So the third kind is added beside them and nothing empties.
GROUP_KINDS = ("device", "identity")
#: Whose members are display rows, and whose are people. A route names groups
#: without caring what is in them, so the answer depends on who is asking: a
#: device must not be let through by a group of people that happens to sit on
#: the same allow-list, and a person must not be let through by a group of
#: screens.
DISPLAY_GROUP_KINDS = ("device",)
IDENTITY_GROUP_KINDS = ("identity",)
#: Read-time only, and it never rewrites the file. `user` was a second kind of
#: DISPLAY group — the machines that asked rather than the ones an admin
#: invited — which is how a row ENROLLED and not which population it is in. It
#: folds into `device` because both were always display rows, so no group loses
#: a member and no admin loses a name.
LEGACY_GROUP_KINDS = {"user": "device"}
MAX_GROUPS = 200


def read_groups():
    try:
        with open(GROUPS_PATH) as fh:
            doc = json.load(fh)
        stored = doc.get("groups", {}) if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}
    out = {}
    for gid, rec in stored.items():
        if not isinstance(rec, dict):
            continue
        kind = LEGACY_GROUP_KINDS.get(rec.get("kind"), rec.get("kind"))
        out[str(gid)] = {
            "name": str(rec.get("name") or "")[:60],
            "kind": kind if kind in GROUP_KINDS else "device",
            # NOT truncated on read. A system group legitimately holds the
            # whole deployment, and cutting the stored list here would drop
            # members on the next write of a document that was never too long.
            "members": [str(m)[:32] for m in (rec.get("members") or [])],
            "created": rec.get("created"), "created_by": rec.get("created_by"),
            # One per kind, made by the server and not deletable. See
            # ensure_system_groups.
            "system": bool(rec.get("system")),
        }
    return out


def write_groups(groups):
    with _groups_lock:
        tmp = GROUPS_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"version": 1, "groups": groups}, fh, indent=2, sort_keys=True)
        os.replace(tmp, GROUPS_PATH)


def enrolled_as(rec):
    """HOW a display row got here: "asked" or "invited".

    It was `group_kind_of`, and it decided which of two display populations a
    row belonged to — which was the wrong question. Both happen in a browser on
    one machine, so both describe a device; what differed was only the door
    they came through. A person is an identity that carries from a phone to a
    laptop, and that is a different FILE rather than a different flavour of
    this one.

    So this is an attribute now. It labels a row and nothing more: it does not
    pick a group, it cannot keep two rows out of the same group, and there is
    no control to override it. A screen an admin minted a code for is
    "invited"; a browser that opened the display page and asked is "asked".

    Rows that predate `origin` are read from what only an admin's invitation
    leaves behind — an approver's name on a row that never asked for anything.
    A guess, and the same guess the row's own history supports."""
    origin = str(rec.get("origin") or "")
    if origin:
        return "invited" if origin == "code" else "asked"
    return "invited" if (rec.get("approved_by") and not rec.get("requested_at")) \
           else "asked"


#: What the group each population lands in is called when this server has to
#: make one. Named for what is in them rather than for how they arrived, since
#: an admin will rename them long before they remember which is which.
#: The auto-created group per kind. `user` is named for what it has always
#: actually held — the personal machines that asked to be here — now that
#: "People" means people. Renaming the constant does NOT rename a group that
#: already exists: those are somebody's data, and an upgrade that renamed them
#: would be editing a list an admin wrote. The kind's LABEL in the panel is
#: what changes for them.
DEFAULT_GROUP_NAME = {"device": "Devices", "identity": "Users"}
#: Names these groups used to be created with. A system group still carrying
#: one is corrected to the current name — it was the server's word, not an
#: admin's, and leaving it means an install renamed by a day's timing. Only
#: these exact strings; anything else is a name somebody chose and is theirs.
SUPERSEDED_GROUP_NAMES = {"identity": ("People",)}


def system_group(kind):
    """The permanent group for a population, by id, or "" if it is somehow
    missing. Never mints: ensure_system_groups does that, once, at startup."""
    for gid, rec in sorted(read_groups().items()):
        if rec["kind"] == kind and rec["system"]:
            return gid
    return ""


def ensure_default_membership():
    """Everything that works is in its default group, and put back if it is
    not. That group is the root — a custom group is somewhere a row is ALSO
    put, never somewhere it moves to — so a row missing from it is a row an
    older rule took out, and it is the one membership nobody chose.

    Rows that do not work yet are left alone: they join when they start
    working, which is the same rule at the other end."""
    displays, idents = read_displays(), read_identities()
    groups = read_groups()
    added = 0
    for kind, ids in (("device", [d for d, r in displays.items()
                                  if r.get("approved") and r.get("hash")]),
                      ("identity", list(idents))):
        gid = next((g for g, r in groups.items()
                    if r["kind"] == kind and r["system"]), "")
        if not gid:
            continue
        for i in ids:
            if i not in groups[gid]["members"] and add_member(groups[gid], i):
                added += 1
    if added:
        write_groups(groups)
        print("put %d row(s) back in their default group" % added, flush=True)


def migrate_pin_identities():
    """THE PIN MODEL DOES NOT CARRY FORWARD. A row from before this change has
    a PIN hash and no email, which is an account nobody can sign in to: the
    login page asks for an address the record does not have, and there is no
    admin gesture that invents one.

    Wiped rather than half-migrated. The alternative was to keep the names and
    the wake words and leave every row needing an address typed in and a link
    reissued before it worked — which is the same work as creating them again,
    with a list of broken rows sitting in the panel until somebody does it.
    Announced loudly on the way out, because it is somebody's data and a
    server that removes data silently is one you cannot trust with the rest.

    Runs once and only where the old shape is actually present: a fresh
    install has no file, and an install already on the new model has no row
    carrying a `pin_hash`."""
    rows = read_identities()
    old = [pid for pid, rec in rows.items()
           if rec.get("pin_hash") or not rec.get("email")]
    if not rows or not old:
        return
    for pid in old:
        print("identity %s (%s) removed: the PIN model it was created under "
              "is gone, and it has no email address to sign in with — create "
              "them again under ENROLLMENTS \u25b8 USER"
              % (pid, identity_label(rows[pid])), flush=True)
        rows.pop(pid, None)
    write_identities(rows)
    print("removed %d identity row(s) from the PIN model" % len(old), flush=True)


def migrate_unenrolled_invites():
    """Rows invited before enrolment was what approved them.

    They sit `approved` with no token and a code still waiting, which is a
    screen nobody has switched on being counted as one that works. Corrected
    once, here, because the alternative is every reader of `approved` carrying
    an "…and does it have a token" clause forever.

    Only that exact shape. A row with a token is working and is left alone; a
    row with neither is one whose code ran out, and its approval is not this
    function's business."""
    displays = read_displays()
    fixed = [d for d, r in displays.items()
             if r.get("approved") and not r.get("hash") and r.get("code")]
    for did in fixed:
        displays[did]["approved"] = False
        displays[did]["approved_at"] = 0
    if fixed:
        write_displays(displays)
        print("corrected %d invited row(s) that were approved before enrolling: %s"
              % (len(fixed), ", ".join(fixed)), flush=True)


def ensure_system_groups(by="the server"):
    """The two groups that always exist: one for displays, one for people.

    They are made HERE, in code, rather than on first need, and they cannot be
    deleted. A default that an admin can delete is not a default — everything
    enrolling afterwards has nowhere to land, and the version of this that
    minted on demand made that worse rather than better: it adopted any
    existing group of the right kind before creating one, so deleting "Devices"
    while a group called "East wing" existed sent every screen that arrived
    afterwards silently into East wing.

    An install that already has a default from that era keeps it — the group
    the settings key names is adopted, with its name and its members, rather
    than left beside a second one meaning the same thing. Only where there is
    nothing to adopt is one created.
    """
    groups = read_groups()
    cfg = display_settings()
    changed = cfg_changed = False
    for kind in GROUP_KINDS:
        mine = [g for g, r in groups.items() if r["kind"] == kind and r["system"]]
        if mine:
            # There is one. Correct its name only where it still carries a
            # default this server has since stopped using.
            # ONCE, not at every startup. An admin may rename a default group
            # — the name is theirs, only its membership is the server's — and
            # "People" is a name somebody might legitimately choose. Running
            # this on every start would take it back off them a restart later,
            # which is the thing DEFAULT_GROUP_NAME's own comment says must not
            # happen.
            for g in (mine if not cfg.get("group_names_done") else []):
                if groups[g]["name"] in SUPERSEDED_GROUP_NAMES.get(kind, ()):
                    was = groups[g]["name"]
                    groups[g]["name"] = DEFAULT_GROUP_NAME[kind]
                    changed = True
                    print("group %s renamed %s -> %s (it was still on the old "
                          "default)" % (g, was, DEFAULT_GROUP_NAME[kind]),
                          flush=True)
            continue
        gid = str(cfg.get(kind + "_group") or "")
        # ONLY a group this server named. That settings key was written by an
        # older default_group which fell back to "the first group of this kind"
        # whenever it was blank — so on an upgraded install it routinely names
        # a group an ADMIN created and named. Adopting that makes their group
        # permanent, fills it with the whole estate, and leaves no way back:
        # its members cannot be edited, it cannot be deleted, and no other
        # group can be nominated. A name this server chose is the only safe
        # evidence that the group was ever meant to be the default.
        ours = (DEFAULT_GROUP_NAME[kind],) + SUPERSEDED_GROUP_NAMES.get(kind, ())
        if gid in groups and groups[gid]["kind"] == kind \
           and groups[gid]["name"] in ours:
            groups[gid]["system"] = True          # adopt what is already there
            print("group %s (%s) is now the permanent %s group"
                  % (gid, groups[gid]["name"], kind), flush=True)
        else:
            gid = "g" + secrets.token_hex(4)
            groups[gid] = {"name": DEFAULT_GROUP_NAME[kind], "kind": kind,
                           "members": [], "created": int(time.time()),
                           "created_by": by, "system": True}
            print("group %s (%s) created as the permanent %s group"
                  % (gid, DEFAULT_GROUP_NAME[kind], kind), flush=True)
        changed = True
        if cfg.get(kind + "_group") != gid:
            cfg[kind + "_group"] = gid
            cfg_changed = True
    if not cfg.get("group_names_done"):
        cfg["group_names_done"] = 1
        cfg_changed = True
    if changed:
        write_groups(groups)
    if cfg_changed:
        write_display_settings(cfg)


def default_group(kind, by="the server"):
    """Where a row lands when it starts working. One answer per kind, and it is
    the permanent group — never "the first one of this kind I found", which is
    how a screen ended up in a group somebody built for something else."""
    return system_group(kind) if kind in GROUP_KINDS else ""


def join_group(did, gid):
    """Put a display in a group, once. Silent where it is already there, and
    where the group has gone — this runs on the back of somebody enrolling a
    screen, and a failure to file it is not a reason to refuse the screen."""
    if not gid:
        return
    with group_edit() as groups:
      rec = groups.get(gid)
      if not rec or did in rec["members"]:
        return
      if not add_member(rec, did):
        print("group %s is full (%d) — %s was NOT filed into it"
              % (gid, MAX_ALLOW, did), flush=True)
        return
      write_groups(groups)


def drop_from_groups(row_id):
    """Take a deleted row out of every group. Returns the names it was in.

    The opposite of join_group, and it was missing: deleting a display or a
    person cleared it from every endpoint's allow-list and left it sitting in
    its groups. That reads as harmless — admin_groups filters to rows that
    still exist, so nothing phantom is ever shown — and it is not, for one
    reason. A group's member list is capped at MAX_ALLOW and join_group appends
    before it truncates, so a group filled with dead ids silently stops
    accepting live ones: the new member is the element that gets cut. The
    screen enrols, appears to work, and is simply not in the group."""
    with group_edit() as groups:
        was = []
        for rec in groups.values():
            if row_id in rec["members"]:
                rec["members"] = [m for m in rec["members"] if m != row_id]
                was.append(rec["name"])
        if was:
            write_groups(groups)
        return was


def _rows_readable(path, key):
    """(readable, ids). The distinction read_displays cannot make: it answers
    {} for a file with no rows AND for one that could not be read at all, which
    is the right shape for a caller that wants to carry on and a catastrophe
    for one that DELETES what is missing from it."""
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return True, set()                       # nothing here yet, genuinely
    except (OSError, ValueError):
        return False, set()                      # unreadable, malformed, denied
    rows = doc.get(key)
    if not isinstance(rows, dict):
        return False, set()
    return True, set(rows)


def prune_group_members():
    """Ids in groups that belong to no row at all — left by every delete that
    happened before drop_from_groups existed.

    GUARDED, because it deletes from one file based on the contents of two
    others. A truncated displays.json, a hand edit with a trailing comma, or a
    restart under an account that cannot read a 0600 file all look exactly like
    "there are no displays" — and this would then strip every display from
    every group. The system groups would be refilled at the next healthy
    startup, which is what would hide it; a custom group has no repopulation
    path and would be gone for good."""
    ok_d, dids = _rows_readable(DISPLAYS_PATH, "displays")
    ok_i, pids = _rows_readable(IDENTITIES_PATH, "identities")
    if not (ok_d and ok_i):
        print("not pruning groups: %s could not be read"
              % (", ".join(n for n, ok in (("displays.json", ok_d),
                                           ("identities.json", ok_i)) if not ok)),
              flush=True)
        return
    live = dids | pids
    groups = read_groups()
    if not live and any(r["members"] for r in groups.values()):
        # Every row gone and groups still full is a state to look at, not one
        # to tidy up after.
        print("not pruning groups: no rows exist at all, which is not a thing "
              "to act on unprompted", flush=True)
        return
    gone = 0
    for rec in groups.values():
        keep = [m for m in rec["members"] if m in live]
        gone += len(rec["members"]) - len(keep)
        rec["members"] = keep
    if gone:
        write_groups(groups)
        print("pruned %d member(s) of no row from groups" % gone, flush=True)


def file_display(rec_or_id, kind=None, by="the server"):
    """A row that has just started working, filed with its own population.

    Called at the two moments something becomes usable — a code redeemed, a
    request approved — because those are the two ways in, and neither of them
    used to leave the row anywhere an allow-list could find it."""
    did = rec_or_id if isinstance(rec_or_id, str) else rec_or_id["id"]
    # One display population now, so there is nothing to work out: every screen
    # and every laptop is a display. How it enrolled is still on the row, where
    # it describes the row rather than deciding which list it may be put in.
    join_group(did, default_group("device", by))


def clean_members(ids, kind):
    """Only rows that exist, out of this kind's own FILE. A member that is not
    there is dropped rather than refused — the panel sends the list it was
    shown, and a row deleted in another tab between the two is not a mistake
    worth making somebody retype a form over.

    There is no longer a test on how a display enrolled. That was the second
    display kind, and enrolment is a property of a row rather than a
    population: a group holding a wall screen and somebody's laptop is a
    perfectly good group, and refusing to let one exist was the split saying
    something about the rows that the rows already said themselves.

    What remains is the one distinction that is real — WHICH FILE the ids come
    out of. Displays and people are minted independently, so their ids are not
    interchangeable, and that is why a kind still cannot change under an
    existing group: it would not filter the members, it would fail to find any
    of them."""
    seen, out = set(), []
    if kind in IDENTITY_GROUP_KINDS:
        known = read_identities()
        for pid in (ids or []):
            pid = str(pid)[:32]
            if pid in known and pid not in seen:
                seen.add(pid)
                out.append(pid)
        return out[:MAX_ALLOW]
    displays = read_displays()
    for did in (ids or []):
        did = str(did)[:32]
        if did in displays and did not in seen:
            seen.add(did)
            out.append(did)
    return out[:MAX_ALLOW]


@contextlib.contextmanager
def group_edit():
    """Read, change, write — with nothing else writing in between.

    Every mutator used to read the whole document, change one row and write the
    whole document back, with the lock held only around the write itself. This
    is a threading server and displays enrol on their own schedule, so those
    interleave for real: the last writer wins wholesale and the loser's change
    is gone with no error and no log line. The dangerous one is join_group,
    which is fire-and-forget by design — a screen enrols, is told nothing went
    wrong, and is not in its group."""
    with _groups_lock:
        groups = read_groups()
        yield groups


def group_cap(rec):
    """How many members this group may hold, or None for no bound.

    MAX_ALLOW bounds a HAND-WRITTEN list: an admin ticking devices into a
    group, or naming them on an endpoint, and nobody does that five thousand
    times. The default group is not that. It holds the whole deployment by
    construction — everything that enrols is in it — so bounding it by a number
    meant for a curated list makes the cap a limit on the installation, and
    MAX_IDENTITIES is 500, exactly MAX_ALLOW, so the Users group could not hold
    the maximum number of people even with nothing ever deleted.

    What bounds a system group is what bounds the population: max_displays and
    MAX_IDENTITIES, enforced where rows are created."""
    return None if rec.get("system") else MAX_ALLOW


def add_member(rec, row_id):
    """Put a row in a group, and say whether it actually went in.

    Every add used to be `(members + [id])[:MAX_ALLOW]` — append, then keep the
    FIRST cap-many — so a full group discarded the element just added and every
    caller reported success. A screen enrolled, got a token, showed as approved,
    and was refused by every endpoint naming its group, with nothing anywhere
    saying why. Truncation is not a way to report a failure."""
    if row_id in rec["members"]:
        return True
    cap = group_cap(rec)
    if cap is not None and len(rec["members"]) >= cap:
        return False
    rec["members"] = rec["members"] + [row_id]
    return True


def group_members(gids, groups=None, kinds=None):
    """Every member id named by these groups, flattened. Grants ADD UP: this
    is unioned with an endpoint's individually named rows, and being in a group
    never takes an individual grant away.

    `kinds` narrows it to one population. Without it a route naming both a
    group of screens and a group of people would answer for either — and since
    the two files mint ids independently, that is not merely wrong, it is
    wrong in a way nobody would see until two ids happened to collide."""
    groups = read_groups() if groups is None else groups
    out = set()
    for gid in (gids or []):
        rec = groups.get(gid)
        if rec and (kinds is None or rec["kind"] in kinds):
            out.update(rec["members"])
    return out


def validate_group(obj, current):
    rec = dict(current)
    if "name" in obj:
        rec["name"] = str(obj["name"] or "").strip()[:60]
    if not rec.get("name"):
        return None, "a group needs a name — it is what you will look for"
    if "kind" in obj:
        k = str(obj["kind"] or "").strip()
        if k not in GROUP_KINDS:
            return None, "a group is either people or devices"
        # ONLY on a group being created. On an existing one the kind is fixed,
        # and taking the requested one here made it decide which FILE the
        # members below were resolved against — so a save that switched the
        # kind had its members validated as the other population, and the
        # handler then put the kind back and kept them. The group ended up
        # holding ids it could never show, never grant and never be rid of,
        # still counting against its cap.
        if not current.get("kind"):
            rec["kind"] = k
    if "members" in obj:
        rec["members"] = clean_members(obj["members"], rec["kind"])
    # Never off the wire. Which group is permanent is this server's to decide,
    # not something a panel can hand back having lost it in a round trip.
    rec["system"] = bool(current.get("system"))
    if rec["system"]:
        # THE DEFAULT GROUP IS THE ROOT. Everything that enrols is in it and
        # stays in it; a custom group is somewhere a row is ALSO put, never
        # somewhere it moves to. So its membership is not a panel's to edit —
        # enrolling adds, deleting the row removes, and nothing else touches
        # it. A name is still the admin's.
        rec["members"] = list(current.get("members") or [])
    return rec, None


def admin_groups():
    groups = read_groups()
    displays = read_displays()
    idents = read_identities()
    out = []
    # The two the server keeps come first, always, whatever they are called.
    # They are where everything lands, so they are the two an admin looks for —
    # and sorting them in among the custom ones by name would move them every
    # time somebody made a group starting with an earlier letter.
    for gid, rec in sorted(groups.items(),
                           key=lambda kv: (not kv[1]["system"], kv[1]["kind"],
                                           kv[1]["name"].lower())):
        # Named rows only. A member whose row was deleted is not shown as a
        # phantom — it is simply gone, the same way a deleted display leaves an
        # endpoint's allow-list. Which FILE the name comes out of is the
        # group's kind: a group of people is the one that is not displays.
        if rec["kind"] in IDENTITY_GROUP_KINDS:
            live = [m for m in rec["members"] if m in idents]
            labels = [identity_label(idents[m]) for m in live]
        else:
            live = [m for m in rec["members"] if m in displays]
            labels = [display_label(displays[m]) for m in live]
        out.append(dict(rec, id=gid, members=live, labels=labels))
    return out


# ------------------------------------------------------------------ accounts
# Local accounts only. No directory, no third party, no network call to log in
# — the same principle as the speech pipeline. Two roles:
#   admin   configure everything, manage accounts
#   viewer  read the configuration, change nothing
ROLES = ("admin", "viewer")
PBKDF2_ROUNDS = 600_000          # ~0.3s per attempt: cheap once, costly to grind
SESSION_IDLE = 30 * 60           # inactivity before a session dies; set at startup
RUNNING = {}                     # what is actually bound, to compare against config
#: The exact sockets this process is holding, as (host, port). Kept OUT of
#: RUNNING deliberately: RUNNING is handed to the panel as JSON, and a set of
#: tuples in it stops the whole /app response being serialisable — which is
#: not a degraded answer but no answer at all, read in the browser as
#: "Failed to fetch" and in the log as a traceback. RUNNING is a wire format;
#: this is bookkeeping.
_BOUND = set()
# Read once at startup rather than per request, for the same reason the ports
# are: this decides what a listener IS, and a listener cannot be re-founded
# under the requests already in flight on it.


def app_pending(cfg):
    """Which stored settings differ from what is actually running, and so are
    waiting on a restart. One implementation, because this is read by the panel
    on load and again on save, and two copies would drift into disagreeing
    about whether a restart is owed."""
    keys = ("http_port", "https_port", "admin_port", "session_idle_minutes",
            "bind", "bind_address")
    return sorted(k for k in keys
                  if RUNNING.get(k) is not None and RUNNING[k] != cfg[k])


# ------------------------------------------------------- a scheduled restart
# Nothing supervises this process. `serve.sh` launches it with `setsid nohup`
# and there is deliberately no systemd unit, because that is what lets the
# whole thing install and run without elevated rights — so a setting that
# merely STOPPED the server at three in the morning would be a setting that
# ended the service, with nothing left to start it again.
#
# So it is a HAND-OVER rather than a stop. At the appointed minute this process
# launches `serve.sh restart` in a session of its own and then lets that script
# kill it: `stop` waits for the socket to be released, `start` binds a fresh
# process. The helper is detached, so the death of its parent is exactly what
# it was launched to cause rather than something that takes it with it.
#
# What this cannot do is catch a `start` that fails. That risk is real, it is
# stated in the panel, and the helper's output goes to a file that survives the
# handover — `server.log` is truncated by every start, so a failure written
# there would be overwritten by the next attempt or lost with the process that
# reported it.
RESTART_LOG = os.path.join(ROOT, "restart.log")
#: The value being watched, when it became current, and whether this process
#: has already handed over.
#:
#: ARMING is the whole of the correctness here. A time is only ever acted on if
#: it was already set when that minute arrived, which settles two cases with
#: one rule: the fresh process that comes back at 03:00:04 does not restart
#: itself again in a loop, and an admin who types 14:23 at 14:23 does not take
#: the server out from under themselves mid-sentence.
_restart = {"at": None, "armed": 0.0, "fired": False}
#: When somebody last USED this server, as opposed to a screen checking in.
#: Polls arrive every few seconds from every display in the building and would
#: read as continuous activity; a question, a transcription or a spoken reply
#: is a person, and a restart in the middle of one is a crash as far as they
#: can tell.
_last_use = 0.0
RESTART_QUIET = 60        # seconds of nobody using it before handing over
RESTART_WINDOW = 3600     # how long to wait for that, before leaving it a day


def note_use():
    global _last_use
    _last_use = time.time()


def clock_at(hhmm, now=None):
    """Epoch seconds for HH:MM today, on THIS machine's clock.

    The server's own clock and not a device's, which is the opposite of the
    display refresh and right for the same reason: that one is about a screen's
    night where it hangs, this one is about one machine."""
    m = re.match(r"^(\d{1,2}):(\d{2})$", str(hhmm or ""))
    if not m:
        return 0
    lt = time.localtime(now if now is not None else time.time())
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday,
                        int(m.group(1)), int(m.group(2)), 0, 0, 0, -1))


def restart_due(now=None):
    """Is it time, and is it safe? Split from the handover so the decision can
    be reasoned about — and tested — without a process dying at the end of it."""
    now = now if now is not None else time.time()
    at = str(read_app().get("restart_at") or "")
    if at != _restart["at"]:
        # Newly set, newly cleared, or this process reading it for the first
        # time. Whichever it is, the clock starts here — see the arming note
        # above.
        _restart.update(at=at, armed=now, fired=False)
    if not at or _restart["fired"]:
        return False
    due = clock_at(at, now)
    if not due or due <= _restart["armed"]:
        return False                      # already past when it was set
    if now < due:
        return False                      # not yet
    if now - due > RESTART_WINDOW:
        return False                      # missed it — leave it for tomorrow
    # Deferred while somebody is using it, and re-asked on the next tick. The
    # window above is what stops that becoming "never": an hour of waiting for
    # quiet, and then it is tomorrow's problem rather than something forced
    # through the middle of a conversation.
    return now - _last_use >= RESTART_QUIET


def do_scheduled_restart():
    """Hand over to serve.sh and expect to be killed by it."""
    sh = os.path.join(ROOT, "serve.sh")
    if not os.access(sh, os.X_OK):
        print("scheduled restart: %s is not executable — skipped" % sh,
              flush=True)
        _restart["fired"] = True          # do not spin on it every tick
        return
    try:
        log = open(RESTART_LOG, "a")
        log.write("\n=== %s — scheduled restart (%s) ===\n"
                  % (time.strftime("%Y-%m-%d %H:%M:%S"), _restart["at"]))
        log.flush()
        _restart["fired"] = True
        print("scheduled restart — handing over to serve.sh", flush=True)
        subprocess.Popen([sh, "restart"], cwd=ROOT, stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception as e:
        # Still marked as fired: a handover that could not be launched will not
        # launch on the next tick either, and a server retrying it every twenty
        # seconds until morning is worse than one that says so once.
        print("scheduled restart could not hand over: %s" % e, flush=True)


def restart_watch():
    """Every twenty seconds, because the whole mechanism is a minute wide and
    a thread that sleeps until the exact second would have to be woken and
    recomputed every time somebody changed the setting."""
    while True:
        time.sleep(20)
        try:
            if restart_due():
                do_scheduled_restart()
        except Exception as e:
            print("scheduled restart check failed: %s" % e, flush=True)
MIN_PASSWORD = 10
_users_lock = threading.Lock()
_sessions = {}                   # token -> {"user","role","expires"}
_sessions_lock = threading.Lock()
_login_fails = {}                # client ip -> [count, blocked_until]


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return salt.hex(), dk.hex()


# ------------------------------------------------------------ wake matching
# A PORT of the display's own matcher — index.html, Wake._tryWord and the two
# helpers above it. It is here because a collision has to be refused where the
# word is STORED and not only where it is typed: a panel that checked in the
# browser would be a check an API call walks straight past, and the word that
# got in that way is the one that cross-triggers.
#
# THE COUPLING IS REAL AND IS NAMED HERE. Waking happens in the browser and
# always will — it has to be instant and it is what drops an utterance before
# it is anybody's business — so these two implementations must agree, and
# nothing in the language makes them. wake_conformance() below is the corpus
# they are both held to; change one and run it.
def wake_norm(s):
    s = re.sub(r"[^a-z0-9\s]", " ", str(s or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def wake_skel(x):
    """Consonant skeleton. Vowels are what a small model gets wrong, so two
    spellings of one spoken word collapse together: berth and birth both go
    to brth."""
    x = re.sub(r"[^a-z]", "", x)
    return x[:1] + re.sub(r"[aeiouy]", "", x[1:]) if x else x


def wake_lev(a, b):
    if a == b:
        return 0
    m, n = len(a), len(b)
    if not m or not n:
        return m or n
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (0 if a[i - 1] == b[j - 1] else 1))
        prev = cur
    return prev[n]


def wake_hit(spoken, word, strict=False):
    """Would this utterance wake that word? The same rules the display uses."""
    word = wake_norm(word)
    toks = [t for t in wake_norm(spoken).split(" ") if t]
    if not word or not toks:
        return False
    if len(word.split(" ")) > 1:                 # a multi-word alias
        return word in " ".join(toks)
    tol = 0 if strict else (2 if len(word) >= 7 else 1 if len(word) >= 4 else 0)
    skel = wake_skel(word)
    for k, t in enumerate(toks):
        if t == word:
            return True
        # the transcriber often splits a compound: "goodbye" -> "good bye"
        if k + 1 < len(toks) and t + toks[k + 1] == word:
            return True
        if strict:
            continue
        if t.startswith(word) and len(t) - len(word) <= 2:
            return True
        if tol and wake_lev(t, word) <= tol:
            return True
        if len(t) >= 3 and abs(len(t) - len(word)) <= 2 and wake_skel(t) == skel:
            return True
    return False


def wake_collides(candidate, existing):
    """Whether a proposed word would cross-trigger with one already in use, or
    the other way round. BOTH directions, because waking is not symmetric: a
    prefix rule fires for "orbital" said at "orbit" and not the reverse, and a
    word nobody can use without also waking somebody else is exactly as broken
    as one that steals theirs."""
    a, b = wake_norm(candidate), wake_norm(existing)
    if not a or not b:
        return False
    return a == b or wake_hit(a, b) or wake_hit(b, a)


#: The corpus both matchers are held to. Captured by running this port and the
#: shipping JS — index.html, Wake._tryWord — over the same cases and checking
#: they agreed on every one; they did, 368 of 368. What is kept here is the
#: subset that pins the behaviour worth not losing: near misses, a compound the
#: transcriber split, a prefix, a consonant skeleton, and strict mode refusing
#: all of it. Change either matcher and run wake_conformance().
WAKE_CORPUS = (
    ('orbit', 'orbit', False, True),
    ('orbit', 'orbit', True, True),
    ('orbital', 'orbit', False, True),
    ('orbital', 'orbit', True, False),
    ('orbits', 'orbit', False, True),
    ('orbits', 'orbit', True, False),
    ('orbet', 'orbit', False, True),
    ('orbet', 'orbit', True, False),
    ('beak on', 'beacon', False, False),
    ('beak on', 'beacon', True, False),
    ('bacon', 'beacon', False, True),
    ('bacon', 'beacon', True, False),
    ('good bye', 'goodbye', False, True),
    ('good bye', 'goodbye', True, True),
    ('commuter', 'computer', False, True),
    ('commuter', 'computer', True, False),
    ('hey computer', 'computer', False, True),
    ('hey computer', 'computer', True, True),
    ('sara', 'sarah', False, True),
    ('sara', 'sarah', True, False),
    ('saran wrap', 'sarah', False, True),
    ('saran wrap', 'sarah', True, False),
    ('adder', 'ada', False, False),
    ('adder', 'ada', True, False),
    ('aida', 'ada', False, True),
    ('aida', 'ada', True, False),
    ('haus', 'house', False, True),
    ('haus', 'house', True, False),
    ('resonate', 'resonance', False, True),
    ('resonate', 'resonance', True, False),
    ('turn off the couch lamps', 'house', False, False),
    ('turn off the couch lamps', 'house', True, False),
    ('', 'orbit', False, False),
    ('', 'orbit', True, False),
)


def wake_conformance():
    """Every case, or the ones that no longer hold. Returns [] when the port
    still behaves as it did the day it was checked against the browser's."""
    return [(sp, w, st, want, serve_got)
            for sp, w, st, want in WAKE_CORPUS
            for serve_got in (wake_hit(sp, w, st),) if serve_got != want]


def verify_password(password, salt_hex, hash_hex):
    try:
        _, dk = hash_password(password, bytes.fromhex(salt_hex))
    except ValueError:
        return False
    return hmac.compare_digest(dk, hash_hex)


def read_users():
    try:
        with open(USERS_PATH) as fh:
            doc = json.load(fh)
        return doc.get("users", {}) if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def write_users(users):
    with _users_lock:
        tmp = USERS_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"version": 1, "users": users}, fh, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)                     # password hashes
        os.replace(tmp, USERS_PATH)


def ensure_first_admin():
    """A fresh install has no accounts, and an admin interface nobody can log
    into is useless. Mint one and print the password exactly once — the same
    bootstrap the old shared key used, minus the URL."""
    users = read_users()
    if users:
        return None
    pw = secrets.token_urlsafe(15)
    salt, dk = hash_password(pw)
    users["admin"] = {"salt": salt, "hash": dk, "role": "admin",
                      "created": int(time.time())}
    write_users(users)
    return pw


def valid_username(name):
    return bool(re.fullmatch(r"[A-Za-z0-9._-]{2,32}", name or ""))


def new_session(username, role):
    token = secrets.token_urlsafe(32)
    with _sessions_lock:
        _sessions[token] = {"user": username, "role": role,
                            "expires": time.time() + SESSION_IDLE}
    return token


def get_session(token, slide=True):
    """Sliding expiry: every authenticated request pushes the deadline out, so
    a session dies from inactivity rather than mid-edit.

    `slide=False` is for the panel's heartbeat, and the distinction is the
    whole reason that route exists. A poll that renewed what it was checking
    would mean an open tab never expired at all — the check would be the
    activity keeping it alive."""
    if not token:
        return None
    now = time.time()
    with _sessions_lock:
        s = _sessions.get(token)
        if not s:
            return None
        if s["expires"] < now:
            _sessions.pop(token, None)
            return None
        if slide:
            s["expires"] = now + SESSION_IDLE
        return dict(s)


def drop_session(token):
    with _sessions_lock:
        _sessions.pop(token, None)


def drop_sessions_for(username):
    """Deleting an account or changing its password must not leave a live
    session behind that still carries the old rights."""
    with _sessions_lock:
        for t in [t for t, s in _sessions.items() if s["user"] == username]:
            _sessions.pop(t, None)


ASK_PER_MINUTE = 20
_ask_hits = {}                   # client ip -> [timestamps]
_ask_lock = threading.Lock()


def ask_allowed(ip):
    """The display is unauthenticated by design, so /ask is the one public
    route that costs something real — CPU on a local model, credits on a
    hosted one, and with an agent-capable backend rather more than that. A
    sliding window per address, no configuration to get wrong."""
    now_ = time.time()
    with _ask_lock:
        hits = [t for t in _ask_hits.get(ip, []) if now_ - t < 60]
        if len(hits) >= ASK_PER_MINUTE:
            _ask_hits[ip] = hits
            return False
        hits.append(now_)
        _ask_hits[ip] = hits
        if len(_ask_hits) > 500:                 # do not grow without bound
            for k in [k for k, v in _ask_hits.items()
                      if not v or now_ - v[-1] > 300]:
                _ask_hits.pop(k, None)
        return True


def login_blocked(ip):
    rec = _login_fails.get(ip)
    return bool(rec and rec[1] > time.time())


def note_login_failure(ip):
    """Back off geometrically after a handful of misses. A local password is
    only as good as the number of guesses somebody gets per minute."""
    rec = _login_fails.setdefault(ip, [0, 0])
    rec[0] += 1
    if rec[0] >= 5:
        rec[1] = time.time() + min(300, 15 * (2 ** (rec[0] - 5)))


def clear_login_failures(ip):
    _login_fails.pop(ip, None)


# -------------------------------------------------------------------- embeds
# Another application pulls this interface into itself. Its SERVER calls this
# server with a key and is given a short-lived session token; it then drops an
# iframe pointing at /embed?t=<token> into its page. Server to server, so the
# right to ask and what it may draw are settled in one call, before a browser
# is involved at all.
#
# Two things are fixed when the admin creates the key and can never be widened
# afterwards: the CAPABILITY envelope — may this application ask at all, open a
# microphone, speak, and how often — and the CHROME it renders. They are
# separate axes on purpose. Hiding the TALK button is not the same as denying
# the microphone: hide the control while the capability stands and a host page
# can open a microphone with nothing on screen to say so. The proof that one
# field cannot serve both is `kiosk` and `signage` — identical chrome, the
# figure alone, and opposite permissions.
EMBEDS_PATH = os.path.join(ROOT, "embeds.json")
_embeds_lock = threading.Lock()

#: The seven components the interface is made of. A list of parts rather than
#: an enumeration of layouts, because seven parts make 128 arrangements and an
#: enumeration needs extending the day somebody wants the 129th.
PARTS = ("visual", "transcript", "input", "mode", "talk", "audio", "text")

#: First-class names over the common arrangements. A preset is a starting
#: point the admin can edit, not a separate kind of token.
PRESETS = {
    "full":    {"parts": list(PARTS),
                "cap": {"ask": True, "mic": True, "speak": True}},
    "console": {"parts": ["visual", "transcript", "input", "mode", "talk", "audio"],
                "cap": {"ask": True, "mic": True, "speak": True}},
    "voice":   {"parts": ["visual", "mode", "talk", "audio"],
                "cap": {"ask": True, "mic": True, "speak": True}},
    "chat":    {"parts": ["transcript", "input", "text"],
                "cap": {"ask": True, "mic": False, "speak": False}},
    "kiosk":   {"parts": ["visual"],
                "cap": {"ask": True, "mic": True, "speak": True}},
    # Identical chrome to kiosk, opposite permissions: it must never open a
    # microphone. It speaks only when the host pushes text at it.
    "signage": {"parts": ["visual"],
                "cap": {"ask": False, "mic": False, "speak": True}},
}
CAP_DEFAULTS = {"ask": True, "mic": False, "speak": True, "rate_per_min": 20}
EMBED_TTL_MIN, EMBED_TTL_MAX = 5, 1440       # minutes a session token lives
EMBED_TTL_DEFAULT = 60

_embed_sessions = {}             # token -> {"id","parts","cap","origins","expires"}
_embed_sessions_lock = threading.Lock()
_embed_hits = {}                 # embed id -> [timestamps], its own rate window
_embed_fails = {}                # client ip -> [count, blocked_until]


def read_embeds():
    try:
        with open(EMBEDS_PATH) as fh:
            doc = json.load(fh)
        return doc.get("embeds", {}) if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def write_embeds(embeds):
    with _embeds_lock:
        tmp = EMBEDS_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"version": 1, "embeds": embeds}, fh, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)                     # key hashes
        os.replace(tmp, EMBEDS_PATH)


def hash_key(secret, salt=None):
    """Plain SHA-256 over a salt, not the PBKDF2 the passwords get. This
    secret is 32 bytes from the system generator rather than something a human
    chose, so there is no dictionary to run and stretching would only buy a
    third of a second of latency on every session a host mints."""
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.sha256(salt + secret.encode()).hexdigest()
    return salt.hex(), dk


def embed_key_blocked(ip):
    rec = _embed_fails.get(ip)
    return bool(rec and rec[1] > time.time())


def note_embed_failure(ip):
    """Same geometric back-off as the sign-in, kept in its own ledger: a host
    server fumbling its key must not lock an admin out of the panel."""
    rec = _embed_fails.setdefault(ip, [0, 0])
    rec[0] += 1
    if rec[0] >= 5:
        rec[1] = time.time() + min(300, 15 * (2 ** (rec[0] - 5)))


def normalise_origin(raw):
    """scheme://host[:port], nothing else. An origin with a path or a trailing
    slash silently fails to match `e.origin` in a browser, and the failure
    looks like a broken embed rather than a typo in a text box."""
    # Lowercased before matching, not after: a scheme and a host are
    # case-insensitive, and somebody pasting from an address bar should not
    # have their own origin rejected for a capital letter.
    s = (raw or "").strip().rstrip("/").lower()
    if not s:
        return None
    m = re.fullmatch(r"https?://([a-z0-9.\-]+|\[[0-9a-f:]+\])(:\d{1,5})?", s)
    return m.group(0) if m else None


def validate_embed(obj):
    """Returns (record, error). Incoherent arrangements are refused HERE, in
    front of the admin creating them, naming the orphaned part — rather than
    left for a host developer to read out of a 400 three weeks later."""
    name = str(obj.get("name") or "").strip()[:64]
    if not name:
        return None, "give it a name — the admin list is unreadable without one"

    preset = str(obj.get("preset") or "custom")
    if preset != "custom" and preset not in PRESETS:
        return None, "no preset called '%s'" % preset

    raw_parts = obj.get("parts")
    if raw_parts is None and preset in PRESETS:
        raw_parts = PRESETS[preset]["parts"]
    if not isinstance(raw_parts, list):
        return None, "parts must be a list"
    parts = [p for p in PARTS if p in raw_parts]          # canonical order
    unknown = sorted(set(map(str, raw_parts)) - set(PARTS))
    if unknown:
        return None, "no such part: %s" % ", ".join(unknown)

    cap = dict(CAP_DEFAULTS)
    if preset in PRESETS:
        cap.update(PRESETS[preset]["cap"])
    given = obj.get("cap")
    if given is not None:
        if not isinstance(given, dict):
            return None, "cap must be an object"
        for k in ("ask", "mic", "speak"):
            if k in given:
                cap[k] = bool(given[k])
        if "rate_per_min" in given:
            try:
                cap["rate_per_min"] = int(given["rate_per_min"])
            except (TypeError, ValueError):
                return None, "the rate limit must be a whole number"
    if not (1 <= cap["rate_per_min"] <= 600):
        return None, "the rate limit must be between 1 and 600 a minute"

    err = incoherent(parts, cap)
    if err:
        return None, err

    origins = []
    for raw in (obj.get("origins") or []):
        o = normalise_origin(raw)
        if not o:
            return None, ("'%s' is not an origin — it wants scheme://host, "
                          "optionally a port, and nothing after that" % raw)
        if o not in origins:
            origins.append(o)
    if not origins:
        return None, ("list at least one origin allowed to frame this — an "
                      "embed with no allow-list is one any site can frame")

    try:
        ttl = int(obj.get("ttl_minutes") or EMBED_TTL_DEFAULT)
    except (TypeError, ValueError):
        return None, "the session length must be a whole number of minutes"
    if not (EMBED_TTL_MIN <= ttl <= EMBED_TTL_MAX):
        return None, ("the session length must be between %d and %d minutes"
                      % (EMBED_TTL_MIN, EMBED_TTL_MAX))

    return {"name": name, "preset": preset, "parts": parts, "cap": cap,
            "origins": origins, "ttl_minutes": ttl}, None


def incoherent(parts, cap):
    """The orphaned-part rules, named one at a time. Each of these is a
    control that cannot do anything, or a permission with no way to exercise
    it — and every one of them looks like a bug to whoever meets it."""
    has = set(parts)
    if "text" in has and "transcript" not in has:
        return ("'text' toggles the transcript, and there is no transcript "
                "here for it to toggle")
    if "mode" in has and "talk" not in has:
        return ("'mode' configures how a microphone decides you have finished "
                "speaking, and this arrangement has no microphone control")
    if ("talk" in has or "mode" in has) and not cap["mic"]:
        return ("'talk' is a microphone button on a token that is not allowed "
                "a microphone — grant the microphone or drop the control")
    if "audio" in has and not cap["speak"]:
        return ("'audio' mutes a voice, and this token is not allowed to "
                "speak")
    if ("input" in has or "talk" in has) and not cap["ask"]:
        return ("there is a way to ask here, on a token that is not allowed "
                "to ask — grant it, or drop 'input' and 'talk'")
    if "input" in has and "transcript" not in has and not cap["speak"]:
        return ("'input' types into a void: nothing here reads the answer out "
                "and there is no transcript to read it in")
    if not parts and not cap["speak"]:
        return "this draws nothing and says nothing"
    return None


def embed_allowed(embed_id, per_min):
    """Per token rather than per address, because one host application behind
    one address is exactly the case the address-based window gets wrong."""
    now_ = time.time()
    with _ask_lock:
        hits = [t for t in _embed_hits.get(embed_id, []) if now_ - t < 60]
        if len(hits) >= per_min:
            _embed_hits[embed_id] = hits
            return False
        hits.append(now_)
        _embed_hits[embed_id] = hits
        return True


def new_embed_session(embed_id, rec):
    """The grant is COPIED into the session, so editing or deleting the token
    cannot retroactively widen a session already running — and a narrowing
    takes effect on the next mint rather than mid-conversation."""
    token = secrets.token_urlsafe(32)
    with _embed_sessions_lock:
        now_ = time.time()
        for t in [t for t, s in _embed_sessions.items() if s["expires"] < now_]:
            _embed_sessions.pop(t, None)         # sweep, so it cannot grow forever
        _embed_sessions[token] = {
            "id": embed_id, "name": rec["name"],
            "parts": list(rec["parts"]), "cap": dict(rec["cap"]),
            "origins": list(rec["origins"]),
            "expires": now_ + rec["ttl_minutes"] * 60,
        }
    return token


def get_embed_session(token):
    """Fixed expiry, not the sliding one a sign-in gets: this is a bearer
    token sitting in a URL inside somebody else's page, and it should stop
    working at a time the admin chose rather than for as long as it is used."""
    if not token:
        return None
    with _embed_sessions_lock:
        s = _embed_sessions.get(token)
        if not s:
            return None
        if s["expires"] < time.time():
            _embed_sessions.pop(token, None)
            return None
        return dict(s)


def drop_embed_sessions(embed_id):
    """Revoking a key must not leave live sessions carrying its grant."""
    with _embed_sessions_lock:
        for t in [t for t, s in _embed_sessions.items() if s["id"] == embed_id]:
            _embed_sessions.pop(t, None)


#: What the assistant's transcript label used to ship as. An install that
#: still holds this exact word is holding the old default rather than a
#: choice: it was the shipped value back when there was one assistant to
#: name, and it attributes every answer to that one name now that there are
#: several. Carried forward to the variable, which renders identically on a
#: single endpoint of that name and correctly once there is a second.
OLD_AINAME = "resonance"


def read_settings():
    try:
        with open(SETTINGS_PATH) as fh:
            stored = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(stored, dict):
        return {}
    # Rewritten on the way out rather than on disk: nothing is lost if this
    # turns out to be wrong, and it persists by itself the next time an admin
    # saves the tab it lives on.
    if stored.get("ainame") == OLD_AINAME:
        stored["ainame"] = "{assistant}"
    return stored


def write_settings(obj):
    """Whole-document replace, written atomically so a crash mid-write can
    never leave every viewer with a truncated config."""
    with _settings_lock:
        tmp = SETTINGS_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True)
        os.replace(tmp, SETTINGS_PATH)
# small.en over base.en: measurably better on technical vocabulary
# ("core switch uplink" vs base.en's "course which uplink") for ~1.5s
# instead of ~0.5s on 6 CPU cores. Override with STT_MODEL.
MODEL_NAME = os.environ.get("STT_MODEL", "small.en")
MAX_UPLOAD = 12 * 1024 * 1024        # ~12MB of opus is minutes of speech

# Every model faster-whisper knows how to fetch, because there is no way to
# know from here what somebody is running this on. Four of these are sensible
# on the reference box and the rest are for hardware it has never seen; the
# aliases (`large` for large-v2, `turbo` for large-v3-turbo) are deliberately
# left out, since a list offering the same weights twice under two names is a
# choice nobody can make correctly.
#
# CAUTION, and it is stated in the panel too: a model that is not on disk is
# DOWNLOADED on first use — up to ~1.6GB, inside the first request that asks
# for it, from a box that may have no route to the internet. The failure is
# visible rather than silent (the display's status line carries the error),
# but the wait is real and belongs to whoever is standing there.
#
# The `.en` models are English-only and better at English than the
# multilingual model of the same size. Choosing a multilingual one is what
# makes this transcribe anything other than English at all.
ALLOWED = (
    # English-only, smallest first
    "tiny.en", "base.en", "distil-small.en", "small.en",
    "distil-medium.en", "medium.en",
    # multilingual
    "tiny", "base", "small", "medium",
    "large-v1", "large-v2", "large-v3", "large-v3-turbo",
    "distil-large-v2", "distil-large-v3",
)
_models = {}
_model_err = None
_model_lock = threading.Lock()


def get_model(name=None):
    """Load once per model, on first use. Several may be resident at once so
    the user can trade speed against accuracy without a restart — base.en is
    ~75MB and small.en ~250MB at int8, which this box can hold easily."""
    global _model_err
    name = name if name in ALLOWED else MODEL_NAME
    if name in _models:
        return _models[name]
    with _model_lock:
        if name not in _models:
            try:
                from faster_whisper import WhisperModel
                t0 = time.time()
                _models[name] = WhisperModel(name, device="cpu",
                                             compute_type="int8", cpu_threads=0)
                print("STT model %s ready in %.1fs" % (name, time.time() - t0),
                      flush=True)
            except Exception as exc:                       # noqa: BLE001
                _model_err = str(exc)
                print("STT unavailable (%s): %s" % (name, _model_err), flush=True)
                return None
    return _models.get(name)


_SUPPORTS_HOTWORDS = None

# ---------------------------------------------------------------- neural TTS
VOICE_DIR = os.path.join(ROOT, "voices")
_voices = {}
_voice_lock = threading.Lock()


def voice_list():
    if not os.path.isdir(VOICE_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(VOICE_DIR) if f.endswith(".onnx"))


def get_voice(name):
    """Piper voices are small enough to keep several resident; loading takes
    about a second, which you do not want in the middle of a reply."""
    if name not in voice_list():
        return None
    if name in _voices:
        return _voices[name]
    with _voice_lock:
        if name not in _voices:
            from piper import PiperVoice
            t0 = time.time()
            _voices[name] = PiperVoice.load(os.path.join(VOICE_DIR, name + ".onnx"))
            print("TTS voice %s ready in %.1fs" % (name, time.time() - t0), flush=True)
    return _voices[name]


def synth(text, name, rate=1.0):
    """`rate` is a speed multiplier to match the browser engine's meaning.
    Piper expresses it as length_scale, which is the inverse — a longer
    utterance means slower speech."""
    import io, wave
    v = get_voice(name)
    if v is None:
        raise RuntimeError("no such voice: %s" % name)
    cfg = None
    try:
        rate = max(0.5, min(2.0, float(rate)))
    except (TypeError, ValueError):
        rate = 1.0
    if abs(rate - 1.0) > 0.01:
        try:
            from piper import SynthesisConfig
            cfg = SynthesisConfig(length_scale=1.0 / rate)
        except Exception:                                  # noqa: BLE001
            cfg = None
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        if cfg is not None:
            v.synthesize_wav(text, w, syn_config=cfg)
        else:
            v.synthesize_wav(text, w)
    return buf.getvalue()


def transcribe(raw, suffix, hint=None, model_name=None):
    """`hint` biases the decoder toward vocabulary it would otherwise
    mishear. CAUTION: a hinted word is frequently omitted from the output —
    the decoder treats it as context already supplied. That makes hints
    useless for wake words (measured) but still useful for domain terms you
    only need spelled correctly when they do appear."""
    global _SUPPORTS_HOTWORDS
    model = get_model(model_name)
    if model is None:
        raise RuntimeError(_model_err or "model not loaded")
    if _SUPPORTS_HOTWORDS is None:
        try:
            _SUPPORTS_HOTWORDS = "hotwords" in inspect.signature(model.transcribe).parameters
        except (TypeError, ValueError):
            _SUPPORTS_HOTWORDS = False
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fh:
            fh.write(raw)
            path = fh.name
        # The browser already decided where this utterance starts and ends,
        # so whisper's own VAD is a second gate that can only trim a short
        # word away. Thresholds are relaxed for the same reason: a single
        # spoken wake word scores high on "probably silence" and would be
        # discarded at the defaults, which reads as the word simply not
        # being recognised.
        # Tuned by measurement on a bare one-word utterance, the hardest
        # case. beam_size=1 beat 2 and 5 on accuracy AND speed here; the
        # temperature fallback only added latency. Relaxed thresholds are
        # the important part — at the defaults a lone spoken word scores as
        # "probably silence" and gets discarded, which reads as the word
        # simply not being recognised.
        kw = dict(
            language="en", beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
            no_speech_threshold=0.90,
            log_prob_threshold=-2.0,
        )
        # hotwords ONLY. initial_prompt makes the decoder treat the hint as
        # already-spoken context and it then omits the word from the output —
        # which silently breaks wake-word matching, the exact thing the hint
        # was meant to help.
        if hint and _SUPPORTS_HOTWORDS:
            kw["hotwords"] = hint
        segments, _info = model.transcribe(path, **kw)
        return "".join(seg.text for seg in segments).strip()
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


SESSION_COOKIE = "rsn_sid"
ADMIN_ONLY_FILES = ("/admin.html",)
#: exist only on the admin listener; anywhere else they are simply not there.
#: Note what is NOT here: /routes, the public half of the route document,
#: which every display must be able to read. Everything privileged about a
#: route lives under /routes/… precisely so this list can be a list of paths
#: rather than a list of paths and methods.
ADMIN_ONLY_ROUTES = ("/users", "/users/delete", "/users/role", "/app",
                     "/routes/all", "/routes/new", "/routes/save",
                     "/routes/delete", "/routes/enable", "/routes/default",
                     "/routes/test",
                     "/embeds", "/embeds/delete", "/embeds/enable",
                     # …and note what is NOT here either: /display/hello, which
                     # is how a display gets its token and therefore has to be
                     # reachable from the listener a display is served on.
                     # Everything an ADMIN does to a display sits under
                     # /displays, one letter and a whole boundary apart.
                     "/displays", "/displays/approve", "/displays/rename",
                     "/displays/delete", "/displays/new", "/displays/reissue",
                     "/displays/decide", "/displays/settings", "/displays/kiosk",
                     "/groups", "/groups/save", "/groups/delete", "/groups/sets",
                     "/log", "/alerts", "/alerts/ack",
                     "/events", "/events/clear",
                     "/identities/wake", "/identities/wake/check",
                     "/identities", "/identities/new", "/identities/rename",
                     "/identities/delete", "/identities/reissue")
#: where an enrolment code is typed. On the display listeners only — it hands
#: out a display's token, and the admin listener is not a display.
ENROL_PREFIX = "/e/"
#: where a person's minted URL is spent. On the display listeners only, and for
#: the same reason /display/hello is: it hands out an identity's cookie, and
#: the admin listener is not somewhere anybody stands and uses this. Everything
#: an ADMIN does to an identity sits under /identities, well away from it.
PERSON_PREFIX = "/p/"
#: the other half of the embed API: reachable from the display listeners,
#: because that is where a host server and a host browser can actually get to
EMBED_ROUTES = ("/embed", "/embed/session")


#: Every file this server will hand out, and there are four of them. An
#: ALLOW-list, because the alternative was tried and failed: the directory
#: `serve.py` runs from is a deployment, not a document root, and the base
#: class will serve anything sitting in it. What was sitting in it was the
#: TLS private key, the accounts and their password hashes, the assistant's
#: API keys, the log and the source — all of it 200 OK, unauthenticated, on a
#: listener bound to every interface.
#:
#: A list of things to hide could never have been right. `routes.json` is the
#: proof: it did not exist yet when such a list would have been written, and
#: it arrived holding one credential per route. The next file to land beside
#: these will not be foreseen either, so the default has to be no.
#:
#: admin.html is here because the admin listener serves it; the earlier
#: ADMIN_ONLY_FILES check has already made it absent everywhere else.
SERVABLE = frozenset(("/index.html", "/admin.html", "/icon.svg", "/lockup.svg"))


def servable(path):
    """Exact match on the path with its query stripped. Deny-by-default gets
    traversal and percent-encoding for nothing: `/docs/../key.pem` and
    `/%6bey.pem` are simply not in the set, so neither needs its own rule."""
    return path.split("?")[0] in SERVABLE


class Handler(SimpleHTTPRequestHandler):
    #: set per-listener by make_server — the admin port is a different surface
    #: with different rules, not the same surface with an extra check
    admin_port = False

    #: set per-listener by make_server: the HTTPS port this listener sends
    #: callers to instead of answering. None means it answers normally.
    redirect_to = None

    #: set per-listener by make_server: the network profile this port belongs
    #: to. Blank is the admin listener, which is not a display port and
    #: answers about all of them.
    pinned_net = ""

    def __init__(self, *args, admin_port=False, redirect_to=None,
                 pinned_net="", **kw):
        # must land before super().__init__, which serves the request outright
        self.admin_port = admin_port
        self.redirect_to = redirect_to
        self.pinned_net = pinned_net
        super().__init__(*args, **kw)

    def _redirected(self):
        """The plain listener, once HTTPS is the only real way in. Kept as a
        redirect rather than deleted, or every bookmark, kiosk startup URL and
        printed QR code pointing at it dies silently on the day it changes.

        307 rather than a permanent 301/308, deliberately and against the
        original note. The target is configuration an admin can change — the
        HTTPS port, or the binding itself — and a permanent redirect is cached
        by the browser indefinitely. Switching a machine back to a personal
        install would leave every browser that had ever visited redirecting to
        a port nothing answers on, unfixable from this end and curable only by
        the user clearing site data by hand. 307 keeps the bookmark working,
        which is the entire reason for not deleting the listener, and costs one
        redirect per visit."""
        if not self.redirect_to:
            return False
        host = self.headers.get("Host") or RUNNING.get("bind_host") or LOOPBACK
        host = re.sub(r":\d+$", "", host)       # its port, not the one we want
        self.send_response(307)
        self.send_header("Location", "https://%s:%d%s"
                                     % (host, self.redirect_to, self.path))
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    #: set for one response by the /embed route, so the file the base class
    #: serves carries the frame-ancestors line without rewriting its HTML
    _csp = None

    # ---------- no-cache ----------
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        if self._csp:
            self.send_header("Content-Security-Policy", self._csp)
            # X-Frame-Options cannot express a list, and where both are present
            # frame-ancestors wins in every browser that implements it. Sending
            # a lying DENY beside it only confuses whoever reads the headers.
        super().end_headers()

    def send_header(self, keyword, value):
        # drop the validator that lets a browser answer from cache
        if keyword.lower() == "last-modified":
            return
        super().send_header(keyword, value)

    def log_message(self, fmt, *args):
        line = fmt % args
        # An embed session token is a bearer credential, and it rides in the
        # URL. Anything with read access to the log would otherwise be able to
        # take over a live embed session by pasting one line of it.
        line = re.sub(r"([?&]t=)[^&\s\"]+", r"\1…", line)
        sys.stderr.write("%s %s\n" % (self.address_string(), line))

    # ---------- json helper ----------
    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---------- identity ----------
    def _session(self, slide=True):
        """Who is calling, or None. Only ever consulted on the admin port —
        a cookie replayed at the public listeners buys nothing, because those
        listeners have no privileged route to reach."""
        if not self.admin_port:
            return None
        # NO BYPASS. There used to be one: with sign-in set to nothing this
        # returned a synthetic admin and everyone who could reach the listener
        # was one. The setting still exists and still means something — it
        # governs whether a PERSON has to sign in at a display — but it no
        # longer reaches this door.
        #
        # This interface holds the assistant's API key, every credential the
        # server stores, and the power to grant anybody access to anything. A
        # configuration switch that opens it is a switch that gets left on: it
        # was defensible only while "the network is the boundary" stayed true,
        # and it stays true right up until the laptop joins another network.
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        try:
            jar = http.cookies.SimpleCookie(raw)
        except http.cookies.CookieError:
            return None
        morsel = jar.get(SESSION_COOKIE)
        return get_session(morsel.value, slide) if morsel else None

    def _require(self, role=None):
        """Returns the session, or answers 401/403 and returns None. `role`
        of "admin" demands it; None accepts any signed-in account."""
        s = self._session()
        if not s:
            self._json(401, {"error": "not signed in"})
            return None
        if role == "admin" and s["role"] != "admin":
            self._json(403, {"error": "this account is read-only"})
            return None
        return s

    def _embed(self):
        """The embed session this call carries, or None. A bearer header
        rather than a cookie, deliberately: a cookie set by an iframe is a
        third-party cookie, and browsers block or partition those — an embed
        that works in one browser and silently fails in the next is the worst
        possible shape for this. It also leaves nothing ambient to forge, so
        there is no CSRF question to answer."""
        raw = self.headers.get("Authorization") or ""
        if not raw.lower().startswith("bearer "):
            return None
        return get_embed_session(raw[7:].strip())

    def _cap(self, want):
        """Returns (session_or_None, refused). A call with no embed session is
        an ordinary visitor at the display and is not this method's business —
        the capability envelope narrows an embed, it does not gate the URL
        anyone can already open."""
        s = self._embed()
        if not s:
            return None, False
        if not s["cap"].get(want):
            self._json(403, {"error": "this embed is not permitted to %s"
                                      % {"ask": "ask", "mic": "use a microphone",
                                         "speak": "speak"}[want]})
            return s, True
        return s, False

    def _display(self):
        """Which display is calling, or None. The cookie is HttpOnly, so page
        script genuinely cannot read it — and `curl` does not have it at all,
        which is the difference between this and a name in a URL."""
        if self.admin_port:
            # The panel's live preview frames this page. It is not a display;
            # it is an admin looking at one, and it is already signed in.
            return dict(PREVIEW_DISPLAY) if self._session() else None
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        try:
            jar = http.cookies.SimpleCookie(raw)
        except http.cookies.CookieError:
            return None
        morsel = jar.get(DISPLAY_COOKIE)
        return find_display(morsel.value) if morsel else None

    def _identity(self):
        """Which person is calling, or None. Same mechanism as `_display`, in a
        cookie of its own — and a browser may hold both, because somebody can
        have opened a display URL on the machine they later spend their own URL
        on. Which of the two a request IS is decided by the URL, not by what is
        in the jar: see the precedence at /display/hello."""
        if self.admin_port:
            # The panel's live preview is an admin looking at a display. It is
            # not somebody's personal session and must never borrow one.
            return None
        # SIGNED IN BEATS EVERYTHING. A session was proved with a password, on
        # this browser, and it is the only thing here that reaches a person who
        # never opened a setup link on this machine — which is the whole point
        # of there being a login at all.
        pid = self._user_pid()
        if pid:
            rec = read_identities().get(pid)
            if rec:
                return dict(rec, id=pid)
        # AND NOTHING ELSE. There was a fallback to the setup cookie — who
        # this browser CLAIMS to be, from having spent a minted link here once
        # — used wherever sign-in was switched off deployment-wide. That switch
        # is gone, and with per-endpoint requirements the fallback was worse
        # than redundant: an endpoint that insists on a person would have
        # accepted a cookie nobody proved, and inherited that person's grants
        # without a password.
        #
        # The setup cookie still exists and still means something. It is read
        # in exactly one place — /user/setup — where it is the claim being
        # spent, and it buys the password box and nothing else.
        return None

    def _subject(self):
        """Which caller this request IS: `(display, identity)`, never both.

        The precedence `/display/hello` applies, in the other two places it
        matters. An approved display is a device whatever else is in the cookie
        jar — a kiosk stays a kiosk, which is the whole of why signing a person
        into one is refused at the door. Below that line a person's cookie wins
        over a token nobody approved, because such a token is somebody who once
        opened this page rather than a screen anybody hung.

        Returning a pair rather than a tagged object because both callers want
        to pass them straight through to `subject_may`, and a wrapper would be
        unpacked at every one of them."""
        disp = self._display()
        if disp and disp.get("approved"):
            return disp, None
        ident = self._identity()
        if ident:
            return None, ident
        return disp, None

    def _user_pid(self):
        """Which person this browser has SIGNED IN as, or "". Read straight
        from the jar and never through `_identity`, which calls this — the two
        would otherwise recurse."""
        raw = self.headers.get("Cookie")
        if not raw or self.admin_port:
            return ""
        try:
            jar = http.cookies.SimpleCookie(raw)
        except http.cookies.CookieError:
            return ""
        m = jar.get(USER_COOKIE)
        return user_session_pid(m.value) if m else ""

    def _set_user_cookie(self, token, hours):
        bits = ["%s=%s" % (USER_COOKIE, token), "Path=/", "HttpOnly",
                "SameSite=Strict", "Max-Age=%d" % int(hours * 3600)]
        if isinstance(self.connection, ssl.SSLSocket):
            bits.insert(3, "Secure")
        self.send_header("Set-Cookie", "; ".join(bits))

    def _set_identity_cookie(self, token):
        # Same reasoning as the display cookie: Secure only where the
        # connection actually is, because bound to loopback this server is the
        # whole product over plain HTTP and a cookie the browser refused to
        # store would leave a personal install unable to hold an identity.
        bits = ["%s=%s" % (IDENTITY_COOKIE, token), "Path=/", "HttpOnly",
                "SameSite=Strict", "Max-Age=%d" % IDENTITY_MAX_AGE]
        if isinstance(self.connection, ssl.SSLSocket):
            bits.insert(3, "Secure")
        self.send_header("Set-Cookie", "; ".join(bits))

    def _display_state(self, rec):
        """Everything the display page needs to know about itself, in one
        object: whether it may use anything, whether it may ask, what the form
        asks, and — where it was refused — what it was told.

        Built once and returned from every path that touches a display, so the
        page never has to assemble its own state from two half-answers."""
        cfg = display_settings()
        expired = display_expired(rec)
        working = bool(rec.get("approved")) and not expired
        # Refused, and told so; waiting on a decision; running on a grant that
        # has run out; or simply here, with whatever is open to everyone.
        # SETUP OUTRANKS EVERYTHING. A row carrying one has been approved
        # into an account, and the only thing left for this browser to do is
        # go and choose a password. It is not `approved` — nothing was granted
        # to the device — so without its own state it would read as still
        # waiting, on a screen whose answer has already arrived.
        state = ("setup" if rec.get("setup")
                 else "denied" if rec.get("denied")
                 else "expired" if expired
                 else "approved" if working
                 else "requested" if rec.get("requested_at")
                 else "none")
        may_ask = (cfg["guest_requests"] and not working
                   and not (rec.get("denied") and not rec.get("deny_repeat", True)))
        out = {"id": rec.get("id", ""), "name": display_label(rec),
               "approved": working, "state": state,
               "can_request": bool(may_ask),
               # Where to go and choose a password. The path only, built the
               # same way the panel builds it — the secret is in it, and it
               # goes out over the token that asked and to nobody else.
               "setup_url": (PERSON_PREFIX + rec["setup"]) if rec.get("setup")
                            else "",
               # A renewal does not ask the form again — what they told you is
               # already on the row, and making somebody retype it every month
               # is how a form stops being answered honestly.
               "answered": bool(rec.get("answers")),
               "renewals": rec.get("renewals") or 0,
               # …and what this place looks like. Sent whatever the state is:
               # a tablet nobody has approved yet is still a tablet on a wall,
               # and the panel that has not been opened is exactly the case
               # where a screen sits burning an image into itself. It is also
               # this display's own row and nobody else's, so there is nothing
               # here to leak — it went out through the token that asked.
               "kiosk": kiosk_of(rec)}
        if may_ask:
            out["form"] = cfg["form"]
        if rec.get("denied"):
            # Only the message written FOR them. The internal note is for
            # whoever comes to this row in six months, and never leaves here.
            out["reason"] = rec.get("deny_reason") or ""
            out["may_ask_again"] = bool(rec.get("deny_repeat", True))
        if working and rec.get("expires"):
            out["expires_in"] = max(0, int(rec["expires"] - time.time()))
        return out

    def _set_display_cookie(self, token):
        # Secure only where the connection actually is: bound to loopback this
        # server is the whole product over plain HTTP, and a cookie a browser
        # refuses to store there would leave a personal install unable to hold
        # an identity at all. Everywhere else the plain listener redirects to
        # HTTPS, so this is set on the secure one either way.
        bits = ["%s=%s" % (DISPLAY_COOKIE, token), "Path=/", "HttpOnly",
                "SameSite=Strict", "Max-Age=%d" % DISPLAY_MAX_AGE]
        if isinstance(self.connection, ssl.SSLSocket):
            bits.insert(3, "Secure")
        self.send_header("Set-Cookie", "; ".join(bits))

    def _same_origin(self):
        """Every state-changing call must come from this interface itself.
        Belt and braces over SameSite=Strict, which older browsers ignore."""
        origin = self.headers.get("Origin")
        if not origin:
            return True                      # non-browser client, no ambient cookie
        host = self.headers.get("Host") or ""
        return origin.split("//")[-1] == host

    def _set_cookie(self, token, clear=False):
        # Secure is unconditional: the admin listener is HTTPS-only by design
        bits = [
            "%s=%s" % (SESSION_COOKIE, "" if clear else token),
            "Path=/", "HttpOnly", "Secure", "SameSite=Strict",
            "Max-Age=0" if clear else "Max-Age=%d" % SESSION_IDLE,
        ]
        self.send_header("Set-Cookie", "; ".join(bits))

    # ---------- routes ----------
    def do_HEAD(self):
        if self._redirected():
            return
        # The same allow-list as GET. A HEAD that confirms key.pem is there is
        # a disclosure of its own, and it is the cheap way to go looking.
        if not servable(self.path):
            return self._json(404, {"error": "not found"})
        return super().do_HEAD()

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        self._csp = None            # one connection can serve several requests
        if self._redirected():
            return
        path = self.path.split("?")[0]
        # The configuration interface does not exist as far as the public
        # listeners are concerned — not hidden by CSS, not gated in JS, absent.
        # Answering 401 here would still confirm the route is there; 404 is
        # the honest answer, because on this listener it genuinely is not.
        if not self.admin_port and (path in ADMIN_ONLY_FILES
                                    or path in ADMIN_ONLY_ROUTES
                                    # A PREFIX, not a list, and it is the list
                                    # above that is the belt. Adding
                                    # /displays/kiosk and forgetting to name it
                                    # there left one admin route answering 401
                                    # on a listener where every one of its
                                    # siblings answers 404 — which is the route
                                    # announcing it exists. The next one added
                                    # is covered whether anybody remembers or
                                    # not. `/display/hello` is one letter and a
                                    # whole boundary away, and unaffected.
                                    or path.startswith("/displays/")
                                    # Same belt-and-braces as /displays/ above,
                                    # applied when the section was new rather
                                    # than after one of its routes announced
                                    # itself with a 401. `/p/` is one letter
                                    # and a whole boundary away, and unaffected.
                                    or path.startswith("/identities/")
                                    or path.startswith("/auth/")
                                    or path == "/docs"
                                    or path.startswith("/docs/")):
            return self._json(404, {"error": "not found"})

        # Documentation. Signed in, but NOT admin-only: a viewer can read the
        # configuration, so a viewer should be able to read what it means —
        # and the user guide is written for people with no account at all.
        if path == "/docs":
            if not self._require():
                return
            return self._json(200, {"docs": manual.doc_index()})
        if path == "/docs/search":
            # Ahead of the /docs/<id> lookup below, which would take "search"
            # for a document id and answer 404. It costs one reserved id in a
            # registry we own, and keeps the search under the path it searches
            # rather than off in a name of its own.
            if not self._require():
                return
            q = (parse_qs(urlparse(self.path).query).get("q") or [""])[0]
            return self._json(200, {"q": q, "results": manual.search(q),
                                    "min": manual.SEARCH_MIN})
        if path.startswith("/docs/"):
            if not self._require():
                return
            name = path[len("/docs/"):]
            want_pdf = name.endswith(".pdf")
            doc_id = name[:-4] if want_pdf else name
            entry = manual.DOC_BY_ID.get(doc_id)
            md = manual.read_doc(doc_id) if entry else None
            if md is None:
                return self._json(404, {"error": "no such document"})
            if not want_pdf:
                return self._json(200, {"doc": dict(entry, body=md)})
            try:
                blob = manual.render_pdf(entry["title"], md, entry["summary"])
            except Exception as exc:                       # noqa: BLE001
                print("pdf failed for %s: %s" % (doc_id, exc), flush=True)
                return self._json(500, {"error": "could not build the PDF"})
            # A filename the operating system will not argue with, and an
            # attachment disposition so it saves rather than opening in a
            # viewer tab the admin then has to save from again.
            fname = "resonance-%s.pdf" % re.sub(r"[^a-z0-9]+", "-",
                                                entry["title"].lower()).strip("-")
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(blob)))
            self.send_header("Content-Disposition",
                             'attachment; filename="%s"' % fname)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return self.wfile.write(blob)
        # The embed exists on the display listeners only. On the admin port it
        # is genuinely absent — that listener serves one page to one signed-in
        # operator, and framing it anywhere is not a thing to support.
        if path in EMBED_ROUTES and self.admin_port:
            return self._json(404, {"error": "not found"})

        if path == "/embed/session":
            # What the frame asks for itself, holding the token its host
            # server was given. The grant, never the key.
            s = self._embed()
            if not s:
                return self._json(401, {"error": "no valid embed session"})
            return self._json(200, {"embed": {
                "name": s["name"], "parts": s["parts"], "cap": s["cap"],
                "origins": s["origins"],
                "expires_in": max(0, int(s["expires"] - time.time())),
            }})

        if path.startswith(ENROL_PREFIX):
            # An enrolment code, typed into the screen being enrolled. A GET,
            # because it arrives as a URL somebody entered with a remote — and
            # it is one use, so the replay a GET usually invites cannot happen
            # twice.
            if self.admin_port:
                return self._json(404, {"error": "not found"})
            ip = self.address_string()
            # Every answer below is a redirect back to the display, never a
            # status code and a page of JSON. Somebody has just typed a URL into
            # a television; what they need next is the screen, with a line on it
            # saying what happened.
            def _back(state):
                self.send_response(303)
                self.send_header("Location", "/?enrol=" + state)
                self.send_header("Content-Length", "0")
                return state
            if code_blocked(ip):
                _back("blocked")
                self.end_headers()
                return
            token, out = redeem_code(path[len(ENROL_PREFIX):])
            if not token:                        # `out` is the reason
                note_code_failure(ip)
                print("enrolment code refused (%s) from %s" % (out, ip), flush=True)
                _back(out)
                self.end_headers()
                return
            _code_fails.pop(ip, None)
            file_display(out["id"])
            print("display %s (%s) enrolled by code" % (out["id"], display_label(out)),
                  flush=True)
            _back("ok")
            self._set_display_cookie(token)
            self.end_headers()
            return

        if path.startswith(PERSON_PREFIX):
            # A person's minted URL, being spent. A GET, because it is a link
            # somebody was handed and clicked, and the redirect is the point
            # rather than a courtesy: it takes the secret out of the address
            # bar, so what is left in the history is a URL that no longer
            # carries anything.
            #
            # No back-off here, unlike an enrolment code. That one is six typed
            # characters and needs four rules around it to be safe; this is 32
            # bytes from the system generator, and a rate limit on guessing it
            # would be a control against nothing.
            if self.admin_port:
                return self._json(404, {"error": "not found"})
            token = path[len(PERSON_PREFIX):]
            here = self._display()
            if here and here.get("approved"):
                # A DEVICE IS A DEVICE. Signing a person into a screen several
                # people share is the middle ground this phase deliberately
                # leaves for later, and a kiosk is the case it is explicitly
                # NOT for — so it is refused where it was attempted, visibly,
                # rather than accepted here and quietly ignored on some later
                # request. The URL is not spent by this: it still works
                # everywhere it should.
                self.send_response(303)
                self.send_header("Location", "/?person=isdevice")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            rec = find_identity(token)
            # THREE ANSWERS, because the link means two different things now.
            # An account with no password is somebody arriving for the first
            # time and the page owes them the box that chooses one; an account
            # that already has one is a link that has done its job, and the way
            # in is the login form. Saying which here keeps the display page
            # from having to ask a second question to find out what just
            # happened.
            where = "bad"
            if rec:
                where = "ready" if identity_ready(rec) else "setup"
            self.send_response(303)
            self.send_header("Location", "/?person=" + where)
            self.send_header("Content-Length", "0")
            if rec:
                note_identity_seen(rec["id"])
                print("identity %s (%s) opened its link from %s (%s)"
                      % (rec["id"], identity_label(rec),
                         self.address_string(), where), flush=True)
                # Set either way. On the setup path it is the claim /user/setup
                # reads; on the other it costs nothing, because a claim without
                # a sign-in reaches nothing wherever sign-in is required.
                self._set_identity_cookie(token)
            self.end_headers()
            return

        if path == "/embed":
            token = (parse_qs(urlparse(self.path).query).get("t") or [""])[0]
            s = get_embed_session(token)
            if not s:
                # 403 rather than 404: the route is real, and an integrator
                # staring at a 404 goes looking for a deployment problem
                # instead of at the token they minted twenty minutes ago.
                return self._json(403, {"error": "this embed token is expired "
                                                 "or was never issued"})
            # The allow-list, enforced by the browser at the only moment it
            # can be: refusing to render inside a page nobody authorised.
            self._csp = "frame-ancestors " + " ".join(s["origins"])
            self.path = "/index.html"
            return super().do_GET()

        if path == "/settings":
            # public: this is what every viewer's interface is built from.
            # THE POSTURE WARNING DOES NOT RIDE ALONG. It used to, and the
            # reason it was safe was written here: "anyone who can read this
            # can already open the admin port and find out the same thing by
            # getting in." That stopped being true the day the panel started
            # always asking for a password. What was a warning shared with
            # somebody who could have looked anyway is now a description of
            # this server's exposure handed to every browser that loads a
            # display — including the ones the warning is about.
            #
            # It is still said where it can be acted on: in the panel, behind
            # the sign-in, and in the startup log to whoever ran the command.
            return self._json(200, {"settings": read_settings()})
        if path == "/auth/me":
            s = self._session()
            if not s:
                # WHICH DOOR. The gate cannot know whether to ask for a
                # username and a password or for one number, and guessing wrong
                # is a form somebody fills in twice.
                return self._json(401, {"error": "not signed in"})
            # The panel needs to tell "signed in as an admin" from "there is no
            # sign-in here" — they grant the same access and want different
            # words, and one of them has no account to offer or to sign out of.
            # `no_auth` is gone with the bypass: reaching here at all now
            # means somebody signed in, so there is always an account to name
            # and always something to sign out of.
            return self._json(200, {"user": s["user"], "role": s["role"]})
        if path == "/auth/check":
            # The panel's heartbeat. Deliberately does NOT slide the session:
            # a poll that renewed what it was checking would mean an open tab
            # never expired, because the check itself would be the activity.
            # It exists because a 401 on a real request only tells you the
            # session died at the moment you happen to make one, and somebody
            # reading the panel or dragging a slider makes none at all.
            s = self._session(slide=False)
            if not s:
                return self._json(401, {"error": "not signed in"})
            return self._json(200, {"alive": True})
        if path == "/routes":
            # Public, and only two thirds of a route. Presentation is what
            # makes a newly hung display look right; routing is what makes it
            # usable, and it is behind the display token — so a browser that
            # has said hello gets the words, and anything that has not gets a
            # page that draws correctly and answers to nothing. The connection
            # half is not here at all, at any tier.
            doc = read_routes()
            rows = public_routes(doc, *self._subject())
            if self.pinned_net:
                # This port carries its own endpoints and no others. They are
                # not filtered out of a list the browser then ignores — they
                # never leave here, which is the rule the connection half
                # already follows. One endpoint on an exclusive port, several
                # One endpoint per port now, so this is a list of one — kept
                # as a list because the membership is read at request time and
                # the rule is enforced at the other end, on save.
                mine = net_members(doc, self.pinned_net)
                rows = [r for r in rows if r["id"] in mine]
                # The document's own default where this port carries it, and
                # otherwise the first thing here — a port whose endpoints do
                # not include the default still has to send a typed question
                # somewhere.
                dflt = (doc["default"] if doc["default"] in mine
                        else (mine[0] if mine else ""))
                return self._json(200, {"routes": rows, "default": dflt})
            return self._json(200, {"routes": rows,
                                    "default": doc["default"]})
        if path == "/routes/all":
            if not self._require("admin"):
                return
            doc = read_routes()
            return self._json(200, {"routes": admin_routes(doc),
                                    "default": doc["default"],
                                    "providers": list(PROVIDERS),
                                    "dialects": list(OPENAI_DIALECT),
                                    "voices": voice_list(),
                                    "max_routes": MAX_ROUTES,
                                    "max_history": MAX_HISTORY})
        if path == "/displays":
            if not self._require("admin"):
                return
            # The enrolment queue when it is your own new tablet, and the early
            # warning when it is somebody trying a URL they overheard. The
            # panel sorts the two apart; the server keeps one list, because
            # they are the same kind of thing seen at different moments.
            # What somebody has to TYPE, built from the host this admin
            # actually reached the panel on — that is the name which resolves
            # for them, where a stored hostname or an interface address is a
            # guess. The port is the display's, not this listener's.
            host = re.sub(r":\d+$", "", self.headers.get("Host") or "") or LOOPBACK
            secure = RUNNING.get("https_port")
            doc = read_routes()
            return self._json(200, {"displays": admin_displays(),
                                    "settings": panel_settings(),
                                    "limits": DISPLAY_LIMITS,
                                    "max_fields": MAX_FORM_FIELDS,
                                    # Which endpoints there are to grant, and
                                    # whether an uninvited device has anywhere
                                    # to go — the panel needs the second to
                                    # explain why the switch will not move.
                                    "endpoints": [{"id": r, "name": doc["routes"][r]["name"],
                                                   "restricted": doc["routes"][r].get("restricted"),
                                                   "is_default": r == doc["default"]}
                                                  for r in route_order(doc)],
                                    "open_default": open_default(doc),
                                    # Offered rather than typed, and with the
                                    # interface beside each so an address can
                                    # be placed without going to the box.
                                    "addresses": [{"addr": a, "iface": i}
                                                  for a, i in local_interfaces()],
                                    # One base per row now: a display set up on
                                    # a network profile is typed at that
                                    # profile's address and port, so a single
                                    # base for the whole list stopped being
                                    # the truth the moment one could differ.
                                    "enrol_bases": {d["id"]: enrol_base_for(
                                        None, host, secure,
                                        display_network(d["id"], doc)[0])
                                        for d in admin_displays()},
                                    "enrol_base": "%s://%s:%d/e/"
                                                  % ("https" if secure else "http", host,
                                                     secure or RUNNING.get("http_port") or 0)})
        if path == "/groups":
            if not self._require("admin"):
                return
            # The two populations a group can be drawn from — the two FILES,
            # which is the only split that is real. Every display is offered
            # for a group of devices whatever way it enrolled; that fact is on
            # the row and says nothing about which list it may be put in.
            #
            # WORKING ONLY, which is approval AND a token. Approval alone is
            # not enough: an admin who names a screen and mints a code for it
            # has approved a row that does not exist yet as a device, and it
            # sits there `approved` with nothing behind it until somebody
            # carries the code to the television. Offering it invites a grant
            # to a screen that has never been switched on.
            #
            # The same pair the gate itself requires, and the same pair the
            # register draws its three states from: INVITED is a code waiting,
            # WAITING is a browser waiting on a decision, and neither is a
            # thing a group should be able to name. Rows join a group when they
            # start working; this is that rule at the other end of the list.
            #
            # …plus anything already IN a group, approved or not. Refusing a
            # display deliberately leaves it in whatever groups it was in — a
            # group is how you address a set of things, not a record of who is
            # currently allowed — so a refused member that stopped being
            # offered would be silently dropped by the next save of that group,
            # which is that decision being undone by a rendering detail.
            in_a_group = set()
            for rec in read_groups().values():
                if rec["kind"] in DISPLAY_GROUP_KINDS:
                    in_a_group.update(rec["members"])
            devices = [{"id": did, "label": display_label(rec),
                        "approved": bool(rec.get("approved")),
                        "arrived": enrolled_as(rec)}
                       for did, rec in sorted(read_displays().items(),
                                              key=lambda kv: display_label(kv[1]).lower())
                       if (rec.get("approved") and rec.get("hash"))
                       or did in in_a_group]
            idents = [{"id": p["id"], "label": p["label"], "approved": True}
                      for p in admin_identities()]
            return self._json(200, {"groups": admin_groups(),
                                    "devices": devices, "identities": idents,
                                    "kinds": list(GROUP_KINDS),
                                    "max": MAX_GROUPS})
        if path == "/identities/wake/check":
            # Answered as it is TYPED rather than on save. A word is refused
            # for a reason somebody has to be able to act on — "too close to
            # the house" tells them to pick another one; a form that only says
            # so after they commit tells them they wasted their time.
            if not self._require("admin"):
                return
            q = parse_qs(urlparse(self.path).query)
            word = (q.get("w") or [""])[0]
            skip = (q.get("id") or [""])[0]
            bad = check_wake_word(word, skip_pid=skip)
            return self._json(200, {"ok": not bad, "why": bad})
        if path == "/log":
            # Read through the panel rather than over SSH. Admin only, and a
            # tail rather than the file: this is a window onto a running
            # server, not a download.
            if not self._require("admin"):
                return
            q = parse_qs(urlparse(self.path).query)
            lines, cut, size = read_log_tail((q.get("q") or [""])[0][:80])
            return self._json(200, {"lines": lines, "truncated": cut,
                                    "bytes": size, "max": log_max_lines()})
        if path == "/alerts":
            if not self._require("admin"):
                return
            displays = read_displays()
            rows = []
            for a in sorted(read_alerts(), key=lambda a: (-a["last"],)):
                spec = ALERT_KINDS.get(a["kind"]) or {}
                rows.append(dict(a, words=spec.get("words", a["kind"]),
                                 label=display_label(displays[a["did"]])
                                 if a.get("did") in displays else ""))
            return self._json(200, {
                "alerts": rows,
                # The two numbers a list like this is read against: what is
                # still true, and what is over but unread.
                "open": len([a for a in rows if not a["resolved"]]),
                "unread": len([a for a in rows if a["resolved"] and not a["acked"]])})
        if path == "/events":
            # The health view's data: what each screen has been reporting, and
            # the raw tail underneath it. Per device, because the useful
            # question is which screen is failing rather than how many faults
            # there were in total.
            if not self._require("admin"):
                return
            rows = read_events()
            displays = read_displays()
            now_ = int(time.time())
            health = []
            for did in sorted(displays, key=lambda d: display_label(displays[d]).lower()):
                h = display_health(did, rows, now_)
                if h["n"]:
                    health.append(dict(h, id=did, label=display_label(displays[did])))
            return self._json(200, {
                "health": health,
                # Newest first, and bounded: this is a tail to read, not a
                # dataset to page through.
                "recent": [dict(r, label=display_label(displays[r["did"]])
                                if r.get("did") in displays else "")
                           for r in sorted(rows, key=lambda r: -r["at"])[:200]],
                # The conversation record, newest first. Bounded the same way
                # the events are: a tail to read, not a dataset to page.
                "turns": [dict(r, label=display_label(displays[r["did"]])
                               if r.get("did") in displays else "")
                          for r in sorted(read_turns(), key=lambda r: -r["at"])[:120]],
                "days": event_window_days(),
                # The sink's settings ride with the data it reports on, so the
                # panel fills that box from the same fetch rather than a second
                # one that can disagree with it.
                "settings": {k: panel_settings().get(k)
                             for k in ("syslog_on", "syslog_host",
                                       "syslog_port", "syslog_facility",
                                       "hook_on", "hook_url",
                                       "ha_on", "ha_url", "ha_service",
                                       "ha_has_token",
                                       "mail_on", "mail_host", "mail_port",
                                       "mail_tls", "mail_user", "mail_from",
                                       "mail_to", "mail_has_pass",
                                       "digest_on", "digest_minutes",
                                       "quiet_on", "quiet_from", "quiet_to")},
                "limits": {"event_days": EVENT_DAYS_LIMITS},
                "kinds": list(EVENT_KINDS), "total": len(rows)})
        if path == "/identities":
            if not self._require("admin"):
                return
            # The host the panel is being read on, for the same reason the
            # enrolment base uses it: an admin is about to hand this address to
            # somebody, so it has to be whole rather than a path they finish by
            # guessing. A stored hostname would be this server's opinion of
            # where it lives; the Host header is where somebody actually is.
            host = re.sub(r":\d+$", "", self.headers.get("Host") or "") or LOOPBACK
            secure = RUNNING.get("https_port")
            return self._json(200, {"identities": admin_identities(),
                                    "max": MAX_IDENTITIES,
                                    "pw_min": MIN_PASSWORD,
                                    "base": "%s://%s:%d%s"
                                            % ("https" if secure else "http", host,
                                               secure or RUNNING.get("http_port") or 0,
                                               PERSON_PREFIX)})
        if path == "/app":
            if not self._require("admin"):
                return
            cfg = read_app()
            # What is configured, what is actually bound, and therefore
            # whether a restart is owed. The page should never have to guess.
            # Two warnings, and they are different questions: what is stored
            # would be unsafe once applied, and what is running is unsafe now.
            return self._json(200, {"app": cfg, "running": RUNNING,
                                    "pending": app_pending(cfg),
                                    "warning": posture_warning(cfg),
                                    "running_warning": posture_warning(RUNNING),
                                    "addresses": local_addresses(),
                                    "limits": {"port_min": PORT_MIN,
                                               "port_max": PORT_MAX,
                                               "session_min": SESSION_MIN,
                                               "session_max": SESSION_MAX,
                                               "bind_modes": list(BIND_MODES),
                                               }})
        if path == "/users":
            if not self._require("admin"):
                return
            return self._json(200, {"users": [
                {"username": n, "role": u.get("role", "viewer"),
                 "created": u.get("created")}
                for n, u in sorted(read_users().items())]})
        if path == "/embeds":
            if not self._require("admin"):
                return
            live = {}
            with _embed_sessions_lock:
                now_ = time.time()
                for s in _embed_sessions.values():
                    if s["expires"] > now_:
                        live[s["id"]] = live.get(s["id"], 0) + 1
            out = []
            for eid, rec in sorted(read_embeds().items(),
                                   key=lambda kv: kv[1].get("created", 0)):
                row = {k: rec.get(k) for k in
                       ("name", "preset", "parts", "cap", "origins",
                        "ttl_minutes", "created", "created_by",
                        "last_used", "enabled")}
                row.update(id=eid, sessions=live.get(eid, 0))
                out.append(row)
            return self._json(200, {"embeds": out, "parts": list(PARTS),
                                    "presets": PRESETS,
                                    "ttl": {"min": EMBED_TTL_MIN,
                                            "max": EMBED_TTL_MAX,
                                            "default": EMBED_TTL_DEFAULT}})
        if path == "/tts/voices":
            return self._json(200, {"voices": voice_list(),
                                    "loaded": sorted(_voices.keys())})
        if path == "/stt/status":
            return self._json(200, {
                "model": MODEL_NAME,
                "loaded": sorted(_models.keys()),
                "allowed": list(ALLOWED),
                "error": _model_err,
            })
        # The root is named explicitly rather than left to the base class,
        # which would otherwise answer it with a directory listing of the
        # deployment if index.html ever went missing.
        if path == "/":
            self.path = "/admin.html" if self.admin_port else "/index.html"
        # Everything that is going to be served has been decided above. What
        # reaches here is a request for a file, and only four of those exist
        # as far as this server is concerned — see SERVABLE.
        if not servable(self.path):
            return self._json(404, {"error": "not found"})
        return super().do_GET()

    def _body(self, limit=256 * 1024):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > limit:
            return None
        return self.rfile.read(n)

    def _json_body(self):
        raw = self._body()
        if raw is None:
            self._json(400, {"error": "empty or oversized body"})
            return None
        try:
            obj = json.loads(raw)
        except ValueError:
            self._json(400, {"error": "invalid json"})
            return None
        if not isinstance(obj, dict):
            self._json(400, {"error": "expected an object"})
            return None
        return obj

    def do_POST(self):
        from urllib.parse import urlparse, parse_qs
        if self._redirected():
            return
        parsed = urlparse(self.path)

        if parsed.path.startswith("/auth/") \
                or parsed.path in ADMIN_ONLY_ROUTES or parsed.path == "/settings":
            # note: /ask is deliberately absent — the display must reach it
            if not self.admin_port:
                # Nothing privileged is reachable from the display listeners.
                return self._json(404, {"error": "not found"})
            if not self._same_origin():
                return self._json(403, {"error": "cross-origin request refused"})

        # With no sign-in there are no accounts to manage, and quietly writing
        # to users.json would leave an admin believing they had created an
        # account that nothing consults. Refuse where the mistake is made, and
        # say which setting is responsible.
        if parsed.path == "/auth/login":
            ip = self.address_string()
            if login_blocked(ip):
                return self._json(429, {"error": "too many attempts — wait a moment"})
            obj = self._json_body()
            if obj is None:
                return
            name = str(obj.get("username") or "").strip()
            users = read_users()
            u = users.get(name)
            ok = bool(u) and verify_password(str(obj.get("password") or ""),
                                             u.get("salt", ""), u.get("hash", ""))
            if not ok:
                note_login_failure(ip)
                print("failed sign-in for %r from %s" % (name, ip), flush=True)
                # never say which half was wrong
                return self._json(401, {"error": "wrong username or password"})
            clear_login_failures(ip)
            role = u.get("role", "viewer")
            token = new_session(name, role)
            body = json.dumps({"ok": True, "user": name, "role": role}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._set_cookie(token)
            self.end_headers()
            print("signed in: %s (%s)" % (name, role), flush=True)
            return self.wfile.write(body)

        if parsed.path == "/auth/logout":
            raw = self.headers.get("Cookie") or ""
            try:
                jar = http.cookies.SimpleCookie(raw)
                m = jar.get(SESSION_COOKIE)
                if m:
                    drop_session(m.value)
            except http.cookies.CookieError:
                pass
            body = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._set_cookie(None, clear=True)
            self.end_headers()
            return self.wfile.write(body)

        if parsed.path == "/auth/password":
            s = self._require()
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            users = read_users()
            target = str(obj.get("username") or s["user"])
            # anyone may change their own; only an admin may change someone else's
            if target != s["user"] and s["role"] != "admin":
                return self._json(403, {"error": "this account is read-only"})
            if target not in users:
                return self._json(404, {"error": "no such account"})
            # changing your own demands the current one, so a walk-up at an
            # unlocked browser cannot lock the owner out
            if target == s["user"]:
                cur = str(obj.get("current") or "")
                if not verify_password(cur, users[target].get("salt", ""),
                                       users[target].get("hash", "")):
                    return self._json(403, {"error": "current password is wrong"})
            new = str(obj.get("password") or "")
            if len(new) < MIN_PASSWORD:
                return self._json(400, {"error": "password must be at least %d characters"
                                                 % MIN_PASSWORD})
            salt, dk = hash_password(new)
            users[target].update({"salt": salt, "hash": dk})
            write_users(users)
            drop_sessions_for(target)          # old sessions die with the old password
            print("password changed for %s by %s" % (target, s["user"]), flush=True)
            return self._json(200, {"ok": True, "signed_out": True})

        if parsed.path == "/users":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            name = str(obj.get("username") or "").strip()
            if not valid_username(name):
                return self._json(400, {"error": "username: 2-32 chars, letters, "
                                                 "digits, dot, dash, underscore"})
            users = read_users()
            if name in users:
                return self._json(409, {"error": "that account already exists"})
            pw = str(obj.get("password") or "")
            if len(pw) < MIN_PASSWORD:
                return self._json(400, {"error": "password must be at least %d characters"
                                                 % MIN_PASSWORD})
            role = obj.get("role") if obj.get("role") in ROLES else "viewer"
            salt, dk = hash_password(pw)
            users[name] = {"salt": salt, "hash": dk, "role": role,
                           "created": int(time.time())}
            write_users(users)
            print("account created: %s (%s) by %s" % (name, role, s["user"]), flush=True)
            return self._json(200, {"ok": True, "username": name, "role": role})

        if parsed.path == "/users/delete":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            name = str(obj.get("username") or "")
            users = read_users()
            if name not in users:
                return self._json(404, {"error": "no such account"})
            # An interface nobody can administer is a brick. Refuse to remove
            # the last admin, including yourself.
            admins = [n for n, u in users.items() if u.get("role") == "admin"]
            if users[name].get("role") == "admin" and len(admins) <= 1:
                return self._json(409, {"error": "this is the only admin account"})
            users.pop(name)
            write_users(users)
            drop_sessions_for(name)
            print("account deleted: %s by %s" % (name, s["user"]), flush=True)
            return self._json(200, {"ok": True})

        if parsed.path == "/users/role":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            name, role = str(obj.get("username") or ""), obj.get("role")
            users = read_users()
            if name not in users:
                return self._json(404, {"error": "no such account"})
            if role not in ROLES:
                return self._json(400, {"error": "role must be admin or viewer"})
            admins = [n for n, u in users.items() if u.get("role") == "admin"]
            if role != "admin" and name in admins and len(admins) <= 1:
                return self._json(409, {"error": "this is the only admin account"})
            users[name]["role"] = role
            write_users(users)
            drop_sessions_for(name)            # re-sign-in picks up the new rights
            print("role of %s set to %s by %s" % (name, role, s["user"]), flush=True)
            return self._json(200, {"ok": True})

        # Creating is /routes/new rather than a POST to /routes, so that every
        # privileged path sits under a prefix and /routes itself is purely the
        # public document. One list can then hide the whole admin half from
        # the display listeners without hiding the half a display must read.
        if parsed.path in ("/routes/new", "/routes/save"):
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            doc = read_routes()
            rid = str(obj.get("id") or "")
            if parsed.path == "/routes/save":
                if rid not in doc["routes"]:
                    return self._json(404, {"error": "no such route"})
                current = doc["routes"][rid]
            else:
                if len(doc["routes"]) >= MAX_ROUTES:
                    return self._json(409, {"error": "that is %d routes — more "
                                            "names than a room can tell apart"
                                            % MAX_ROUTES})
                rid, current = None, dict(ROUTE_DEFAULTS)
            rec, err = validate_route(obj, current, doc, rid)
            if err:
                return self._json(400, {"error": err})
            if rid is None:
                rid = "r" + secrets.token_hex(4)
                rec.update(created=int(time.time()), created_by=s["user"])
            else:
                rec.update(created=current.get("created"),
                           created_by=current.get("created_by"))
            doc["routes"][rid] = rec
            # Asked of the document as it would stand, before it is written.
            # _settle_default may move the default as a consequence of this
            # edit, so the only honest question is what a guest reaches
            # afterwards — not what this field was set to.
            _settle_default(doc)
            if guest_path_broken(doc):
                return self._json(409, {"error": GUEST_PATH_MSG})
            write_routes(doc)
            # The wake word and the adapter kind, and never the key or the
            # URL it points at: a log is read by more people than the panel.
            print("route %s (%s) saved by %s: wake=%s model=%s"
                  % (rid, rec["name"], s["user"], rec["wakeword"],
                     rec.get("model_profile") or "(default)"), flush=True)
            return self._json(200, {"ok": True, "id": rid,
                                    "routes": admin_routes(doc),
                                    "default": doc["default"]})

        if parsed.path == "/routes/delete":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            doc = read_routes()
            rid = str(obj.get("id") or "")
            if rid not in doc["routes"]:
                return self._json(404, {"error": "no such route"})
            if len(doc["routes"]) <= 1:
                # Same reasoning as the last admin account. A server with no
                # route has nowhere to send a question, and the only way back
                # would be editing JSON on the box.
                return self._json(409, {"error": "this is the only route — "
                                        "make another before removing it"})
            name = doc["routes"].pop(rid)["name"]
            # Anything that fell through to it now falls through to nothing.
            # Cleared here rather than left dangling: a stored id that names
            # no route is a setting the panel cannot show and nobody can
            # correct, and the behaviour it produces — the house answering
            # "I don't understand" where it used to hand over — has no visible
            # cause.
            orphaned = [r for r, o in doc["routes"].items()
                        if o.get("fallthrough") == rid]
            for r in orphaned:
                doc["routes"][r]["fallthrough"] = ""
            _settle_default(doc)
            if guest_path_broken(doc):
                return self._json(409, {"error": GUEST_PATH_MSG})
            write_routes(doc)             # which settles the default, if it was this one
            print("route %s (%s) deleted by %s%s"
                  % (rid, name, s["user"],
                     (" — %d no longer fall through to it" % len(orphaned))
                     if orphaned else ""), flush=True)
            return self._json(200, {"ok": True, "routes": admin_routes(doc),
                                    "default": doc["default"]})

        if parsed.path == "/routes/enable":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            doc = read_routes()
            rid = str(obj.get("id") or "")
            if rid not in doc["routes"]:
                return self._json(404, {"error": "no such route"})
            on = bool(obj.get("enabled"))
            if not on and not [r for r in doc["routes"]
                               if r != rid and doc["routes"][r].get("enabled", True)]:
                return self._json(409, {"error": "this is the only route still "
                                        "answering — the display would have "
                                        "nowhere to send anything"})
            doc["routes"][rid]["enabled"] = on
            _settle_default(doc)
            if guest_path_broken(doc):
                return self._json(409, {"error": GUEST_PATH_MSG})
            write_routes(doc)
            print("route %s %s by %s" % (rid, "enabled" if on else "disabled",
                                         s["user"]), flush=True)
            return self._json(200, {"ok": True, "routes": admin_routes(doc),
                                    "default": doc["default"]})

        if parsed.path == "/routes/default":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            doc = read_routes()
            rid = str(obj.get("id") or "")
            if rid not in doc["routes"]:
                return self._json(404, {"error": "no such route"})
            if not doc["routes"][rid].get("enabled", True):
                return self._json(409, {"error": "a route that is not "
                                        "answering cannot be the default"})
            doc["default"] = rid
            if guest_path_broken(doc):
                return self._json(409, {"error": GUEST_PATH_MSG})
            write_routes(doc)
            print("default route is now %s (%s), set by %s"
                  % (rid, doc["routes"][rid]["name"], s["user"]), flush=True)
            return self._json(200, {"ok": True, "routes": admin_routes(doc),
                                    "default": doc["default"]})

        if parsed.path == "/routes/test":
            # A real round trip against one route's own connection. With
            # several of them the per-route test stops being a convenience:
            # "the assistant works" is no longer a thing that can be true or
            # false about this server as a whole.
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            doc = read_routes()
            rid = str(obj.get("id") or "")
            if rid not in doc["routes"]:
                return self._json(404, {"error": "no such route"})
            # Resolved the same way /ask resolves it: a test that asked the
            # route's own fields would be testing something no utterance uses.
            rec = with_model(doc["routes"][rid])
            if rec["provider"] == "demo":
                return self._json(200, {"demo": True, "name": rec["name"],
                                        "reply": "", "ms": 0})
            # Deliberately not a command, on a route that may be wired to a
            # house: a test button that switches something on is a test button
            # nobody presses twice.
            text = (str(obj.get("text") or "").strip()
                    or "Reply with one short sentence confirming you can hear me.")
            t0 = time.time()
            try:
                out = ask_backend(text[:500], [], rec)
            except Exception as exc:                       # noqa: BLE001
                print("route test failed (%s %s): %s"
                      % (rid, route_dest(rec), exc), flush=True)
                return self._json(502, {"error": str(exc), "name": rec["name"]})
            res = {"reply": out.get("reply") or "", "name": rec["name"],
                   "ms": int((time.time() - t0) * 1000)}
            if rec["provider"] == HOMEASSISTANT:
                # A round trip that comes back "I don't understand" is a PASS
                # here, and an admin cannot be expected to know that: the
                # built-in intent engine matches sentences, and a test
                # sentence is not one of them. What the round trip proves is
                # the address, the token and the agent — three of the four
                # things that go wrong. The fourth, whether the right entities
                # are exposed, only a real command answers.
                missed = out.get("code") == "no_intent_match"
                res["check"] = ("no command was recognised in the test "
                                "sentence, which is what the built-in intent "
                                "engine does with anything that is not one — "
                                "the address, the token and the agent are all "
                                "good. Ask it to switch something on to test "
                                "what is exposed."
                                if missed else
                                "the agent answered — address, token and agent "
                                "are all good.")
                # TEST goes down this endpoint's own connection and stops
                # there, deliberately: it is testing the house, not the chain.
                # But an admin who has just configured a fallthrough and gets
                # the house's refusal back reasonably concludes the fallthrough
                # is broken — it was read as exactly that, twice, before this
                # line existed. Say what the same sentence would do in use.
                alt = doc["routes"].get(rec.get("fallthrough") or "")
                if alt and alt.get("enabled", True):
                    res["check"] += (
                        " In use a question like this would go to %s instead — "
                        "TEST stops here on purpose, so a pass cannot come from "
                        "a different endpoint answering." % alt["name"]
                        if missed else
                        " A question it could not place would go to %s instead."
                        % alt["name"])
            return self._json(200, res)

        if parsed.path == "/embed/session":
            # A host application's SERVER calling this one. No cookie, no
            # origin check: this is not a browser and there is nothing
            # ambient to abuse. The key is the whole of the authentication.
            if self.admin_port:
                return self._json(404, {"error": "not found"})
            ip = self.address_string()
            if embed_key_blocked(ip):
                return self._json(429, {"error": "too many attempts — wait a moment"})
            obj = self._json_body()
            if obj is None:
                return
            key = str(obj.get("key") or "").strip()
            eid, _, secret = key.partition(".")
            rec = read_embeds().get(eid) if (eid and secret) else None
            try:
                ok = bool(rec) and hmac.compare_digest(
                    hash_key(secret, bytes.fromhex(rec["salt"]))[1], rec["hash"])
            except (KeyError, TypeError, ValueError):
                ok = False                        # a record edited by hand
            if not ok:
                note_embed_failure(ip)
                # One message for a bad id and a bad secret alike: telling a
                # caller which half it got right is telling it which half to
                # keep guessing at.
                return self._json(401, {"error": "that key is not recognised"})
            if not rec.get("enabled", True):
                return self._json(403, {"error": "this embed key is disabled"})
            _embed_fails.pop(ip, None)
            token = new_embed_session(eid, rec)
            rec["last_used"] = int(time.time())
            embeds = read_embeds()
            if eid in embeds:                     # re-read: another thread may have written
                embeds[eid]["last_used"] = rec["last_used"]
                write_embeds(embeds)
            print("embed session for %s (%s) — %d min" % (eid, rec["name"],
                  rec["ttl_minutes"]), flush=True)
            return self._json(200, {
                "token": token,
                "src": "/embed?t=" + token,
                "expires_in": rec["ttl_minutes"] * 60,
                "parts": rec["parts"], "cap": rec["cap"],
            })

        if parsed.path == "/embeds":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            rec, err = validate_embed(obj)
            if err:
                return self._json(400, {"error": err})
            eid = "e" + secrets.token_hex(6)
            secret = secrets.token_urlsafe(32)
            salt, dk = hash_key(secret)
            rec.update(salt=salt, hash=dk, enabled=True, last_used=None,
                       created=int(time.time()), created_by=s["user"])
            embeds = read_embeds()
            embeds[eid] = rec
            write_embeds(embeds)
            print("embed key %s (%s) created by %s: parts=%s cap=%s"
                  % (eid, rec["name"], s["user"], ",".join(rec["parts"]) or "none",
                     ",".join(k for k in ("ask", "mic", "speak") if rec["cap"][k])
                     or "none"), flush=True)
            # The only time the secret exists anywhere but in the caller's
            # hands. Nothing on this server can show it again, which is the
            # point of storing a hash — say so in the panel, loudly.
            return self._json(200, {"ok": True, "id": eid,
                                    "key": eid + "." + secret})

        if parsed.path == "/embeds/delete":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            eid = str(obj.get("id") or "")
            embeds = read_embeds()
            if eid not in embeds:
                return self._json(404, {"error": "no such embed"})
            name = embeds.pop(eid).get("name")
            write_embeds(embeds)
            drop_embed_sessions(eid)
            print("embed key %s (%s) deleted by %s" % (eid, name, s["user"]),
                  flush=True)
            return self._json(200, {"ok": True})

        if parsed.path == "/embeds/enable":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            eid = str(obj.get("id") or "")
            embeds = read_embeds()
            if eid not in embeds:
                return self._json(404, {"error": "no such embed"})
            on = bool(obj.get("enabled"))
            embeds[eid]["enabled"] = on
            write_embeds(embeds)
            if not on:
                drop_embed_sessions(eid)     # disabled means now, not at expiry
            print("embed key %s %s by %s"
                  % (eid, "enabled" if on else "disabled", s["user"]), flush=True)
            return self._json(200, {"ok": True})

        if parsed.path == "/display/hello":
            # A display announcing itself, and where a token comes from.
            #
            # Same-origin only, and that check is doing real work rather than
            # being belt and braces: with SameSite=Strict a cross-site POST
            # arrives WITHOUT the cookie, would be taken for a device nobody
            # has seen before, and would hand an approved wall tablet a fresh
            # unapproved token. That is a way to take a screen off the wall
            # from a page in another tab.
            if not self._same_origin():
                return self._json(403, {"error": "cross-origin request refused"})
            obj = self._json_body()
            if obj is None:
                return
            # Somebody else's string out of a URL, and it ends up rendered in
            # the panel — capped here as well as there.
            asked = str(obj.get("name") or "").strip()[:40]
            hint = str(obj.get("hint") or "").strip()[:120]
            if self.admin_port:
                if not self._session():
                    return self._json(401, {"error": "not signed in"})
                return self._json(200, {"display": dict(PREVIEW_DISPLAY)})
            disp = self._display()
            # A SESSION IS A USER OR A DEVICE, AND THE URL DECIDES WHICH.
            # A declared name means this browser is standing somewhere, and an
            # approved token means somebody hung it there — either way it is a
            # device, whatever else is in the cookie jar. Below that line a
            # person wins: a browser holding an unapproved token is somebody
            # who once looked at this page, not a screen on a wall.
            #
            # It must not fall through to minting a display, or everybody who
            # ever opened their own URL would leave a stray row in the panel
            # for an admin to wonder about.
            if not asked and not (disp and disp.get("approved")):
                who = self._identity()
                if who:
                    note_identity_seen(who["id"])
                    # SIGNED IN, and the page only ever sees this state now.
                    # `_identity` already refused a browser that merely holds
                    # the setup cookie wherever sign-in is required, so a
                    # person reaching here has proved who they are and their
                    # settings come from the server rather than localStorage.
                    #
                    # There were three states, because a PIN was optional and a
                    # person could be here without one. A password is not
                    # optional — it is what the setup link exists to collect —
                    # so "signed in" and "not" is the whole of it.
                    out = {"id": who["id"], "name": who["name"] or "",
                           "email": who.get("email") or "",
                           "settings": identity_settings(who["id"])}
                    return self._json(200, {"person": out})
            if disp:
                note_display_seen(disp["id"], asked=asked or None,
                                  hint=hint or None)
                rec = dict(disp)
                if asked:
                    rec["asked"] = asked
                return self._json(200, {"display": self._display_state(rec)})
            token, rec = new_display(asked, hint)
            if not token:
                return self._json(409, {"error": rec})
            print("display %s arrived as %r — not approved"
                  % (rec["id"], asked or "(no name)"), flush=True)
            body = json.dumps({"display": self._display_state(rec)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._set_display_cookie(token)
            self.end_headers()
            return self.wfile.write(body)

        if parsed.path == "/display/poll":
            # A display saying it is still here, and asking whether anything
            # has moved. The smallest answer that lets a screen decide to
            # reload itself: a stamp, and whether an admin has asked it to.
            #
            # Same-origin for the reason hello is — with SameSite=Strict a
            # cross-site POST arrives without the cookie and would be taken for
            # a device nobody has seen before.
            if not self._same_origin():
                return self._json(403, {"error": "cross-origin request refused"})
            obj = self._json_body()
            if obj is None:
                return
            try:
                boot = int(obj.get("boot") or 0)
            except (TypeError, ValueError):
                boot = 0
            # The numbers the display needs to keep itself up, answered here
            # rather than at hello so there is one place that carries them and
            # a change reaches a screen on its next poll. They are operational
            # rather than secret — how often a screen checks in and how many
            # times it tries says nothing about what it is connected to.
            app = read_app()
            cfg = {k: app.get(k, APP_DEFAULTS[k])
                   for k in ("poll_seconds", "retry_attempts", "retry_seconds",
                             "refresh_at", "refresh_stagger")}
            cfg["refresh_offset"] = 0
            # The panel's preview frames the display page and polls like
            # anything else that does. It is not a device: it must not enrol,
            # and it must never be told to reload itself out from under the
            # admin who is editing the very settings it is previewing — by an
            # admin's request or by the clock, which is why the nightly refresh
            # is blanked here as well.
            # THIS server's clock, which is the clock a reload request is
            # stamped with. The display keeps the value it was given at its
            # first poll and hands it back as `boot`, so the comparison below
            # is server time against server time — a tablet whose own clock is
            # a year out would otherwise obey a request for ever or never.
            now_ = int(time.time())
            if self.admin_port:
                cfg["refresh_at"] = ""
                return self._json(200, {"ok": True, "gen": config_gen(),
                                        "reload": False, "cfg": cfg,
                                        "now": now_})
            disp = self._display()
            if not disp:
                # No cookie, or one naming a row that is gone. Still a 200:
                # an unapproved screen renders, and the poll is how it finds
                # out it has been approved without anybody touching it.
                return self._json(200, {"ok": True, "gen": config_gen(),
                                        "reload": False, "cfg": cfg,
                                        "now": now_})
            # …and from here the stamp is THIS display's: its own row and the
            # settings everybody shares, so another device arriving or being
            # deleted is not a reason for this one to reload.
            gen = config_gen(disp["id"])
            cfg["refresh_offset"] = refresh_offset(disp["id"],
                                                   cfg["refresh_stagger"])
            note_display_seen(disp["id"])
            # Whatever it has been keeping since its last poll, filed against
            # the TOKEN's display and nothing else — a screen naming which
            # screen it is would be a screen able to file a fault against
            # another one. After `disp` on purpose: an unapproved browser has
            # no row to file against, and its poll returns above.
            if obj.get("events") and take_events(disp["id"], obj.get("events")):
                prune_events()
                prune_turns()
            # Judged here because this is the only clock a display keeps wound,
            # and because liveness is read from this very request — the thing
            # measured and the thing measuring arrive together.
            evaluate_alerts()
            # The poll is the only clock, so it is also what releases anything
            # being held — by quiet hours, or by the digest timer.
            flush_digest()
            try:
                req = int(disp.get("reload_req") or 0)
            except (TypeError, ValueError):
                req = 0
            # Satisfied by being obeyed: the display reports when it booted, so
            # a request older than this boot has already been carried out. No
            # acknowledgement to store, and nothing left set to fire again on
            # the next restart.
            return self._json(200, {"ok": True, "gen": gen, "cfg": cfg,
                                    "now": now_,
                                    "reload": bool(boot and req > boot)})

        if parsed.path == "/display/enrol":
            # The same redemption as /e/CODE, from a box on the screen itself.
            #
            # The URL form was the only way in, and it is the wrong shape for
            # the thing it is for: somebody standing at a screen that is
            # already showing this interface, holding six characters, being
            # asked to type an address instead of the code. Worse where guest
            # requests are off — that screen offered nothing at all, so a
            # device with a code had no way to use it and no way to find out
            # there was one.
            if self.admin_port:
                return self._json(404, {"error": "not found"})
            if not self._same_origin():
                return self._json(403, {"error": "cross-origin request refused"})
            obj = self._json_body()
            if obj is None:
                return
            ip = self.address_string()
            # The same back-off ledger the URL form uses, which is what makes
            # six characters enough: a billion possibilities only matters if
            # guessing is cheap.
            if code_blocked(ip):
                return self._json(429, {"error": "blocked", "state": "blocked"})
            token, out = redeem_code(str(obj.get("code") or ""))
            if not token:                        # `out` is the reason
                note_code_failure(ip)
                print("enrolment code refused (%s) from %s" % (out, ip), flush=True)
                return self._json(400, {"error": out, "state": out})
            _code_fails.pop(ip, None)
            file_display(out["id"])
            print("display %s (%s) enrolled by code, in page"
                  % (out["id"], display_label(out)), flush=True)
            body = json.dumps({"ok": True,
                               "display": self._display_state(out)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._set_display_cookie(token)
            self.end_headers()
            return self.wfile.write(body)

        if parsed.path == "/display/request":
            # A device asking for access, in the admin's own words. Same-origin
            # for the same reason hello is: nothing here should be reachable
            # from a page in another tab.
            if self.admin_port:
                return self._json(404, {"error": "not found"})
            if not self._same_origin():
                return self._json(403, {"error": "cross-origin request refused"})
            cfg = display_settings()
            if not cfg["guest_requests"]:
                return self._json(409, {"error": "this server does not take "
                                                 "requests for access"})
            disp = self._display()
            if not disp:
                return self._json(401, {"error": "this device has no identity "
                                                 "yet — reload the page"})
            obj = self._json_body()
            if obj is None:
                return
            # A renewal sends nothing: the answers are already on the row, and
            # asking somebody to retype them every month is how a form stops
            # being answered honestly.
            # THE ADDRESS, ahead of the admin's own fields and not one of
            # them. It is not something a deployment chose to ask: it is the
            # login this request is FOR, so it cannot be renamed, reordered or
            # switched off, and a form with it missing is a request that could
            # only ever be approved into an account nobody can reach.
            #
            # Checked here as well as at approval. The person is standing at
            # the screen now and can fix a typo; the admin looking at the row
            # tomorrow cannot.
            email = ""
            if not obj.get("renew"):
                email, bad = check_email(obj.get("email"))
                if bad:
                    return self._json(400, {"error": bad})
            answers = None
            if not obj.get("renew"):
                answers, err = [], None
                given = obj.get("answers")
                given = given if isinstance(given, dict) else {}
                for i, f in enumerate(cfg["form"]):
                    v = str(given.get(str(i)) or "").strip()
                    v = v[:2000] if f["message"] else v[:200]
                    if f["required"] and not v:
                        err = "%s is required" % f["label"]
                        break
                    if v:
                        answers.append({"label": f["label"], "value": v})
                if err:
                    return self._json(400, {"error": err})
            elif not disp.get("answers"):
                return self._json(400, {"error": "nothing to renew — this "
                                                 "device has never asked"})
            rec, err = request_access(disp["id"], answers)
            if err:
                return self._json(409, {"error": err})
            if email:
                rows = read_displays()
                if disp["id"] in rows:
                    rows[disp["id"]]["req_email"] = email
                    write_displays(rows)
                    rec = dict(rows[disp["id"]], id=disp["id"])
            print("display %s (%s) asked for access%s"
                  % (rec["id"], display_label(rec),
                     " again" if obj.get("renew") else ""), flush=True)
            return self._json(200, {"display": self._display_state(rec)})

        if parsed.path == "/groups/save":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            groups = read_groups()
            gid = str(obj.get("id") or "")
            if gid:
                if gid not in groups:
                    return self._json(404, {"error": "no such group"})
                current = groups[gid]
            else:
                if len(groups) >= MAX_GROUPS:
                    return self._json(409, {"error": "that is %d groups already"
                                                     % MAX_GROUPS})
                current = {"name": "", "kind": "device", "members": []}
            rec, err = validate_group(obj, current)
            if err:
                return self._json(400, {"error": err})
            if gid:
                rec.update(created=current.get("created"),
                           created_by=current.get("created_by"))
                # The kind cannot change under an existing group: its members
                # are of one population and a switch would silently empty it.
                rec["kind"] = current["kind"]
            else:
                gid = "g" + secrets.token_hex(4)
                rec.update(created=int(time.time()), created_by=s["user"])
            groups[gid] = rec
            write_groups(groups)
            print("group %s (%s, %s) saved by %s — %d member(s)"
                  % (gid, rec["name"], rec["kind"], s["user"],
                     len(rec["members"])), flush=True)
            return self._json(200, {"ok": True, "id": gid,
                                    "groups": admin_groups()})

        if parsed.path == "/identities/new":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            token, rec = new_identity(obj.get("name"), obj.get("email"),
                                      s["user"])
            if not token:                        # `rec` is the reason
                return self._json(409, {"error": rec})
            print("identity %s (%s) created by %s"
                  % (rec["id"], identity_label(rec), s["user"]), flush=True)
            # The URL is handed back ONCE and never again: what is stored is
            # its hash, so a panel that has been closed cannot show it a second
            # time. Same contract an embed key already has, and for the same
            # reason — a secret a panel can re-display is a secret sitting in
            # every browser that ever had that page open.
            return self._json(200, {"ok": True, "token": token,
                                    "identities": admin_identities()})

        if parsed.path == "/user/login":
            # AN EMAIL AND A PASSWORD, from anywhere. Nothing is required in
            # the cookie jar first: that is the difference between this and
            # every credential this server had before it — a person can sit
            # down at a machine that has never heard of them and be themselves
            # on it, which is what an account is for and what a minted URL in a
            # cookie could never do.
            #
            # HTTPS ONLY, and refused rather than degraded: a password typed
            # over plain HTTP is a password somebody else has. The loopback
            # case is the exception the whole server already makes — bound
            # there it is the only listener and nothing is between the ends.
            if self.admin_port:
                return self._json(404, {"error": "not found"})
            if not self._same_origin():
                return self._json(403, {"error": "cross-origin request refused"})
            if not isinstance(self.connection, ssl.SSLSocket) \
               and exposed(read_app()):
                return self._json(400, {"error": "signing in needs a secure "
                                                 "connection"})
            obj = self._json_body()
            if obj is None:
                return
            who = identity_by_email(obj.get("email"))
            # ONE ANSWER FOR BOTH HALVES. "no such account" tells somebody
            # standing at a public screen which addresses are real here, which
            # is a list worth having before you start guessing passwords.
            wrong = {"error": "that is not an email and password we know"}
            if not who:
                return self._json(401, wrong)
            pid = who["id"]
            if user_login_blocked(pid):
                # The number is not given: "wait 47 seconds" is a clock an
                # attacker can read, and the person who typed it wrong twice
                # needs to know to stop rather than to know when.
                return self._json(429, {"error": "too many attempts — wait a "
                                                 "little and try again"})
            if not verify_identity_password(pid, obj.get("password")):
                print("sign-in refused for %s from %s"
                      % (pid, self.address_string()), flush=True)
                return self._json(401, wrong)
            hours = identity_hours(who)
            token = open_user_session(pid, hours)
            note_identity_seen(pid)
            print("identity %s signed in for %dh" % (pid, hours), flush=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_user_cookie(token, hours)
            body = json.dumps({"ok": True, "hours": hours,
                               "name": who.get("name") or "",
                               "settings": identity_settings(pid)}).encode()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/user/logout":
            # Ending it HERE as well as dropping the cookie: a session the
            # server still honours is a session, whatever the browser was
            # persuaded to forget.
            if self.admin_port:
                return self._json(404, {"error": "not found"})
            if not self._same_origin():
                return self._json(403, {"error": "cross-origin request refused"})
            pid = self._user_pid()
            if pid:
                close_user_sessions(pid)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_user_cookie("", 0)
            body = json.dumps({"ok": True}).encode()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/user/setup":
            # THE SETUP LINK BEING SPENT. A person chooses their own password
            # here and nowhere else: an admin who set it would know it, and
            # then the account would be theirs rather than the person's.
            #
            # The claim is the setup cookie, which the minted URL left in this
            # browser a moment ago. It is enough exactly ONCE — the moment a
            # password exists, this route refuses, and the way back in is the
            # login page. Otherwise anybody who found that browser open could
            # take the account by setting a new password on it.
            if self.admin_port:
                return self._json(404, {"error": "not found"})
            if not self._same_origin():
                return self._json(403, {"error": "cross-origin request refused"})
            if not isinstance(self.connection, ssl.SSLSocket) \
               and exposed(read_app()):
                return self._json(400, {"error": "choosing a password needs a "
                                                 "secure connection"})
            # Read from the jar rather than through `_identity`, which answers
            # None wherever sign-in is required — and this is the one moment
            # somebody legitimately has no way to sign in yet.
            claim = ""
            raw = self.headers.get("Cookie")
            if raw:
                try:
                    jar = http.cookies.SimpleCookie(raw)
                except http.cookies.CookieError:
                    jar = {}
                m = jar.get(IDENTITY_COOKIE) if jar else None
                found = find_identity(m.value) if m else None
                claim = found["id"] if found else ""
            if not claim:
                return self._json(401, {"error": "open the link you were sent "
                                                 "first"})
            obj = self._json_body()
            if obj is None:
                return
            rec = read_identities().get(claim)
            if not rec:
                return self._json(404, {"error": "no such account"})
            if identity_ready(rec):
                return self._json(409, {"error": "this account already has a "
                                                 "password — sign in with it"})
            bad = set_identity_password(claim, obj.get("password"))
            if bad:
                return self._json(400, {"error": bad})
            # Signed in on the way out. set_identity_password closes every
            # session the account had, so without this somebody would choose a
            # password and be asked for it in the same breath.
            hours = identity_hours(read_identities()[claim])
            token = open_user_session(claim, hours)
            note_identity_seen(claim)
            print("identity %s set its password and signed in" % claim,
                  flush=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_user_cookie(token, hours)
            body = json.dumps({"ok": True, "hours": hours,
                               "name": rec.get("name") or "",
                               "settings": identity_settings(claim)}).encode()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/person/settings":
            # What a person keeps. Only for a browser that has SIGNED IN: the
            # setup cookie says who this claims to be, and a claim is not what
            # durable storage hangs off. Signed out, the display keeps its own
            # preferences in the browser, exactly as it always has.
            if self.admin_port:
                return self._json(404, {"error": "not found"})
            if not self._same_origin():
                return self._json(403, {"error": "cross-origin request refused"})
            pid = self._user_pid()
            if not pid:
                return self._json(401, {"error": "not signed in"})
            obj = self._json_body()
            if obj is None:
                return
            saved = write_identity_settings(pid, obj.get("settings"))
            if saved is None:
                return self._json(404, {"error": "no such identity"})
            return self._json(200, {"ok": True, "settings": saved})

        if parsed.path == "/alerts/ack":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            ids = [str(i)[:16] for i in (obj.get("ids") or [])]
            gone = ack_alerts(ids)
            return self._json(200, {"ok": True, "closed": gone})

        if parsed.path == "/events/clear":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            did = str(obj.get("id") or "")
            rows = read_events()
            # One screen's, or all of them. Deleting what a display reported is
            # not deleting the display: a screen whose fault has been fixed
            # should be able to start clean without being taken off the wall.
            keep = [r for r in rows if r.get("did") != did] if did else []
            write_events(keep)
            # The conversation record goes with it. They are one window and one
            # control; clearing what a screen reported while keeping what was
            # said to it would be the surprising half of the pair.
            turns = read_turns()
            tkeep = [r for r in turns if r.get("did") != did] if did else []
            write_turns(tkeep)
            print("%d event(s) and %d turn(s) cleared by %s%s"
                  % (len(rows) - len(keep), len(turns) - len(tkeep), s["user"],
                     " for " + did if did else " (all)"), flush=True)
            return self._json(200, {"ok": True,
                                    "cleared": len(rows) - len(keep),
                                    "turns": len(turns) - len(tkeep)})

        if parsed.path == "/identities/wake":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            pid = str(obj.get("id") or "")
            bad = set_identity_wake(pid, obj.get("word"))
            if bad == "no such identity":
                return self._json(404, {"error": bad})
            if bad:
                return self._json(409, {"error": bad})
            print("identity %s wake word set to %r by %s"
                  % (pid, str(obj.get("word") or "").strip(), s["user"]), flush=True)
            return self._json(200, {"ok": True, "identities": admin_identities()})

        if parsed.path == "/identities/reissue":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            token = reissue_identity(str(obj.get("id") or ""))
            if not token:
                return self._json(404, {"error": "no such identity"})
            print("identity %s reissued by %s" % (obj.get("id"), s["user"]),
                  flush=True)
            # The old URL stopped working the moment that returned. Anything
            # holding a cookie from it keeps that cookie and it no longer
            # resolves, which is the same revocation an embed key gets.
            return self._json(200, {"ok": True, "token": token,
                                    "identities": admin_identities()})

        if parsed.path == "/identities/rename":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            rows = read_identities()
            pid = str(obj.get("id") or "")
            if pid not in rows:
                return self._json(404, {"error": "no such identity"})
            name = str(obj.get("name") or "").strip()[:60]
            if not name:
                return self._json(400, {"error": "a name is required"})
            if any(p != pid and r["name"].lower() == name.lower()
                   for p, r in rows.items()):
                return self._json(409, {"error": "there is already an identity "
                                                 "with that name"})
            rows[pid]["name"] = name
            # THE ADDRESS IS EDITABLE, because it is what they sign in with and
            # people change employer, surname and provider. Only when one is
            # sent: the panel edits the two fields separately and a rename that
            # arrived without an address must not blank the login.
            #
            # It does NOT touch the password. Changing where somebody signs in
            # from is not a reason to take away what they signed in with, and
            # an admin who could reset a password by editing an address would
            # be able to take the account.
            if obj.get("email") is not None:
                email, bad = check_email(obj.get("email"), skip_pid=pid)
                if bad:
                    return self._json(409, {"error": bad})
                rows[pid]["email"] = email
            write_identities(rows)
            return self._json(200, {"ok": True, "identities": admin_identities()})

        if parsed.path == "/identities/delete":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            rows = read_identities()
            pid = str(obj.get("id") or "")
            if pid not in rows:
                return self._json(404, {"error": "no such identity"})
            name = identity_label(rows.pop(pid))
            write_identities(rows)
            left = drop_from_groups(pid)
            # An allow-list holding somebody who no longer exists is a
            # permission nobody can see and nobody can withdraw. Cleared here,
            # exactly as a deleted display's is.
            doc = read_routes()
            touched = [r for r, o in doc["routes"].items()
                       if pid in (o.get("identities") or [])]
            for r in touched:
                doc["routes"][r]["identities"] = [
                    p for p in doc["routes"][r]["identities"] if p != pid]
            if touched:
                write_routes(doc)
            print("identity %s (%s) deleted by %s%s%s"
                  % (pid, name, s["user"],
                     " — removed from %d endpoint(s)" % len(touched)
                     if touched else "",
                     "; out of " + ", ".join(left) if left else ""), flush=True)
            return self._json(200, {"ok": True, "identities": admin_identities()})

        if parsed.path == "/groups/sets":
            # Which CUSTOM groups a row is in, set from the row rather than
            # from each group in turn. It replaces /groups/move, which took the
            # row out of every other group first — a single-select control's
            # rule, not the model's. A group is a grant and grants add up: a
            # television is allowed to be physics department kit and a
            # television at the same time.
            #
            # The default group is not in this list and cannot be. It is the
            # root: enrolling put the row there and only deleting the row takes
            # it out.
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            did = str(obj.get("id") or "")
            people = did in read_identities()
            if not people and did not in read_displays():
                return self._json(404, {"error": "no such row"})
            kinds = IDENTITY_GROUP_KINDS if people else DISPLAY_GROUP_KINDS
            want = {str(g)[:32] for g in (obj.get("groups") or [])}
            groups = read_groups()
            touched = []
            for gid, rec in groups.items():
                if rec["system"] or rec["kind"] not in kinds:
                    continue                      # not this control's business
                here, should = did in rec["members"], gid in want
                if here == should:
                    continue
                if should:
                    if not add_member(rec, did):
                        return self._json(409, {"error": '"%s" is full — it '
                                                         "holds %d already"
                                                         % (rec["name"], MAX_ALLOW)})
                else:
                    rec["members"] = [m for m in rec["members"] if m != did]
                touched.append(rec["name"])
            if touched:
                write_groups(groups)
                print("row %s regrouped by %s: %s"
                      % (did, s["user"], ", ".join(touched)), flush=True)
            return self._json(200, {"ok": True, "groups": admin_groups()})

        if parsed.path == "/groups/delete":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            groups = read_groups()
            gid = str(obj.get("id") or "")
            if gid not in groups:
                return self._json(404, {"error": "no such group"})
            if groups[gid]["system"]:
                # A default an admin can delete is not a default: everything
                # enrolling afterwards would have nowhere to land.
                return self._json(400, {"error": "this group cannot be deleted "
                                                 "— it is where new %ss land"
                                                 % ("person" if groups[gid]["kind"]
                                                    == "identity" else "display")})
            name = groups.pop(gid)["name"]
            write_groups(groups)
            # An endpoint naming a group that no longer exists is a permission
            # nobody can see and nobody can withdraw — the same reasoning that
            # clears a deleted display from an allow-list, and a deleted
            # endpoint from a fallthrough.
            doc = read_routes()
            touched = [r for r, o in doc["routes"].items()
                       if gid in (o.get("groups") or [])]
            for r in touched:
                doc["routes"][r]["groups"] = [g for g in doc["routes"][r]["groups"]
                                              if g != gid]
            if touched:
                write_routes(doc)
            print("group %s (%s) deleted by %s%s"
                  % (gid, name, s["user"],
                     " — removed from %d endpoint(s)" % len(touched)
                     if touched else ""), flush=True)
            return self._json(200, {"ok": True, "groups": admin_groups()})

        if parsed.path == "/displays/settings":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            cfg, err = validate_display_settings(obj, display_settings())
            if err:
                return self._json(400, {"error": err})
            # The other end of the rule. Switching requests off leaves the
            # default endpoint as the only thing an uninvited device can reach,
            # so it has to BE something — and the matching refusal, when an
            # endpoint edit would close that door from the other side, lives in
            # the /routes handlers.
            if not cfg["guest_requests"] and not open_default(read_routes()):
                return self._json(409, {"error":
                    "there is nowhere for a guest to go: the default endpoint "
                    "is restricted or switched off, so turning requests off "
                    "would leave an uninvited device unable to reach anything. "
                    "Make an endpoint that is open to any display the default "
                    "first."})
            write_display_settings(cfg)
            # A device pointing at a profile that has just been deleted is a
            # setting nobody can see and nobody can change — the same fault as
            # an allow-list naming a display that no longer exists, and cleared
            # the same way. kiosk_of already fails it off, so nothing was ever
            # drifting to numbers that had gone; this is so the panel says so.
            displays = read_displays()
            touched = 0
            for key, what in (("saver", "screensaver"), ("look", "appearance")):
                live = {p["id"] for p in cfg[key + "s"]}
                gone = [d for d, r in displays.items()
                        if r.get(key) and r[key] not in live]
                for d in gone:
                    displays[d][key] = ""
                if gone:
                    touched += len(gone)
                    print("%s profile deleted — cleared from %d device(s)"
                          % (what, len(gone)), flush=True)
            if touched:
                write_displays(displays)
            print("display settings saved by %s: requests=%s max=%d "
                  "pending=%d guest=%dd form=%d field(s)"
                  % (s["user"], "on" if cfg["guest_requests"] else "off",
                     cfg["max_displays"], cfg["max_pending"], cfg["guest_days"],
                     len(cfg["form"])), flush=True)
            # Read back rather than echoed: `cfg` is what went to disk, keys
            # and all, and the panel is never sent one. The save response was
            # the one path that would have handed them back.
            return self._json(200, {"ok": True, "settings": panel_settings(),
                                    "displays": admin_displays()})

        if parsed.path == "/displays/decide":
            # Approve or refuse, in one gesture with the endpoints it gets.
            # Two steps in two places was the wrong shape: the whole reason to
            # approve somebody is to give them a particular assistant, so
            # deciding and granting are one decision.
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            did = str(obj.get("id") or "")
            displays = read_displays()
            rec = displays.get(did)
            if not rec:
                return self._json(404, {"error": "no such display"})
            now_ = int(time.time())
            approve = bool(obj.get("approved"))
            name = str(obj.get("name") or "").strip()[:40]
            if name:
                rec["name"] = name
            # A REQUEST IS FOR AN ACCOUNT, NOT FOR A DEVICE. Somebody who
            # filled in the form is a person asking to be let in, and a person
            # is an account now — so approving them creates one and mints the
            # link that lets them choose a password. The row they asked from is
            # a browser on a machine; it does not become a screen on anybody's
            # wall because they typed their name into a form.
            #
            # The link goes back down the channel the verdict already uses:
            # they are standing at that screen waiting for an answer, and the
            # answer is "here is where you choose your password". The panel
            # keeps a copy on the row for the case where they walked away.
            if approve and rec.get("req_email") and not rec.get("approved_at"):
                who = str(rec.get("name") or "").strip() \
                      or next((a["value"] for a in (rec.get("answers") or [])
                               if (a.get("value") or "").strip()), "") \
                      or display_label(rec)
                token, made = new_identity(who, rec["req_email"], s["user"])
                if not token:                    # `made` is the reason
                    return self._json(409, {"error": made})
                rec["setup"] = token
                # Not a device, and not left in the queue either: the person
                # row is the live thing now and this one is only the browser
                # they asked from.
                rec.update(approved=False, denied=False, deny_reason="",
                           approved_by=s["user"], approved_at=now_, expires=0)
                write_displays(displays)
                # THE TICKS, ON THE PERSON. Approving and granting are one
                # gesture — that is the whole reason the endpoints are on this
                # row — and they have to follow the account, not the browser
                # the form was filled in on. That browser is about to stop
                # being anything at all.
                set_identity_endpoints(made["id"], obj.get("endpoints"))
                # The display half, cleared: this row was never granted
                # anything as a device and must not keep a grant from an
                # earlier ask.
                set_display_endpoints(did, [])
                # Decided, so it is no longer asking.
                clear_alert("asked_in", did)
                print("request from display %s approved into identity %s (%s) "
                      "by %s" % (did, made["id"], rec["req_email"], s["user"]),
                      flush=True)
                return self._json(200, {"ok": True,
                                        "token": token,
                                        "identities": admin_identities(),
                                        "displays": admin_displays()})
            if approve:
                # Ever granted before, which is what makes this one a renewal.
                # Not `approved`: asking again clears that, so by the time a
                # decision is made the flag says nothing about the history.
                again = bool(rec.get("approved_at"))
                rec.update(approved=True, denied=False, deny_reason="",
                           approved_by=s["user"], approved_at=now_)
                # A grant to something that asked runs out; one to a display an
                # admin created and sent a code for does not.
                if is_guest(rec):
                    days = display_settings()["guest_days"]
                    rec["expires"] = now_ + days * 86400
                    if again:
                        rec["renewals"] = (rec.get("renewals") or 0) + 1
                else:
                    rec["expires"] = 0
            else:
                rec.update(approved=False, denied=True, expires=0,
                           deny_reason=str(obj.get("reason") or "").strip()[:300],
                           deny_note=str(obj.get("note") or "").strip()[:500],
                           deny_repeat=bool(obj.get("repeat", True)))
            write_displays(displays)
            # …and filed with its own population, so the next grant to all of
            # them is one tick rather than one per row. Only on the way in: a
            # refusal leaves whatever group it was already in alone, because
            # groups are how you address a set of things and not a record of
            # who is currently allowed.
            # Decided, so it is no longer asking. Resolved either way — the
            # alert was "somebody is waiting", and they are not any more.
            clear_alert("asked_in", did)
            if approve:
                file_display(did, by=s["user"])
            # The allow-lists, whichever way it went: a refusal has to take
            # back anything a previous approval gave, or "denied" is a word on
            # a row rather than a thing that happened.
            set_display_endpoints(did, obj.get("endpoints") if approve else [])
            print("display %s (%s) %s by %s%s"
                  % (did, display_label(rec),
                     "approved" if approve else "refused", s["user"],
                     "" if approve else
                     (" — may ask again" if rec["deny_repeat"] else " — final")),
                  flush=True)
            return self._json(200, {"ok": True, "displays": admin_displays()})

        if parsed.path == "/displays/new":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            # Validated here rather than trusted: a profile id that does not
            # exist would leave a screen naming nothing, which reads on the row
            # as a setting somebody chose.
            cfg = display_settings()
            kp = str(obj.get("kiosk_profile") or "")[:16]
            nw = str(obj.get("network") or "")[:16]
            if kp and not any(k["id"] == kp for k in cfg["kiosks"]):
                return self._json(400, {"error": "that display profile no "
                                                 "longer exists — reload the "
                                                 "panel to see the list"})
            if nw and not any(n["id"] == nw for n in cfg["networks"]):
                return self._json(400, {"error": "that network profile no "
                                                 "longer exists — reload the "
                                                 "panel to see the list"})
            # The endpoints this screen is for — several, because a wall panel
            # answering to a house name and a model is the ordinary case.
            # Validated the same way and for the same reason as the profiles
            # above: an id that no longer exists would be a grant that
            # silently landed nowhere.
            known = read_routes()["routes"]
            eps = [str(r)[:16] for r in (obj.get("endpoints") or [])][:20]
            if any(e not in known for e in eps):
                return self._json(400, {"error": "one of those endpoints no "
                                                 "longer exists — reload the "
                                                 "panel to see the list"})
            # A screen is loaded from ONE address, so a grant spanning two
            # ports is a screen that cannot exist. Refused here, where the
            # ticks are, rather than handed out as a code pointing at a port
            # where half the grant is unreachable.
            clash = display_network_clash(eps)
            if clash:
                return self._json(400, {"error": clash})

            rec, err = invite_display(str(obj.get("name") or "").strip()[:40],
                                      s["user"],
                                      {"kiosk": obj.get("kiosk"),
                                       "kiosk_profile": kp, "network": nw})
            if err:
                return self._json(400, {"error": err})
            # Granted through the same call the row's own ticks use, so there
            # is one way a display comes to be on an allow-list rather than two
            # that have to agree. That call treats its argument as the WHOLE
            # truth and clears the row from every other list — which is right
            # for ticks and would be wrong here, except that this row was made
            # three lines ago and is on no list to be cleared from. Anything
            # that ever calls this for an existing row has to pass the full
            # set.
            if eps:
                set_display_endpoints(rec["id"], eps)
                print("display %s invited with endpoint%s %s by %s"
                      % (rec["id"], "" if len(eps) == 1 else "s",
                         ", ".join(eps), s["user"]), flush=True)
            print("display %s (%s) invited by %s — code issued"
                  % (rec["id"], display_label(rec), s["user"]), flush=True)
            # …and how long it is worth anything for, so the panel can count
            # it down rather than restate the rule. Read off the record rather
            # than recomputed from the setting: an admin who changes the
            # lifetime between minting and reading must not be shown a number
            # the code itself does not agree with.
            return self._json(200, {"ok": True, "id": rec["id"],
                                    "code": rec["code"],
                                    "code_left": max(0, rec["code_expires"]
                                                     - int(time.time()))
                                                 if rec["code_expires"] else 0,
                                    "code_forever": not rec["code_expires"],
                                    "displays": admin_displays()})

        if parsed.path == "/displays/reissue":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            rec, err = reissue_display(str(obj.get("id") or ""))
            if err:
                return self._json(404, {"error": err})
            # Loud in the log, because this took a working screen off the air
            # deliberately and somebody may be standing in front of it.
            print("display %s (%s) reissued by %s — its old token is dead"
                  % (rec["id"], display_label(rec), s["user"]), flush=True)
            # …and how long it is worth anything for, so the panel can count
            # it down rather than restate the rule. Read off the record rather
            # than recomputed from the setting: an admin who changes the
            # lifetime between minting and reading must not be shown a number
            # the code itself does not agree with.
            return self._json(200, {"ok": True, "id": rec["id"],
                                    "code": rec["code"],
                                    "code_left": max(0, rec["code_expires"]
                                                     - int(time.time()))
                                                 if rec["code_expires"] else 0,
                                    "code_forever": not rec["code_expires"],
                                    "displays": admin_displays()})

        if parsed.path == "/displays/approve":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            did = str(obj.get("id") or "")
            displays = read_displays()
            if did not in displays:
                return self._json(404, {"error": "no such display"})
            on = bool(obj.get("approved"))
            displays[did]["approved"] = on
            displays[did]["approved_by"] = s["user"] if on else ""
            displays[did]["approved_at"] = int(time.time()) if on else 0
            name = str(obj.get("name") or "").strip()[:40]
            if on and name:
                # Approving and naming in one gesture. A row called "kitchen"
                # because that is what the URL said is a row that will still
                # be called "kitchen" when the tablet moves to the hall.
                displays[did]["name"] = name
            write_displays(displays)
            # Approving a row that already holds a token is the moment it
            # starts working, and everything that starts working is filed. The
            # panel goes through /displays/decide, which does this — so without
            # it here the invariant held only for the route the shipped UI
            # happens to use, and a row approved through the API stayed outside
            # its group until the next restart backfilled it.
            if on and displays[did].get("hash"):
                file_display(did, by=s["user"])
            print("display %s (%s) %s by %s"
                  % (did, display_label(displays[did]),
                     "approved" if on else "approval withdrawn", s["user"]),
                  flush=True)
            return self._json(200, {"ok": True, "displays": admin_displays()})

        if parsed.path == "/displays/kiosk":
            # What this screen looks like where it hangs. Its own endpoint
            # rather than a field on rename, because they are saved by
            # different gestures at different moments: a name is typed once
            # when a device arrives, and these are tuned while watching a
            # preview move.
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            did = str(obj.get("id") or "")
            displays = read_displays()
            if did not in displays:
                return self._json(404, {"error": "no such display"})
            cfg = display_settings()
            fields, err = validate_kiosk(obj, displays[did], cfg["kiosks"])
            if err:
                return self._json(400, {"error": err})
            # WHICH ASSISTANTS, where they are named. It is a different
            # document — the allow-list lives on the endpoint, not on the
            # display — but it is one gesture for whoever pressed SAVE, and a
            # second button for it would be two ways to describe one screen.
            # Absent means "not being set", which is not the same as an empty
            # list meaning "none of them": a caller that does not carry the
            # field must not clear a grant it never showed.
            if isinstance(obj.get("endpoints"), list):
                known = read_routes()["routes"]
                eps = [str(r)[:16] for r in obj["endpoints"]][:20]
                if any(e not in known for e in eps):
                    return self._json(400, {"error": "one of those endpoints "
                                                     "no longer exists — "
                                                     "reload the panel"})
            # A screen is loaded from ONE address, so a grant spanning two
            # ports is a screen that cannot exist. Refused here, where the
            # ticks are, rather than handed out as a code pointing at a port
            # where half the grant is unreachable.
            clash = display_network_clash(eps)
            if clash:
                return self._json(400, {"error": clash})
                set_display_endpoints(did, eps)
            displays[did].update(fields)
            write_displays(displays)
            return self._json(200, {"ok": True, "id": did,
                                    "displays": admin_displays()})

        # /displays/kind is GONE. It moved a display row between two display
        # populations, and there is one — how a row enrolled describes the row
        # rather than deciding which list it may be put in. The panel control
        # went with it; a control whose only two answers are the same answer
        # is a control wired to nothing.

        if parsed.path == "/displays/reload":
            # Ask a screen to reload itself, without walking to it. What this
            # actually fixes is a display that is alive but stuck: it is still
            # polling, so it is still listening, and a reload is the whole
            # repair. A display that does NOT come back from this is one the
            # server has no channel to at all — nothing here reaches it, and
            # that is the condition worth raising an alert about rather than
            # retrying into.
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            did = str(obj.get("id") or "")
            displays = read_displays()
            if did not in displays:
                return self._json(404, {"error": "no such display"})
            displays[did]["reload_req"] = int(time.time())
            write_displays(displays)
            return self._json(200, {"ok": True, "id": did,
                                    "displays": admin_displays()})

        if parsed.path == "/displays/rename":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            did = str(obj.get("id") or "")
            displays = read_displays()
            if did not in displays:
                return self._json(404, {"error": "no such display"})
            # Blank hands the row back to whatever the device calls itself,
            # which is a real thing to want rather than an empty field.
            displays[did]["name"] = str(obj.get("name") or "").strip()[:40]
            write_displays(displays)
            return self._json(200, {"ok": True, "displays": admin_displays()})

        if parsed.path == "/displays/delete":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            did = str(obj.get("id") or "")
            displays = read_displays()
            if did not in displays:
                return self._json(404, {"error": "no such display"})
            name = display_label(displays.pop(did))
            write_displays(displays)
            _display_refusals.pop(did, None)
            left = drop_from_groups(did)
            # An allow-list holding the id of a display that no longer exists
            # is a permission nobody can see and nobody can withdraw. Cleared
            # here, for the same reason a deleted endpoint's fallthrough is.
            doc = read_routes()
            touched = [r for r, o in doc["routes"].items()
                       if did in (o.get("displays") or [])]
            for r in touched:
                doc["routes"][r]["displays"] = [d for d in doc["routes"][r]["displays"]
                                                if d != did]
            if touched:
                write_routes(doc)
            print("display %s (%s) deleted by %s%s%s"
                  % (did, name, s["user"],
                     " — removed from %d endpoint(s)" % len(touched)
                     if touched else "",
                     "; out of " + ", ".join(left) if left else ""), flush=True)
            # Its token still exists in a cookie jar somewhere and now matches
            # nothing, so the device it belonged to is back to being a browser
            # that has never been here. That is the revocation.
            return self._json(200, {"ok": True, "displays": admin_displays()})

        if parsed.path == "/ask":
            # Somebody is using this, which is not the same as a screen
            # checking in — see note_use. A scheduled restart waits for these
            # to stop.
            note_use()
            # Reachable from the display, which has no sign-in by design.
            emb, refused = self._cap("ask")
            if refused:
                return
            if emb:
                if not embed_allowed(emb["id"], emb["cap"]["rate_per_min"]):
                    return self._json(429, {"error": "this embed is over its "
                                                     "rate limit — slow down"})
            elif not ask_allowed(self.address_string()):
                return self._json(429, {"error": "too many requests — slow down"})
            obj = self._json_body()
            if obj is None:
                return
            text = str(obj.get("text") or "").strip()[:4000]
            if not text:
                return self._json(400, {"error": "no text"})
            # Which name was spoken decides where this goes. Nothing spoke a
            # name at all when it was typed into the composer or pushed
            # through an embed, and that is what the default route is for.
            doc = read_routes()
            want = str(obj.get("route") or "")[:32]
            if self.pinned_net:
                # A port answers as its own endpoints and no others. Asking
                # for one it does not carry is a caller at the wrong door —
                # given this port's default rather than refused, which is the
                # same thing the shared port does with a route that has been
                # switched off since the page loaded.
                mine = net_members(doc, self.pinned_net)
                if want not in mine:
                    want = (doc["default"] if doc["default"] in mine
                            else (mine[0] if mine else ""))
                if not want:
                    return self._json(503, {"error": "no endpoint answers on "
                                                     "this port"})
            rid, cfg = resolve_route(doc, want)
            if not cfg:
                return self._json(503, {"error": "no route is answering"})
            # The route is named back on every reply, not just when it
            # changes: the display is entitled to know which one answered,
            # and the answer is the only place it could come from. The
            # adapter kind is deliberately not in here — see public_routes.
            about = {"route": rid, "name": cfg["name"]}

            # The gate. The display drops these before they ever get here —
            # that is where the utterance actually belongs to somebody — and
            # this is the half that does not depend on the browser being the
            # one we shipped. An embed is not a display and does not inherit
            # one: its rights come from its key, so it reaches the endpoints
            # anything can reach and no others.
            disp, ident = (None, None) if emb else self._subject()
            # ONE GATE. There was a second — a network profile could be marked
            # "the port is the grant", and reaching such a port bypassed this
            # test entirely. It is gone, and with it the hole where an endpoint
            # requiring a sign-in sat on such a port and quietly required
            # nothing. What a port is FOR is now said on the endpoint that owns
            # it, where it can be read.
            if not subject_may(cfg, disp, ident):
                note_display_refused(disp, cfg["name"])
                print("refused: %s may not use %s (%s)"
                      % (disp["id"] if disp else
                         ("identity " + ident["id"] if ident else
                          "a caller with no token"),
                         cfg["name"], rid), flush=True)
                # The DISPLAY says nothing about this: that utterance was
                # addressed to a different device, and one nobody was talking
                # to announcing that it cannot help is noise laid over the
                # answer somebody is waiting for. Which is why the reason is
                # here, in a field, rather than in anything speakable.
                return self._json(403, dict(about, refused="display",
                                            error="this display may not use "
                                                  "that endpoint"))
            if cfg["provider"] == "demo":
                # The display owns the demo replies; say so plainly rather
                # than inventing a second set that drifts from the first.
                return self._json(200, dict(about, reply="", demo=True))
            history = obj.get("history") or []
            tz = str(obj.get("tz") or "")[:64]
            t0 = time.time()
            try:
                out = ask_backend(text, history, cfg, tz=tz,
                                  # Held by the display for exactly as long as
                                  # the route binding, and handed back on every
                                  # turn: it is what makes "which room?" →
                                  # "the kitchen" work.
                                  conversation_id=str(obj.get("conversation_id")
                                                      or "")[:64])
            except Exception as exc:                       # noqa: BLE001
                print("ask failed (%s %s): %s"
                      % (rid, route_dest(cfg), exc), flush=True)
                # The leg only this side can see. A display is told something
                # went wrong and deliberately not what; the panel is where the
                # verbatim error belongs, keyed to the screen that hit it.
                failed_ms = int((time.time() - t0) * 1000)
                note_event("backend_error", did=disp["id"] if disp else "",
                           level="error", route=cfg.get("name") or rid,
                           detail=str(exc)[:300], ms=failed_ms)
                bad_trail = obj.get("trail") if isinstance(obj.get("trail"), dict) else None
                note_turn(disp["id"] if disp else "", cfg.get("name") or rid,
                          (bad_trail or {}).get("heard"), text, "", bad_trail,
                          failed_ms, error=str(exc))
                # The message names the route rather than the adapter. A
                # display says this out loud, and "openai returned 401" tells
                # the person standing in front of it nothing they can act on
                # while telling anyone in earshot what this box is wired to.
                return self._json(502, dict(about, error=str(exc)))

            # Nobody remembers which name owns which capability. Asked
            # something it has no intent for, a house hands the question to
            # the route it was told to, and the person is never told they used
            # the wrong word — so the answer keeps the house's name and voice.
            #
            # One hop, and never the target's own fallthrough: a chain of them
            # is a question travelling somewhere nobody chose, at a cost per
            # link, and two routes pointing at each other would do it for ever.
            took_ms = int((time.time() - t0) * 1000)
            # PER ROUTE, because one number across both never fires or never
            # stops: a house intent answers in about a tenth of a second and a
            # hosted model takes seconds. The route's own timeout is the only
            # number here that already means "longer than this is wrong", so
            # half of it is the line.
            if took_ms >= max(2000, int(cfg.get("timeout") or 120) * 500):
                note_event("backend_slow", did=disp["id"] if disp else "",
                           level="warn", route=cfg.get("name") or rid,
                           ms=took_ms, detail="%dms" % took_ms)
            # A house being asked for things it cannot do, which is a fact
            # about how people are speaking to it rather than a fault.
            if out.get("code") == "no_intent_match":
                note_event("no_intent", did=disp["id"] if disp else "",
                           level="info", route=cfg.get("name") or rid,
                           detail=text[:120])
            fell_to = ""
            if out.get("code") == "no_intent_match" and cfg.get("fallthrough"):
                ft = cfg["fallthrough"]
                alt = doc["routes"].get(ft)
                # Strictly this route, not resolve_route's fallback to the
                # default: falling back there could hand the question to the
                # house that just declined it, or to somewhere nobody named.
                if alt and alt.get("enabled", True) and alt["provider"] != "demo":
                    try:
                        second = ask_backend(text, history, alt, tz=tz)
                    except Exception as exc:               # noqa: BLE001
                        print("fallthrough failed (%s -> %s): %s"
                              % (rid, ft, exc), flush=True)
                        # Audible, and NOT the house's own words. Those were
                        # "I couldn't understand that" — true of the house, and
                        # a lie about the system: the question was placed with
                        # somebody who could have answered it, and that failed.
                        # Speaking the refusal here would dress a broken model
                        # as a badly phrased question, which is the same defect
                        # as a light command that fails quietly, wearing a
                        # politer hat. The person waited the full timeout for
                        # it, too. The reason goes to the display's status
                        # line; the name of the second endpoint stays out of
                        # the air, since it is not one anybody addressed.
                        return self._json(502, dict(
                            about, ms=int((time.time() - t0) * 1000),
                            error=str(exc)))
                    else:
                        fell_to = alt["name"]
                        # The house's conversation id survives — the binding is
                        # still to the house, and the next turn goes there.
                        out = dict(out, reply=second.get("reply") or "", code="")

            ms = int((time.time() - t0) * 1000)
            reply = out.get("reply") or ""
            # The trail comes from the display, which is the only place it ever
            # existed: after the gate the wake word is stripped and the near
            # miss is gone. A turn typed into the composer carries none, and
            # gets none invented for it.
            trail = obj.get("trail") if isinstance(obj.get("trail"), dict) else None
            if not reply:
                note_turn(disp["id"] if disp else "", cfg.get("name") or rid,
                          (trail or {}).get("heard"), text, "", trail, ms,
                          error="that route returned nothing")
                return self._json(502, dict(about, ms=ms,
                                            error="that route returned nothing"))
            print("ask ok (%s %s) %dms%s"
                  % (rid, route_dest(cfg), ms,
                     " — fell through to " + fell_to if fell_to else ""),
                  flush=True)
            # `conversation_id` is the display's to hold: it owns the awake
            # window, and the server has no idea a conversation is in progress
            # between two requests. Nothing here ends one — see the note in
            # ask_homeassistant about the flag that used to.
            note_turn(disp["id"] if disp else "", cfg.get("name") or rid,
                      (trail or {}).get("heard"), text, reply, trail, ms,
                      fell_to=fell_to)
            return self._json(200, dict(about, reply=reply, ms=ms,
                                        conversation_id=out.get("conversation_id") or ""))

        if parsed.path == "/app":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            cfg, err = validate_app(obj, read_app())
            if err:
                return self._json(400, {"error": err})
            write_app(cfg)
            print("app settings saved by %s: http=%d https=%d admin=%d "
                  "session=%dm bind=%s%s"
                  % (s["user"], cfg["http_port"], cfg["https_port"],
                     cfg["admin_port"], cfg["session_idle_minutes"], cfg["bind"],
                     (" " + cfg["bind_address"]) if cfg["bind"] == "address" else ""),
                  flush=True)
            warn = posture_warning(cfg)
            if warn:
                print("  WARNING: " + warn, flush=True)
            return self._json(200, {"ok": True, "app": cfg,
                                    "pending": app_pending(cfg),
                                    "warning": warn,
                                    "running_warning": posture_warning(RUNNING),
                                    "running": RUNNING})

        if parsed.path == "/settings":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            # Two shapes. A bare object replaces the document, which is what
            # this route has always done. `{"settings": …, "merge": true}`
            # writes only the keys it carries and leaves the rest alone —
            # what a panel needs once each part of it commits separately,
            # because a full replace from one part would quietly publish
            # every unsaved edit made in another.
            if isinstance(obj.get("settings"), dict):
                incoming = obj["settings"]
                merge = bool(obj.get("merge"))
            else:
                incoming, merge = obj, False
            if merge:
                # Re-read inside the write lock's shadow rather than trusting
                # a copy this browser loaded minutes ago: two admins on two
                # tabs must not undo each other's untouched settings.
                stored = read_settings()
                stored.update(incoming)
                incoming = stored
            write_settings(incoming)
            print("settings saved (%d key%s%s) by %s"
                  % (len(obj.get("settings", obj)),
                     "" if len(obj.get("settings", obj)) == 1 else "s",
                     ", merged" if merge else "", s["user"]), flush=True)
            return self._json(200, {"ok": True, "keys": len(incoming)})

        if parsed.path == "/tts":
            note_use()
            if self._cap("speak")[1]:
                return
            raw = self._body(64 * 1024)
            if raw is None:
                return self._json(400, {"error": "empty or oversized body"})
            text = raw.decode("utf-8", "replace").strip()
            if not text:
                return self._json(400, {"error": "no text"})
            name = (parse_qs(parsed.query).get("voice") or [None])[0] \
                   or (voice_list()[0] if voice_list() else None)
            if not name:
                return self._json(503, {"error": "no voices installed"})
            t0 = time.time()
            try:
                wav = synth(text, name, (parse_qs(parsed.query).get("rate") or ["1"])[0])
            except Exception as exc:                       # noqa: BLE001
                return self._json(503, {"error": str(exc)})
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav)))
            self.send_header("X-Synth-Ms", str(int((time.time() - t0) * 1000)))
            self.send_header("X-Voice", name)
            self.end_headers()
            return self.wfile.write(wav)

        if parsed.path != "/stt":
            return self._json(404, {"error": "not found"})
        note_use()
        if self._cap("mic")[1]:
            return
        q = parse_qs(parsed.query)
        hint = (q.get("hint") or [None])[0]
        want = (q.get("model") or [None])[0]
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return self._json(400, {"error": "empty body"})
        if length > MAX_UPLOAD:
            return self._json(413, {"error": "audio too large"})

        raw = self.rfile.read(length)
        ctype = (self.headers.get("Content-Type") or "").lower()
        suffix = ".webm" if "webm" in ctype else ".ogg" if "ogg" in ctype else ".wav"
        t0 = time.time()
        try:
            text = transcribe(raw, suffix, hint, want)
        except Exception as exc:                           # noqa: BLE001
            return self._json(503, {"error": str(exc)})
        return self._json(200, {
            "text": text,
            "model": want if want in ALLOWED else MODEL_NAME,
            "ms": int((time.time() - t0) * 1000),
            "bytes": len(raw),
        })


def make_server(port, admin_port=False, host="0.0.0.0", redirect_to=None,
                pinned_net=""):
    handler = functools.partial(Handler, directory=ROOT, admin_port=admin_port,
                                redirect_to=redirect_to, pinned_net=pinned_net)
    return ThreadingHTTPServer((host, port), handler)


def start_tls(port, cert, key, admin_port=False, host="0.0.0.0", pinned_net=""):
    srv = make_server(port, admin_port=admin_port, host=host,
                      pinned_net=pinned_net)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    global SESSION_IDLE
    # Before anything can read a display. read_displays keeps only the keys in
    # DISPLAY_DEFAULTS, so the first write after an upgrade would drop the old
    # wall settings silently — see migrate_kiosks.
    migrate_kiosks()
    ensure_default_kiosk()
    migrate_models()
    migrate_networks()
    # The two groups that always exist. Made at startup rather than on first
    # need, so they are there before anything can enrol into them and there is
    # no moment where a population has nowhere to land.
    ensure_system_groups()
    migrate_pin_identities()
    migrate_unenrolled_invites()
    prune_group_members()
    ensure_default_membership()
    # Anything past the window, gone — read at startup as well as after a poll,
    # so a server that has been down for a fortnight does not come back holding
    # a fortnight of what was said to a screen.
    prune_events()
    prune_turns()
    app = read_app()
    # Environment still wins, so a one-off run on a different port needs no
    # edit to the stored configuration. Setting PORT alone moves all three,
    # as it always did — otherwise a second instance started with PORT=9800
    # would quietly try to bind the first one's admin port.
    def _env(name):
        try:
            return int(os.environ[name])
        except (KeyError, ValueError):
            return None
    # The display's ports are the DEFAULT network profile's now; app.json holds
    # the admin portal's and nothing else that is read. The stored values are
    # still the fallback for one case only — a settings document with no
    # network profiles at all, which is an install somebody has edited by hand
    # — because a server that cannot serve the display is worse than one on an
    # unexpected port, and the admin portal is how it gets fixed either way.
    _dnet = net_profile(display_settings()["network_default"]) or {}
    _dvals = _dnet.get("values") or {}
    shifted = _env("PORT") is not None
    tls_port = _env("HTTPS_PORT") or (_env("PORT") + 1 if shifted
                                      else _dvals.get("port") or app["https_port"])
    port = _env("PORT") or (_dvals.get("redirect") or 0)
    adm_port = _env("ADMIN_PORT") or (_env("PORT") + 2 if shifted
                                      else app["admin_port"])
    SESSION_IDLE = app["session_idle_minutes"] * 60
    host = bind_host(app)
    RUNNING.update({"http_port": port, "https_port": None, "admin_port": None,
                    "session_idle_minutes": app["session_idle_minutes"],
                    "bind": app["bind"], "bind_address": app["bind_address"],
                    "bind_host": host,
                    "exposed": exposed(app)})

    cert, key = os.path.join(ROOT, "cert.pem"), os.path.join(ROOT, "key.pem")
    have_tls = os.path.exists(cert) and os.path.exists(key)
    # Bound to loopback, a certificate is not part of the product. Browsers
    # treat http://localhost as a secure context, so the microphone works
    # unprompted and there is nothing for TLS to protect: the traffic never
    # leaves the machine. Start it, open localhost, talk to it — none of the
    # certificate ceremony applies. Anywhere else it is still required, and
    # the admin interface still refuses to exist without it.
    personal = not exposed(app)
    # Retire the plain listener into a redirect — but only where there is
    # somewhere to redirect TO. Beyond loopback with no certificate, HTTPS
    # does not exist, and sending every visitor to a dead port would take the
    # whole product off the air to enforce a rule it cannot satisfy. There it
    # keeps serving, and says why.
    redirect_plain = have_tls and not personal

    # The scheduled restart, if one is set. A daemon thread, so it never keeps
    # a dying process alive — and it reads the setting each time round rather
    # than at startup, so changing the time in the panel takes effect without
    # the restart this is here to schedule.
    threading.Thread(target=restart_watch, daemon=True).start()

    # warm the model in the background so the first utterance isn't slow
    for _n in (MODEL_NAME, "base.en"):      # warm both sides of the trade
        threading.Thread(target=get_model, args=(_n,), daemon=True).start()
    if voice_list():
        threading.Thread(target=get_voice, args=(voice_list()[0],), daemon=True).start()

    # The pair, reported as a pair. Not a name for the combination — a name
    # goes stale the moment one half of it changes.
    _dflt = display_settings()["network_default"]
    # EXISTING SHARERS, named out loud. The one-endpoint-per-port rule is
    # enforced where a save is made, not by rewriting somebody's configuration
    # on an upgrade — moving an assistant to a different port is a decision
    # with a URL on the other end of it. So an install that already shares one
    # keeps working and says so every time it starts, rather than staying
    # quiet until the next save is refused for a reason that looks new.
    _doc = read_routes()
    _byport, _adrift = {}, []
    for _rid, _r in _doc["routes"].items():
        if not _r.get("enabled", True):
            continue
        _on = str(_r.get("network") or "")
        if not _on:
            # NO PORT, SO NOWHERE. Named rather than counted: an assistant
            # nobody can reach is a fault, and the only thing worse than the
            # fault is it being invisible.
            _adrift.append(_r.get("name") or _rid)
            continue
        _byport.setdefault(_on, []).append(_r.get("name") or _rid)
    if _adrift:
        print("WARNING: %d endpoint(s) answer nowhere — no port is selected "
              "for %s. Give each one a network profile under PROFILES \u25b8 "
              "NETWORK, or it cannot be reached."
              % (len(_adrift), ", ".join(sorted(_adrift))), flush=True)
    for _nid, _names in sorted(_byport.items()):
        if len(_names) > 1:
            _prof = net_profile(_nid) or {}
            print("WARNING: %d endpoints share one port (%s): %s — a port "
                  "carries one endpoint now, and saving any of them is "
                  "refused until they are moved apart"
                  % (len(_names), _prof.get("name") or "the display port",
                     ", ".join(sorted(_names))), flush=True)
    _shut = sum(1 for r in read_routes()["routes"].values()
                if r.get("enabled", True) and r.get("needs_signin"))
    _all = sum(1 for r in read_routes()["routes"].values()
               if r.get("enabled", True))
    print("reachable at %s · %d of %d assistant(s) need a sign-in" % (
        "this machine only (loopback)" if personal else
        "every interface on this machine" if host == "0.0.0.0" else host,
        _shut, _all), flush=True)

    if have_tls:
        # Pinned to the default profile, so an endpoint moved onto a port of
        # its own leaves this one. An endpoint belongs to exactly one network
        # profile; a port carrying several is what SHARED is for.
        start_tls(tls_port, cert, key, host=host, pinned_net=_dflt)
        RUNNING["https_port"] = tls_port
        print("HTTPS on %s:%d  (mic + local STT work here)" % (host, tls_port),
              flush=True)
    elif personal:
        # Not a degraded install. http://localhost is a secure context, so the
        # microphone works here with no certificate and no browser warning.
        print("no cert.pem/key.pem — not needed on loopback, where the browser "
              "already treats this as a secure origin", flush=True)
    else:
        print("no cert.pem/key.pem — HTTPS disabled, mic will be blocked", flush=True)

    # Reading it here also performs the migration, so an upgrade turns its
    # single assistant into route one while somebody is watching the console
    # rather than silently on the first question anybody asks.
    _doc = read_routes()
    for _rid in route_order(_doc):
        # Resolved through the model profile, like every other reader: printing
        # the route's own fields would have shown DEMO for everything the
        # moment those fields stopped being kept.
        _r = with_model(_doc["routes"][_rid])
        print("route %-10s “%s”%s%s%s" % (
            _r["name"], _r["wakeword"],
            "" if _r["provider"] == "demo" else
            " · %s · %s" % (route_dest(_r), _r["base_url"]),
            "  (default)" if _rid == _doc["default"] else "",
            "" if _r.get("enabled", True) else "  — not answering"), flush=True)

    # One listener per network profile, and its plain-HTTP companion where the
    # profile names one. Bound here rather than on save: a listening socket is
    # not something to open and close under an admin's mouse, which is the
    # same reason the admin portal's port has always taken a restart.
    #
    # The NOMINATED profile is skipped — it is the display listener started
    # above, and binding it twice would be the server colliding with itself.
    _dflt_id = display_settings()["network_default"]
    for _n in display_settings()["networks"]:
        if _n["id"] == _dflt_id:
            continue
        _mine = [r for r in net_members(_doc, _n["id"])
                 if _doc["routes"][r].get("enabled", True)]
        if not _mine:
            # A port nothing answers on would accept connections and then have
            # nothing to say. Said out loud rather than bound: a profile
            # nobody has pointed an endpoint at is usually one half of a job.
            print("network %-10s not bound — no endpoint answers on it"
                  % _n["name"], flush=True)
            continue
        _vals = _n.get("values") or {}
        try:
            _p = int(_vals.get("port"))
        except (TypeError, ValueError):
            continue
        # The address this profile answers on, or the server's own where it
        # says ANY. A profile does not get to reach further than the app it
        # belongs to: bound to loopback, ANY is loopback.
        _host = net_host(_vals, host)
        for _bind, _to in ((_p, None), (int(_vals.get("redirect") or 0), _p)):
            if not _bind:
                continue
            try:
                if have_tls and _to is None:
                    start_tls(_bind, cert, key, host=_host, pinned_net=_n["id"])
                else:
                    _srv = make_server(_bind, host=_host, pinned_net=_n["id"],
                                       redirect_to=_to if have_tls else None)
                    threading.Thread(target=_srv.serve_forever,
                                     daemon=True).start()
            except OSError as exc:
                # One profile's port being taken is not a reason for the server
                # not to come up: everything else still answers, and the admin
                # needs the panel in order to fix it.
                print("network %-10s port %d NOT bound: %s"
                      % (_n["name"], _bind, exc), flush=True)
                continue
            _BOUND.add((_host, _bind))
            if _to is not None:
                print("HTTP  on %s:%d  → redirects to %d" % (_host, _bind, _p),
                      flush=True)
            else:
                print("%-5s on %s:%d  → %s"
                      % ("HTTPS" if have_tls else "HTTP", _host, _bind,
                         ", ".join(_doc["routes"][r]["name"] for r in _mine)),
                      flush=True)

    if not port:
        pass                     # the default profile names no plain port
    elif redirect_plain:
        print("HTTP  on %s:%d  → redirects to HTTPS on %d"
              % (host, port, tls_port), flush=True)
    else:
        print("HTTP  on %s:%d  (no-store)%s" % (host, port,
              "  — mic works, this is a secure origin" if personal else ""),
              flush=True)

    # ---- admin listener ----
    # HTTPS, or loopback, or nothing. The rule was "HTTPS or nothing" because
    # this interface takes a password and holds the assistant's API key, and
    # neither may cross a network in the clear. On loopback nothing crosses a
    # network at all, so the reason does not apply and the certificate
    # ceremony it forces is pure obstruction — which is exactly the install
    # this setting exists to make possible.
    if have_tls or personal:
        # ALWAYS. The panel is always signed into now, so an install that
        # reaches this line with no account is an admin interface nobody can
        # open — and the only way back would be editing JSON on the box. It
        # was conditional while a mode existed that needed no key at all.
        first_pw = ensure_first_admin()
        if have_tls:
            start_tls(adm_port, cert, key, admin_port=True, host=host)
        else:
            srv = make_server(adm_port, admin_port=True, host=host)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        RUNNING["admin_port"] = adm_port
        # No second half about sign-in: there is only one answer now, and a
        # banner that reports a constant is a banner people stop reading.
        print("ADMIN on %s:%d  (%s, sign-in required)"
              % (host, adm_port, "HTTPS" if have_tls else "HTTP on loopback"),
              flush=True)
        if first_pw:
            print("", flush=True)
            print("  first-run account created — this is printed ONCE:", flush=True)
            print("      username: admin", flush=True)
            print("      password: %s" % first_pw, flush=True)
            print("  change it after signing in.", flush=True)
            print("", flush=True)
        else:
            print("       %d account(s) configured" % len(read_users()), flush=True)
    else:
        print("ADMIN disabled — it takes a password and refuses to serve one "
              "over plain HTTP.", flush=True)
        print("       run ./make-cert.sh <host> and restart, or bind to "
              "loopback, where no certificate is needed.", flush=True)

    warn = posture_warning(app)
    if warn:
        # Loud on purpose, and every restart rather than once. A machine set up
        # this way on a network its owner controls may later join one they do
        # not, and the setting will not have changed on the day that matters.
        print("", flush=True)
        print("  " + "!" * 68, flush=True)
        print("  NO SIGN-IN, AND REACHABLE FROM THE NETWORK", flush=True)
        print("  " + warn, flush=True)
        print("  Bind to loopback, or switch sign-in to accounts, in ADMIN "
              "SETTINGS.", flush=True)
        print("  " + "!" * 68, flush=True)
        print("", flush=True)

    if port:
        make_server(port, host=host, pinned_net=_dflt,
                    redirect_to=tls_port if redirect_plain else None
                    ).serve_forever()
    else:
        # The default profile names no plain HTTP port, so there is no
        # foreground listener to run. Everything is on daemon threads, and a
        # process that returned from main() here would take them with it.
        print("no plain HTTP port on the default network profile", flush=True)
        threading.Event().wait()


if __name__ == "__main__":
    main()
