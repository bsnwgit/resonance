#!/usr/bin/env python3
"""Static server + local speech-to-text for Resonance.

Listeners:
  PORT      (default 9700) plain HTTP  — redirects to HTTPS, except where it
                                         is the whole product (see below)
  PORT + 1  (default 9701) HTTPS       — required for getUserMedia, which the
                                         browser refuses on an insecure origin
  PORT + 2  (default 9702) ADMIN       — the configuration interface

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
import base64, functools, hashlib, hmac, http.cookies, inspect, json, os, re, \
       secrets, ssl, sys, tempfile, threading, time
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
    "auth": "accounts",              # none | accounts
}
PORT_MIN, PORT_MAX = 1024, 65535     # below 1024 needs root; this runs as you
SESSION_MIN, SESSION_MAX = 5, 480    # minutes: below 5 is unusable, above 8h absurd
BIND_MODES = ("loopback", "address", "everything")
# "pin" — one number for the whole display, no accounts — is the middle rung
# and is not here yet. It is the identity work's PIN machinery pointed at the
# display rather than at a named person, so it lands with that rather than
# being built twice. Named here so the omission is deliberate and visible.
AUTH_MODES = ("none", "accounts")
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
    from the network, and nothing at the door. Not refused — somebody may want
    exactly this on a network they control — but a laptop configured this way
    that later joins an office network must say so."""
    if cfg.get("auth") == "none" and exposed(cfg):
        where = ("every interface on this machine" if bind_host(cfg) == "0.0.0.0"
                 else bind_host(cfg))
        return ("Reachable at %s with no sign-in — anyone who can reach this "
                "machine can change its configuration, including the "
                "assistant's API key." % where)
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

    # continue_conversation decides whether to hang up, and it belongs to the
    # reply rather than to the configuration: a command should acknowledge and
    # close, but "turn on the lights" answered with "which room?" has to stay
    # open, and a route configured one-shot would hang up on the question it
    # just asked. Absent — an older Home Assistant that does not send it — is
    # not false: staying awake is the behaviour every other adapter has.
    return {"reply": speech, "code": code,
            "hangup": j.get("continue_conversation") is False,
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
})
MAX_ROUTES = 24                  # a household, not a directory service


def _norm_word(s):
    """The matcher's normalisation, in Python. Wake words are compared here
    only to refuse an outright collision at the point of saving — the waking
    itself happens in the browser."""
    s = re.sub(r"[^a-z0-9\s]", " ", str(s or "").lower())
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
    rec["wakeword"] = _norm_word(stored.get("wakeword")) or ROUTE_DEFAULTS["wakeword"]
    rec["aliases"] = [w for w in (_norm_word(a) for a in
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
                out["aliases"] = [w for w in (_norm_word(a) for a in
                                              (rec.get("aliases") or [])) if w]
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


def public_routes(doc):
    """The two halves a browser may see. The connection half is not omitted
    from the serialisation by accident — it is enumerated the other way
    round, so a field added to a route later is private until somebody
    decides otherwise."""
    return [dict({k: doc["routes"][rid][k] for k in ROUTE_PUBLIC}, id=rid)
            for rid in route_order(doc)
            if doc["routes"][rid].get("enabled", True)]


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
    gone quiet for a reason nobody standing in front of it can see."""
    if rid and rid in doc["routes"] and doc["routes"][rid].get("enabled", True):
        return rid, doc["routes"][rid]
    d = doc["default"]
    if d in doc["routes"] and doc["routes"][d].get("enabled", True):
        return d, doc["routes"][d]
    for r in route_order(doc):
        if doc["routes"][r].get("enabled", True):
            return r, doc["routes"][r]
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
    if "wakeword" in obj:
        rec["wakeword"] = _norm_word(obj["wakeword"])[:40]
    if not rec["wakeword"]:
        return None, "a route needs a wake word — it is how anybody reaches it"
    if "aliases" in obj:
        raw = obj["aliases"]
        if not isinstance(raw, (list, tuple)):
            raw = re.split(r"[\n,]", str(raw or ""))
        seen, out = set(), []
        for a in raw:
            w = _norm_word(a)[:40]
            if w and w not in seen:
                seen.add(w)
                out.append(w)
        rec["aliases"] = out[:20]

    # Two routes answering to the same word is not a preference, it is a
    # route nobody can reach. Refused here at the point of entry; words that
    # are merely CLOSE are the personal-wake-word phase's problem, and want
    # the matcher that does the waking rather than a string comparison.
    mine = set([rec["wakeword"]] + list(rec["aliases"]))
    for other, o in doc["routes"].items():
        if other == rid:
            continue
        clash = mine & set([o["wakeword"]] + list(o.get("aliases") or []))
        if clash:
            return None, ("“%s” already reaches %s"
                          % (sorted(clash)[0], o["name"]))
    return rec, None


def validate_app(obj, current):
    """Returns (config, error). Refuses anything that would leave the server
    unable to start, because the only way back would be editing JSON on the
    box by hand."""
    cfg = dict(current)
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

    host = bind_host(cfg)
    for k in ("http_port", "https_port", "admin_port"):
        if cfg[k] != current[k] and not port_free(cfg[k], host):
            return None, ("port %d is already in use by something else on this "
                          "machine — the server would fail to start on it"
                          % cfg[k])

    if "auth" in obj:
        v = str(obj["auth"] or "").strip()
        if v not in AUTH_MODES:
            # The rung that is specified but not built. Saying so beats a
            # generic "not one of" that reads like a typo in the request.
            if v == "pin":
                return None, ("a single PIN with no accounts is not built yet — "
                              "it arrives with identity")
            return None, "sign-in must be one of: " + ", ".join(AUTH_MODES)
        cfg["auth"] = v
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

# ------------------------------------------------------------------ accounts
# Local accounts only. No directory, no third party, no network call to log in
# — the same principle as the speech pipeline. Two roles:
#   admin   configure everything, manage accounts
#   viewer  read the configuration, change nothing
ROLES = ("admin", "viewer")
PBKDF2_ROUNDS = 600_000          # ~0.3s per attempt: cheap once, costly to grind
SESSION_IDLE = 30 * 60           # inactivity before a session dies; set at startup
RUNNING = {}                     # what is actually bound, to compare against config
# Read once at startup rather than per request, for the same reason the ports
# are: this decides what a listener IS, and a listener cannot be re-founded
# under the requests already in flight on it.
AUTH_MODE = "accounts"


def app_pending(cfg):
    """Which stored settings differ from what is actually running, and so are
    waiting on a restart. One implementation, because this is read by the panel
    on load and again on save, and two copies would drift into disagreeing
    about whether a restart is owed."""
    keys = ("http_port", "https_port", "admin_port", "session_idle_minutes",
            "bind", "bind_address", "auth")
    return sorted(k for k in keys
                  if RUNNING.get(k) is not None and RUNNING[k] != cfg[k])
MIN_PASSWORD = 10
_users_lock = threading.Lock()
_sessions = {}                   # token -> {"user","role","expires"}
_sessions_lock = threading.Lock()
_login_fails = {}                # client ip -> [count, blocked_until]


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return salt.hex(), dk.hex()


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

ALLOWED = ("base.en", "small.en", "distil-small.en", "medium.en")
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
                     "/embeds", "/embeds/delete", "/embeds/enable")
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

    def __init__(self, *args, admin_port=False, redirect_to=None, **kw):
        # must land before super().__init__, which serves the request outright
        self.admin_port = admin_port
        self.redirect_to = redirect_to
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
        if AUTH_MODE == "none":
            # Nothing at the door, by configuration. Everyone who reaches this
            # listener is an admin — which is the whole of the setting, and why
            # it is only defensible when the network is the boundary. The name
            # is not a username: it is what the panel and the log should say
            # instead of implying somebody signed in as somebody.
            return {"user": "(no sign-in)", "role": "admin"}
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
            # The warning rides along because the display has to be able to
            # say it too — a startup banner is seen by whoever ran the
            # command, and the person who needs to know a screen is wide open
            # is usually the person standing in front of it. It discloses
            # nothing: anyone who can read this can already open the admin
            # port and find out the same thing by getting in.
            return self._json(200, {"settings": read_settings(),
                                    "warning": posture_warning(RUNNING)})
        if path == "/auth/me":
            s = self._session()
            if not s:
                return self._json(401, {"error": "not signed in"})
            # The panel needs to tell "signed in as an admin" from "there is no
            # sign-in here" — they grant the same access and want different
            # words, and one of them has no account to offer or to sign out of.
            return self._json(200, {"user": s["user"], "role": s["role"],
                                    "no_auth": AUTH_MODE == "none"})
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
            # public, and only two thirds of a route. Presentation is what
            # makes a newly hung display look right; routing is what makes it
            # usable, and it moves behind the device token when displays land.
            # The connection half is not here at all, at any tier.
            doc = read_routes()
            return self._json(200, {"routes": public_routes(doc),
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
                                               "auth_modes": list(AUTH_MODES)}})
        if path == "/users":
            if not self._require("admin"):
                return
            if AUTH_MODE == "none":
                # Listing the accounts stored from a previous configuration
                # would show a set of people who cannot sign in and are not
                # keeping anybody out. An empty list plus the reason is truer.
                return self._json(200, {"users": [], "disabled": True})
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
        if AUTH_MODE == "none" and (parsed.path.startswith("/auth/")
                                    or parsed.path.startswith("/users")):
            return self._json(409, {"error": "this server is set to no sign-in — "
                                             "there are no accounts to manage. "
                                             "Switch sign-in to accounts in APP "
                                             "SETTINGS and restart."})

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
            write_routes(doc)
            # The wake word and the adapter kind, and never the key or the
            # URL it points at: a log is read by more people than the panel.
            print("route %s (%s) saved by %s: wake=%s adapter=%s key=%s"
                  % (rid, rec["name"], s["user"], rec["wakeword"],
                     rec["provider"], "set" if rec["api_key"] else "none"),
                  flush=True)
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
            rec = doc["routes"][rid]
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
                res["check"] = ("no command was recognised in the test "
                                "sentence, which is what the built-in intent "
                                "engine does with anything that is not one — "
                                "the address, the token and the agent are all "
                                "good. Ask it to switch something on to test "
                                "what is exposed."
                                if out.get("code") == "no_intent_match" else
                                "the agent answered — address, token and agent "
                                "are all good.")
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

        if parsed.path == "/ask":
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
            rid, cfg = resolve_route(doc, str(obj.get("route") or "")[:32])
            if not cfg:
                return self._json(503, {"error": "no route is answering"})
            # The route is named back on every reply, not just when it
            # changes: the display is entitled to know which one answered,
            # and the answer is the only place it could come from. The
            # adapter kind is deliberately not in here — see public_routes.
            about = {"route": rid, "name": cfg["name"]}
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
                    else:
                        fell_to = alt["name"]
                        # The house's conversation id survives — the binding is
                        # still to the house and the next turn goes there. Its
                        # hang-up does not: it was refusing a sentence, and
                        # closing the conversation on an answer somebody is
                        # still listening to is the one thing that would make
                        # this visible.
                        out = dict(out, reply=second.get("reply") or "",
                                   hangup=False, code="")

            ms = int((time.time() - t0) * 1000)
            reply = out.get("reply") or ""
            if not reply:
                return self._json(502, dict(about, ms=ms,
                                            error="that route returned nothing"))
            print("ask ok (%s %s) %dms%s"
                  % (rid, route_dest(cfg), ms,
                     " — fell through to " + fell_to if fell_to else ""),
                  flush=True)
            # `hangup` and `conversation_id` are the display's to act on: it
            # owns the awake window, and the server has no idea a conversation
            # is in progress between two requests.
            return self._json(200, dict(about, reply=reply, ms=ms,
                                        hangup=bool(out.get("hangup")),
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
                  "session=%dm bind=%s%s auth=%s"
                  % (s["user"], cfg["http_port"], cfg["https_port"],
                     cfg["admin_port"], cfg["session_idle_minutes"], cfg["bind"],
                     (" " + cfg["bind_address"]) if cfg["bind"] == "address" else "",
                     cfg["auth"]), flush=True)
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


def make_server(port, admin_port=False, host="0.0.0.0", redirect_to=None):
    handler = functools.partial(Handler, directory=ROOT, admin_port=admin_port,
                                redirect_to=redirect_to)
    return ThreadingHTTPServer((host, port), handler)


def start_tls(port, cert, key, admin_port=False, host="0.0.0.0"):
    srv = make_server(port, admin_port=admin_port, host=host)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    global SESSION_IDLE, AUTH_MODE
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
    port = _env("PORT") or app["http_port"]
    shifted = _env("PORT") is not None
    tls_port = _env("HTTPS_PORT") or (port + 1 if shifted else app["https_port"])
    adm_port = _env("ADMIN_PORT") or (port + 2 if shifted else app["admin_port"])
    SESSION_IDLE = app["session_idle_minutes"] * 60
    AUTH_MODE = app["auth"]
    host = bind_host(app)
    RUNNING.update({"http_port": port, "https_port": None, "admin_port": None,
                    "session_idle_minutes": app["session_idle_minutes"],
                    "bind": app["bind"], "bind_address": app["bind_address"],
                    "auth": app["auth"], "bind_host": host,
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

    # warm the model in the background so the first utterance isn't slow
    for _n in (MODEL_NAME, "base.en"):      # warm both sides of the trade
        threading.Thread(target=get_model, args=(_n,), daemon=True).start()
    if voice_list():
        threading.Thread(target=get_voice, args=(voice_list()[0],), daemon=True).start()

    # The pair, reported as a pair. Not a name for the combination — a name
    # goes stale the moment one half of it changes.
    print("reachable at %s · %s" % (
        "this machine only (loopback)" if personal else
        "every interface on this machine" if host == "0.0.0.0" else host,
        "no sign-in" if AUTH_MODE == "none" else "accounts and roles"), flush=True)

    if have_tls:
        start_tls(tls_port, cert, key, host=host)
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
        _r = _doc["routes"][_rid]
        print("route %-10s “%s”%s%s%s" % (
            _r["name"], _r["wakeword"],
            "" if _r["provider"] == "demo" else
            " · %s · %s" % (route_dest(_r), _r["base_url"]),
            "  (default)" if _rid == _doc["default"] else "",
            "" if _r.get("enabled", True) else "  — not answering"), flush=True)

    if redirect_plain:
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
        first_pw = ensure_first_admin() if AUTH_MODE == "accounts" else None
        if have_tls:
            start_tls(adm_port, cert, key, admin_port=True, host=host)
        else:
            srv = make_server(adm_port, admin_port=True, host=host)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        RUNNING["admin_port"] = adm_port
        print("ADMIN on %s:%d  (%s, %s)"
              % (host, adm_port, "HTTPS" if have_tls else "HTTP on loopback",
                 "no sign-in" if AUTH_MODE == "none" else "sign-in required"),
              flush=True)
        if first_pw:
            print("", flush=True)
            print("  first-run account created — this is printed ONCE:", flush=True)
            print("      username: admin", flush=True)
            print("      password: %s" % first_pw, flush=True)
            print("  change it after signing in.", flush=True)
            print("", flush=True)
        elif AUTH_MODE == "accounts":
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
        print("  Bind to loopback, or switch sign-in to accounts, in APP "
              "SETTINGS.", flush=True)
        print("  " + "!" * 68, flush=True)
        print("", flush=True)

    make_server(port, host=host,
                redirect_to=tls_port if redirect_plain else None).serve_forever()


if __name__ == "__main__":
    main()
