#!/usr/bin/env python3
"""Static server + local speech-to-text for Resonance.

Listeners:
  One per NETWORK PROFILE, each carrying the endpoints that name it — one
  assistant on a port of its own, or several told apart by wake word. The
  profile nominated DEFAULT is where an endpoint naming none of them answers,
  and an upgrade turns the ports an install already had into one called
  "Display" (9701, with 9700 redirecting to it).

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
    "displays": [],
    # …and the groups it names. Kept beside the individual list rather than
    # folded into it: a grant made to "the physics department" should still
    # read that way next year, and flattening it at the point of saving would
    # turn it into twelve ids nobody can maintain.
    "groups": [],
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


def public_routes(doc, disp=None):
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
        row.update(id=rid, allowed=display_may(disp, rec))
        if disp:
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

    The default profile also carries every endpoint that names no profile at
    all: that is what makes it the default, and it is why the default has to
    be shared."""
    if not nid:
        return list(route_order(doc))
    dflt = nid == display_settings()["network_default"]
    return [r for r in route_order(doc)
            if doc["routes"][r].get("network") == nid
            or (dflt and not doc["routes"][r].get("network"))]


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
        # A SHARED port carries as many endpoints as you like and tells them
        # apart by wake word, which is how the display port has always worked.
        # An exclusive one is the other thing you might want — a port that IS
        # one assistant — and a second endpoint claiming it would simply never
        # be reached, so it is refused rather than silently ignored.
        if nid:
            prof = next((p for p in pool if p["id"] == nid), {})
            if not (prof.get("values") or {}).get("shared"):
                other = [k for k, r in doc["routes"].items()
                         if k != rid and r.get("network") == nid]
                if other:
                    who = doc["routes"][other[0]].get("name") or "another endpoint"
                    return None, ("%s already answers on that port, and it is "
                                  "not marked shared — mark it shared, or give "
                                  "this one a port of its own" % who)
        rec["network"] = nid
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
# — so their credential is something they CARRY, which is the PIN, and it is
# the identity phase's to build. One mechanism, two ways of granting it.
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
CODE_TTL = 10 * 60               # you are standing in front of the screen
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
    # Which population this row belongs to when a group is drawn from one:
    # "user", "device", or blank for "work it out". Set by an admin, because
    # the inference below can only see how the row ARRIVED — and asking for
    # access is something a browser on one machine does, which describes a
    # device rather than a person. A person is an identity that carries from a
    # phone to a laptop, and nothing here issues one yet.
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
    "mode":    ("stack", "disc", "orb", "knot"),
}
#: How many appearance profiles may exist — the same reasoning and the same
#: number as the screensavers. A place, not a screen.
MAX_LOOKS = 8

#: The displays document's own settings, as opposed to the rows in it. Set in
#: the panel, and none of them needs a restart.
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
}
MAX_FORM_FIELDS = 5
#: (low, high) for each number the panel can set
DISPLAY_LIMITS = {"max_displays": (2, 5000), "max_pending": (1, 1000),
                  "guest_days": (1, 3650)}

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
        for r in rows:
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
                if v in seen:
                    return None, ("%s and %s are both on port %d"
                                  % (seen[v], r["name"], v))
                seen[v] = r["name"]
            r["values"]["port"] = pv
            r["values"]["redirect"] = rv
            r["values"]["shared"] = bool(r["values"].get("shared"))
            r["values"]["open"] = bool(r["values"].get("open"))
        cfg["networks"] = rows
        # There is always a default, and it is always shared. An endpoint
        # naming no profile lands on it, and a default that refused to carry
        # more than one endpoint would strand every one of them.
        want = str(obj.get("network_default") or cfg.get("network_default") or "")
        by_id = {r["id"]: r for r in rows}
        if want not in by_id:
            want = next((r["id"] for r in rows if r["values"].get("shared")), "")
        if rows and not want:
            return None, ("one network profile has to be shared — it is where "
                          "an endpoint that names none of them answers")
        if want and not by_id[want]["values"].get("shared"):
            return None, ("%s is the default, so it has to be shared — it is "
                          "where an endpoint that names no profile answers"
                          % by_id[want]["name"])
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
    # A profile list built before there was a default — an exclusive port made
    # for one endpoint, say — is not a reason to invent a second display port.
    # Nominate a shared one if there is one; otherwise the app's own ports
    # become the profile they always were in everything but name.
    pick = next((r["id"] for r in rows if (r["values"] or {}).get("shared")), "")
    if not pick:
        app = read_app()
        prof = {"id": "w" + secrets.token_hex(4), "name": "Display",
                "values": {"port": app["https_port"],
                           "redirect": app["http_port"],
                           "shared": True, "open": False}}
        rows = [prof] + rows
        pick = prof["id"]
        print("network migration: display ports %d/%d -> profile "
              "\u201cDisplay\u201d (shared)"
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
    return out, None


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
    rec.update(asked=asked, hint=hint, salt=salt, hash=dk,
               created=int(time.time()), last_seen=int(time.time()))
    displays[did] = rec
    write_displays(displays)
    return did + "." + secret, dict(rec, id=did)


def invite_display(name, by):
    """A row created from the panel, before the device it is for has ever been
    switched on. Approved from the moment it exists — an admin naming a screen
    and ticking the endpoints it may use IS the approval — but holding no
    token, so nothing can BE it until somebody types the code into the screen
    itself."""
    displays = read_displays()
    limit = display_settings()["max_displays"]
    if len(displays) >= limit:
        return None, ("that is %d displays already — remove one, or raise the "
                      "limit on the DISPLAYS tab" % limit)
    did = "d" + secrets.token_hex(6)
    now_ = int(time.time())
    rec = dict(DISPLAY_DEFAULTS)
    rec.update(name=name, approved=True, approved_by=by, approved_at=now_,
               created=now_, code=new_code(), code_expires=now_ + CODE_TTL)
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
    rec.update(salt="", hash="", approved=True,
               code=new_code(), code_expires=now_ + CODE_TTL)
    write_displays(displays)
    return dict(rec, id=did), None


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
        if (rec.get("code_expires") or 0) < now_:
            return None, "expired"
        secret = secrets.token_urlsafe(32)
        salt, dk = hash_key(secret)
        # Spent. The code is gone from the record before the token exists
        # anywhere else, so the same six characters cannot enrol a second
        # device however quickly somebody types them.
        rec.update(salt=salt, hash=dk, code="", code_expires=0,
                   last_seen=now_, approved=True)
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
    return dict(rec, id=did), None


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


def display_may(disp, route):
    """May this display use this endpoint?

    An endpoint with no allow-list is reachable by anything that can reach the
    port, which is what every endpoint was before displays existed — so an
    upgrade changes nothing until somebody restricts one, and the restriction
    is a thing you can see rather than a default nobody was told about.

    Where there IS one: approval is the floor. An unapproved device holding a
    freshly minted token is exactly the phone somebody typed the URL into."""
    if not route.get("restricted"):
        return True
    if not disp:
        return False
    # The preview is the panel. It is already signed in as an admin, who can
    # reach any endpoint from the panel anyway, and a preview that refused to
    # demonstrate half the endpoints would be lying in the other direction.
    if disp.get("preview"):
        return True
    # Expiry is checked here rather than at the door, which is what makes a
    # grant run out cleanly mid-conversation: the turn already in flight was
    # allowed when it started and finishes, and the next one is refused.
    if not disp.get("approved") or display_expired(disp):
        return False
    if disp["id"] in (route.get("displays") or []):
        return True
    # Grants add up: named directly, or named by a group it is in.
    return disp["id"] in group_members(route.get("groups"))


def admin_displays():
    """The list, less the credential. What a token IS never leaves this server
    — the panel shows the id, which says which device a row is about without
    being the thing that proves it."""
    out = []
    displays = read_displays()
    now_ = int(time.time())
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
        live = bool(rec.get("code")) and (rec.get("code_expires") or 0) > now_
        row.update(id=did, label=display_label(rec),
                   guest=is_guest(rec), expired=display_expired(rec),
                   # What it was SET to, and what it resolves to. The panel
                   # needs both: one is the control's value, the other is the
                   # answer a blank control is currently getting.
                   kind=str(rec.get("kind") or ""), group_kind=group_kind_of(rec),
                   # Three states, and the panel needs to tell them apart:
                   # INVITED is a row waiting for somebody to type its code
                   # into a screen, WAITING is a device that turned up on its
                   # own, and the rest are working.
                   enrolled=bool(rec.get("hash")),
                   code=rec["code"] if live else "",
                   code_left=max(0, (rec.get("code_expires") or 0) - now_) if live else 0,
                   refused=ref[0] if ref else 0,
                   refused_at=ref[1] if ref else 0,
                   refused_from=ref[2] if ref else "")
        out.append(row)
    return out


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
_groups_lock = threading.Lock()
GROUP_KINDS = ("user", "device")
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
        kind = rec.get("kind")
        out[str(gid)] = {
            "name": str(rec.get("name") or "")[:60],
            "kind": kind if kind in GROUP_KINDS else "device",
            "members": [str(m)[:32] for m in (rec.get("members") or [])][:MAX_ALLOW],
            "created": rec.get("created"), "created_by": rec.get("created_by"),
        }
    return out


def write_groups(groups):
    with _groups_lock:
        tmp = GROUPS_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"version": 1, "groups": groups}, fh, indent=2, sort_keys=True)
        os.replace(tmp, GROUPS_PATH)


def group_kind_of(rec):
    """Which population a display row belongs to.

    What an admin said it is, where they have said. Otherwise it is inferred
    from how the row arrived — asked for access, or issued a code — which is a
    guess about the wrong question: both of those happen in a browser on one
    machine. The inference is kept only so that every existing row has an
    answer without anybody visiting it."""
    k = str(rec.get("kind") or "")
    if k in GROUP_KINDS:
        return k
    return "user" if is_guest(rec) else "device"


def clean_members(ids, kind):
    """Only rows that exist, and only of this group's own kind. A member that
    is neither is dropped rather than refused — the panel sends the list it was
    shown, and a display deleted in another tab between the two is not a
    mistake worth making somebody retype a form over."""
    displays = read_displays()
    seen, out = set(), []
    for did in (ids or []):
        did = str(did)[:32]
        rec = displays.get(did)
        if rec and did not in seen and group_kind_of(rec) == kind:
            seen.add(did)
            out.append(did)
    return out[:MAX_ALLOW]


def group_members(gids, groups=None):
    """Every display id named by these groups, flattened. Grants ADD UP: this
    is unioned with an endpoint's individually named displays, and being in a
    group never takes an individual grant away."""
    groups = read_groups() if groups is None else groups
    out = set()
    for gid in (gids or []):
        rec = groups.get(gid)
        if rec:
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
        rec["kind"] = k
    if "members" in obj:
        rec["members"] = clean_members(obj["members"], rec["kind"])
    return rec, None


def admin_groups():
    groups = read_groups()
    displays = read_displays()
    out = []
    for gid, rec in sorted(groups.items(),
                           key=lambda kv: (kv[1]["kind"], kv[1]["name"].lower())):
        # Named rows only. A member whose display was deleted is not shown as a
        # phantom — it is simply gone, the same way a deleted display leaves an
        # endpoint's allow-list.
        live = [m for m in rec["members"] if m in displays]
        out.append(dict(rec, id=gid, members=live,
                        labels=[display_label(displays[m]) for m in live]))
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
                     "/groups", "/groups/save", "/groups/delete")
#: where an enrolment code is typed. On the display listeners only — it hands
#: out a display's token, and the admin listener is not a display.
ENROL_PREFIX = "/e/"
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

    @property
    def pinned_open(self):
        """Whether reaching this port is itself the grant. Read live off the
        profile rather than captured at bind time, so turning it off takes
        effect on the next request instead of at the next restart — the socket
        is the part that cannot move without one."""
        n = net_profile(self.pinned_net)
        return bool((n.get("values") or {}).get("open")) if n else False

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
        state = ("denied" if rec.get("denied")
                 else "expired" if expired
                 else "approved" if working
                 else "requested" if rec.get("requested_at")
                 else "none")
        may_ask = (cfg["guest_requests"] and not working
                   and not (rec.get("denied") and not rec.get("deny_repeat", True)))
        if self.pinned_open:
            # Reaching this port is the grant. There is nothing to ask for and
            # nothing to wait on, so the page gets its composer rather than a
            # form — the row still exists and still says what this device is,
            # and it is this PORT that has stopped gating on it.
            working, state, may_ask = True, "approved", False
        out = {"id": rec.get("id", ""), "name": display_label(rec),
               "approved": working, "state": state,
               "can_request": bool(may_ask),
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
            print("display %s (%s) enrolled by code" % (out["id"], display_label(out)),
                  flush=True)
            _back("ok")
            self._set_display_cookie(token)
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
            # Public, and only two thirds of a route. Presentation is what
            # makes a newly hung display look right; routing is what makes it
            # usable, and it is behind the display token — so a browser that
            # has said hello gets the words, and anything that has not gets a
            # page that draws correctly and answers to nothing. The connection
            # half is not here at all, at any tier.
            doc = read_routes()
            rows = public_routes(doc, self._display())
            if self.pinned_net:
                # This port carries its own endpoints and no others. They are
                # not filtered out of a list the browser then ignores — they
                # never leave here, which is the rule the connection half
                # already follows. One endpoint on an exclusive port, several
                # told apart by wake word on a shared one: the same page
                # either way, built from what it was told.
                mine = net_members(doc, self.pinned_net)
                rows = [r for r in rows if r["id"] in mine]
                if self.pinned_open:
                    for r in rows:
                        r["allowed"] = True
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
                                    "enrol_base": "%s://%s:%d/e/"
                                                  % ("https" if secure else "http", host,
                                                     secure or RUNNING.get("http_port") or 0)})
        if path == "/groups":
            if not self._require("admin"):
                return
            # The two populations a group can be drawn from, so the panel can
            # offer the right one rather than every row it has ever seen.
            displays = read_displays()
            people, devices = [], []
            for did, rec in sorted(displays.items(),
                                   key=lambda kv: display_label(kv[1]).lower()):
                row = {"id": did, "label": display_label(rec),
                       "approved": bool(rec.get("approved"))}
                (people if group_kind_of(rec) == "user" else devices).append(row)
            return self._json(200, {"groups": admin_groups(),
                                    "people": people, "devices": devices,
                                    "kinds": list(GROUP_KINDS),
                                    "max": MAX_GROUPS})
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
            rec, err = invite_display(str(obj.get("name") or "").strip()[:40],
                                      s["user"])
            if err:
                return self._json(400, {"error": err})
            print("display %s (%s) invited by %s — code issued"
                  % (rec["id"], display_label(rec), s["user"]), flush=True)
            return self._json(200, {"ok": True, "id": rec["id"],
                                    "code": rec["code"],
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
            return self._json(200, {"ok": True, "id": rec["id"],
                                    "code": rec["code"],
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
            displays[did].update(fields)
            write_displays(displays)
            return self._json(200, {"ok": True, "id": did,
                                    "displays": admin_displays()})

        if parsed.path == "/displays/kind":
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
            want = str(obj.get("kind") or "")
            if want and want not in GROUP_KINDS:
                return self._json(400, {"error": "kind must be one of: "
                                                 + ", ".join(GROUP_KINDS)})
            was = group_kind_of(displays[did])
            displays[did]["kind"] = want
            now = group_kind_of(displays[did])
            write_displays(displays)
            # A group is drawn from one population, and clean_members drops a
            # member of the wrong one — silently, at the next save of that
            # group. Done here instead, and counted, so moving a row between
            # populations says what it cost rather than emptying a group
            # somebody built weeks ago with nothing on screen about it.
            dropped = []
            if now != was:
                groups = read_groups()
                touched = False
                for gid, g in groups.items():
                    if g["kind"] != now and did in (g.get("members") or []):
                        g["members"] = [m for m in g["members"] if m != did]
                        dropped.append(g["name"])
                        touched = True
                if touched:
                    write_groups(groups)
            print("display %s kind=%s by %s%s"
                  % (did, want or "(inferred: %s)" % now, s["user"],
                     "; dropped from " + ", ".join(dropped) if dropped else ""),
                  flush=True)
            return self._json(200, {"ok": True, "displays": admin_displays(),
                                    "dropped": dropped})

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
            print("display %s (%s) deleted by %s%s"
                  % (did, name, s["user"],
                     " — removed from %d endpoint(s)" % len(touched)
                     if touched else ""), flush=True)
            # Its token still exists in a cookie jar somewhere and now matches
            # nothing, so the device it belonged to is back to being a browser
            # that has never been here. That is the revocation.
            return self._json(200, {"ok": True, "displays": admin_displays()})

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
            disp = None if emb else self._display()
            if not (self.pinned_open or display_may(disp, cfg)):
                note_display_refused(disp, cfg["name"])
                print("refused: %s may not use %s (%s)"
                      % (disp["id"] if disp else "a display with no token",
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
            if not reply:
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
    global SESSION_IDLE, AUTH_MODE
    # Before anything can read a display. read_displays keeps only the keys in
    # DISPLAY_DEFAULTS, so the first write after an upgrade would drop the old
    # wall settings silently — see migrate_kiosks.
    migrate_kiosks()
    ensure_default_kiosk()
    migrate_models()
    migrate_networks()
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
    _dflt = display_settings()["network_default"]
    print("reachable at %s · %s" % (
        "this machine only (loopback)" if personal else
        "every interface on this machine" if host == "0.0.0.0" else host,
        "no sign-in" if AUTH_MODE == "none" else "accounts and roles"), flush=True)

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
    # The DEFAULT profile is skipped — it is the display listener started
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
        for _bind, _to in ((_p, None), (int(_vals.get("redirect") or 0), _p)):
            if not _bind:
                continue
            try:
                if have_tls and _to is None:
                    start_tls(_bind, cert, key, host=host, pinned_net=_n["id"])
                else:
                    _srv = make_server(_bind, host=host, pinned_net=_n["id"],
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
            if _to is not None:
                print("HTTP  on %s:%d  → redirects to %d" % (host, _bind, _p),
                      flush=True)
            else:
                print("%-5s on %s:%d  → %s%s"
                      % ("HTTPS" if have_tls else "HTTP", host, _bind,
                         ", ".join(_doc["routes"][r]["name"] for r in _mine),
                         "  (no approval — the port is the grant)"
                         if _vals.get("open") else ""), flush=True)

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
