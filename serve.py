#!/usr/bin/env python3
"""Static server + local speech-to-text for Resonance.

Listeners:
  PORT      (default 9700) plain HTTP  — fine for everything except the mic
  PORT + 1  (default 9701) HTTPS       — required for getUserMedia, which the
                                         browser refuses on an insecure origin
  PORT + 2  (default 9702) HTTPS ADMIN — the configuration interface, behind a
                                         username and password

The admin listener is HTTPS-only and deliberately refuses to start without a
certificate: it takes a password, and a password over plain HTTP crosses the
network in the clear. If it is missing from the startup banner, run
make-cert.sh. There is no way to write settings from the public listeners —
they serve the display and answer GET /settings, nothing more.

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

ROOT = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(ROOT, "settings.json")
USERS_PATH = os.path.join(ROOT, "users.json")
APP_PATH = os.path.join(ROOT, "app.json")
BACKEND_PATH = os.path.join(ROOT, "backend.json")
_settings_lock = threading.Lock()
_app_lock = threading.Lock()
_backend_lock = threading.Lock()

# ------------------------------------------------------------------ backend
# Which assistant answers, and how to reach it. Deliberately NOT part of
# settings.json: that document is world-readable by design — every viewer
# builds their interface from it — so an API key placed there would be handed
# to anyone who opens the page. Same reasoning that put accounts in their own
# file. This one is admin-only and the key never leaves the server.
BACKEND_DEFAULTS = {
    "provider": "demo",                 # demo | openai
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
}
OPENAI_DIALECT = ("openai",)            # anthropic joins this when there is a key to test
MAX_HISTORY = 24                        # hard ceiling regardless of configuration

# ------------------------------------------------------------ app settings
# How the server itself is wired, as opposed to how the interface looks.
# Editable from the admin page, but nothing here can take effect until the
# process restarts — you cannot move the floor you are standing on.
APP_DEFAULTS = {
    "http_port": 9700,               # the display, no microphone
    "https_port": 9701,              # the display in full
    "admin_port": 9702,              # this interface
    "session_idle_hours": 8,
}
PORT_MIN, PORT_MAX = 1024, 65535     # below 1024 needs root; this runs as you


def read_app():
    cfg = dict(APP_DEFAULTS)
    try:
        with open(APP_PATH) as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
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


def port_free(p):
    """Can we actually bind it? A port already taken by something else would
    otherwise pass validation and only fail at the next restart — by which
    point the admin interface is gone and the fix is editing JSON on the box
    by hand. Ports this process already holds are its own and count as free."""
    import socket
    if p in (RUNNING.get("http_port"), RUNNING.get("https_port"),
             RUNNING.get("admin_port")):
        return True
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", p))
        return True
    except OSError:
        return False
    finally:
        s.close()


def read_backend():
    cfg = dict(BACKEND_DEFAULTS)
    try:
        with open(BACKEND_PATH) as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            cfg.update({k: v for k, v in stored.items() if k in BACKEND_DEFAULTS})
    except (OSError, ValueError):
        pass
    return cfg


def write_backend(cfg):
    with _backend_lock:
        tmp = BACKEND_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(cfg, fh, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)                     # it holds a credential
        os.replace(tmp, BACKEND_PATH)


def validate_backend(obj, current):
    """Returns (config, error). Refuses a configuration that cannot work,
    rather than accepting it and failing later in front of somebody."""
    cfg = dict(current)
    for k in ("provider", "base_url", "model", "system", "keep_alive"):
        if k in obj:
            cfg[k] = str(obj[k] or "").strip()
    if cfg["provider"] not in ("demo",) + OPENAI_DIALECT:
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
    if cfg["provider"] != "demo":
        if not cfg["model"]:
            return None, "a model is required"
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


def ask_backend(text, history, cfg):
    """One turn against whichever assistant is configured.

    `openai` is the dialect, not the vendor: Ollama, OpenClaw, LM Studio and
    vLLM all speak it, so one adapter reaches all of them and the difference
    is a base URL."""
    turns = [m for m in history if isinstance(m, dict)
             and m.get("role") in ("user", "assistant") and m.get("content")]
    keep = max(0, min(int(cfg.get("history_turns") or 0), MAX_HISTORY))
    msgs = [{"role": m["role"], "content": str(m["content"])[:8000]}
            for m in turns[-keep:]] if keep else []
    msgs.append({"role": "user", "content": text})

    if cfg["provider"] in OPENAI_DIALECT:
        base = (cfg.get("base_url") or "").rstrip("/")
        url = base if base.endswith("/chat/completions") else base + "/chat/completions"
        if cfg.get("system"):
            msgs = [{"role": "system", "content": cfg["system"]}] + msgs
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
        return ((choices[0].get("message") or {}).get("content") or "").strip()

    raise RuntimeError("provider '%s' has no adapter" % cfg["provider"])


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
    for k in ("http_port", "https_port", "admin_port"):
        if cfg[k] != current[k] and not port_free(cfg[k]):
            return None, ("port %d is already in use by something else on this "
                          "machine — the server would fail to start on it"
                          % cfg[k])
    if "session_idle_hours" in obj:
        try:
            h = int(obj["session_idle_hours"])
        except (TypeError, ValueError):
            return None, "session length must be a whole number of hours"
        if not (1 <= h <= 168):
            return None, "session length must be between 1 and 168 hours"
        cfg["session_idle_hours"] = h
    return cfg, None

# ------------------------------------------------------------------ accounts
# Local accounts only. No directory, no third party, no network call to log in
# — the same principle as the speech pipeline. Two roles:
#   admin   configure everything, manage accounts
#   viewer  read the configuration, change nothing
ROLES = ("admin", "viewer")
PBKDF2_ROUNDS = 600_000          # ~0.3s per attempt: cheap once, costly to grind
SESSION_IDLE = 8 * 3600          # inactivity before a session dies; set at startup
RUNNING = {}                     # the ports actually bound, to compare against config
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


def get_session(token):
    """Sliding expiry: every authenticated request pushes the deadline out, so
    a session dies from inactivity rather than mid-edit."""
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


def read_settings():
    try:
        with open(SETTINGS_PATH) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


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
#: exist only on the admin listener; anywhere else they are simply not there
ADMIN_ONLY_ROUTES = ("/users", "/users/delete", "/users/role", "/app",
                     "/backend")


class Handler(SimpleHTTPRequestHandler):
    #: set per-listener by make_server — the admin port is a different surface
    #: with different rules, not the same surface with an extra check
    admin_port = False

    def __init__(self, *args, admin_port=False, **kw):
        # must land before super().__init__, which serves the request outright
        self.admin_port = admin_port
        super().__init__(*args, **kw)

    # ---------- no-cache ----------
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def send_header(self, keyword, value):
        # drop the validator that lets a browser answer from cache
        if keyword.lower() == "last-modified":
            return
        super().send_header(keyword, value)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # ---------- json helper ----------
    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---------- identity ----------
    def _session(self):
        """Who is calling, or None. Only ever consulted on the admin port —
        a cookie replayed at the public listeners buys nothing, because those
        listeners have no privileged route to reach."""
        if not self.admin_port:
            return None
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        try:
            jar = http.cookies.SimpleCookie(raw)
        except http.cookies.CookieError:
            return None
        morsel = jar.get(SESSION_COOKIE)
        return get_session(morsel.value) if morsel else None

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
    def do_GET(self):
        route = self.path.split("?")[0]
        # The configuration interface does not exist as far as the public
        # listeners are concerned — not hidden by CSS, not gated in JS, absent.
        # Answering 401 here would still confirm the route is there; 404 is
        # the honest answer, because on this listener it genuinely is not.
        if not self.admin_port and (route in ADMIN_ONLY_FILES
                                    or route in ADMIN_ONLY_ROUTES
                                    or route.startswith("/auth/")):
            return self._json(404, {"error": "not found"})
        if route == "/settings":
            # public: this is what every viewer's interface is built from
            return self._json(200, {"settings": read_settings()})
        if route == "/auth/me":
            s = self._session()
            if not s:
                return self._json(401, {"error": "not signed in"})
            return self._json(200, {"user": s["user"], "role": s["role"]})
        if route == "/backend":
            if not self._require("admin"):
                return
            cfg = read_backend()
            has_key = bool(cfg.pop("api_key", ""))
            return self._json(200, {"backend": cfg, "has_key": has_key,
                                    "dialects": list(OPENAI_DIALECT),
                                    "max_history": MAX_HISTORY})
        if route == "/app":
            if not self._require("admin"):
                return
            cfg = read_app()
            # What is configured, what is actually bound, and therefore
            # whether a restart is owed. The page should never have to guess.
            pending = sorted(k for k in ("http_port", "https_port", "admin_port")
                             if RUNNING.get(k) is not None and RUNNING[k] != cfg[k])
            if RUNNING.get("session_idle_hours") not in (None, cfg["session_idle_hours"]):
                pending.append("session_idle_hours")
            return self._json(200, {"app": cfg, "running": RUNNING,
                                    "pending": pending,
                                    "limits": {"port_min": PORT_MIN,
                                               "port_max": PORT_MAX}})
        if route == "/users":
            if not self._require("admin"):
                return
            return self._json(200, {"users": [
                {"username": n, "role": u.get("role", "viewer"),
                 "created": u.get("created")}
                for n, u in sorted(read_users().items())]})
        if route == "/tts/voices":
            return self._json(200, {"voices": voice_list(),
                                    "loaded": sorted(_voices.keys())})
        if route == "/stt/status":
            return self._json(200, {
                "model": MODEL_NAME,
                "loaded": sorted(_models.keys()),
                "allowed": list(ALLOWED),
                "error": _model_err,
            })
        if route == "/" and self.admin_port:
            self.path = "/admin.html"        # the admin port opens on admin.html
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
        parsed = urlparse(self.path)

        if parsed.path.startswith("/auth/") \
                or parsed.path in ADMIN_ONLY_ROUTES or parsed.path == "/settings":
            # note: /ask is deliberately absent — the display must reach it
            if not self.admin_port:
                # Nothing privileged is reachable from the display listeners.
                return self._json(404, {"error": "not found"})
            if not self._same_origin():
                return self._json(403, {"error": "cross-origin request refused"})

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

        if parsed.path == "/backend":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            cfg, err = validate_backend(obj, read_backend())
            if err:
                return self._json(400, {"error": err})
            write_backend(cfg)
            print("backend saved by %s: provider=%s model=%s key=%s"
                  % (s["user"], cfg["provider"], cfg["model"] or "-",
                     "set" if cfg["api_key"] else "none"), flush=True)
            out = dict(cfg)
            has_key = bool(out.pop("api_key", ""))
            return self._json(200, {"ok": True, "backend": out,
                                    "has_key": has_key})

        if parsed.path == "/ask":
            # Reachable from the display, which has no sign-in by design.
            if not ask_allowed(self.address_string()):
                return self._json(429, {"error": "too many requests — slow down"})
            obj = self._json_body()
            if obj is None:
                return
            text = str(obj.get("text") or "").strip()[:4000]
            if not text:
                return self._json(400, {"error": "no text"})
            cfg = read_backend()
            if cfg["provider"] == "demo":
                # The display owns the demo replies; say so plainly rather
                # than inventing a second set that drifts from the first.
                return self._json(200, {"reply": "", "demo": True,
                                        "provider": "demo"})
            t0 = time.time()
            try:
                reply = ask_backend(text, obj.get("history") or [], cfg)
            except Exception as exc:                       # noqa: BLE001
                print("ask failed (%s/%s): %s"
                      % (cfg["provider"], cfg["model"], exc), flush=True)
                return self._json(502, {"error": str(exc),
                                        "provider": cfg["provider"]})
            ms = int((time.time() - t0) * 1000)
            if not reply:
                return self._json(502, {"error": "the model returned nothing",
                                        "provider": cfg["provider"], "ms": ms})
            print("ask ok (%s %s) %dms" % (cfg["provider"], cfg["model"], ms),
                  flush=True)
            return self._json(200, {"reply": reply, "provider": cfg["provider"],
                                    "model": cfg["model"], "ms": ms})

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
            print("app settings saved by %s: http=%d https=%d admin=%d session=%dh"
                  % (s["user"], cfg["http_port"], cfg["https_port"],
                     cfg["admin_port"], cfg["session_idle_hours"]), flush=True)
            pending = sorted(k for k in ("http_port", "https_port", "admin_port")
                             if RUNNING.get(k) is not None and RUNNING[k] != cfg[k])
            if RUNNING.get("session_idle_hours") not in (None, cfg["session_idle_hours"]):
                pending.append("session_idle_hours")
            return self._json(200, {"ok": True, "app": cfg, "pending": pending,
                                    "running": RUNNING})

        if parsed.path == "/settings":
            s = self._require("admin")
            if not s:
                return
            obj = self._json_body()
            if obj is None:
                return
            write_settings(obj)
            print("settings saved (%d keys) by %s" % (len(obj), s["user"]), flush=True)
            return self._json(200, {"ok": True, "keys": len(obj)})

        if parsed.path == "/tts":
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


def make_server(port, admin_port=False):
    handler = functools.partial(Handler, directory=ROOT, admin_port=admin_port)
    return ThreadingHTTPServer(("0.0.0.0", port), handler)


def start_tls(port, cert, key, admin_port=False):
    srv = make_server(port, admin_port=admin_port)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    global SESSION_IDLE
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
    SESSION_IDLE = app["session_idle_hours"] * 3600
    RUNNING.update({"http_port": port, "https_port": None, "admin_port": None,
                    "session_idle_hours": app["session_idle_hours"]})

    cert, key = os.path.join(ROOT, "cert.pem"), os.path.join(ROOT, "key.pem")
    have_tls = os.path.exists(cert) and os.path.exists(key)

    # warm the model in the background so the first utterance isn't slow
    for _n in (MODEL_NAME, "base.en"):      # warm both sides of the trade
        threading.Thread(target=get_model, args=(_n,), daemon=True).start()
    if voice_list():
        threading.Thread(target=get_voice, args=(voice_list()[0],), daemon=True).start()

    if have_tls:
        start_tls(tls_port, cert, key)
        RUNNING["https_port"] = tls_port
        print("HTTPS on 0.0.0.0:%d  (mic + local STT work here)" % tls_port, flush=True)
    else:
        print("no cert.pem/key.pem — HTTPS disabled, mic will be blocked", flush=True)

    _b = read_backend()
    print("assistant: %s%s" % (
        _b["provider"],
        "" if _b["provider"] == "demo" else
        " · %s · %s" % (_b["model"] or "(no model)", _b["base_url"])), flush=True)

    print("HTTP  on 0.0.0.0:%d  (no-store)" % port, flush=True)

    # ---- admin listener: HTTPS or nothing ----
    if have_tls:
        first_pw = ensure_first_admin()
        start_tls(adm_port, cert, key, admin_port=True)
        RUNNING["admin_port"] = adm_port
        print("ADMIN on 0.0.0.0:%d  (HTTPS only, sign-in required)" % adm_port,
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
        print("       run ./make-cert.sh <host> and restart.", flush=True)

    make_server(port).serve_forever()


if __name__ == "__main__":
    main()
