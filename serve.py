#!/usr/bin/env python3
"""Static server + local speech-to-text for Resonance.

Listeners:
  PORT      (default 9700) plain HTTP — fine for everything except the mic
  PORT + 1  (default 9701) HTTPS      — required for getUserMedia, which the
                                        browser refuses on an insecure origin

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
import functools, hmac, inspect, json, os, secrets, ssl, sys, tempfile, threading, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(ROOT, "settings.json")
KEY_PATH = os.path.join(ROOT, "admin.key")
_settings_lock = threading.Lock()


def admin_key():
    """One shared admin secret. Env wins; otherwise generate and persist so
    it survives restarts. Everyone else gets read-only settings."""
    k = os.environ.get("ADMIN_KEY")
    if k:
        return k
    if os.path.exists(KEY_PATH):
        return open(KEY_PATH).read().strip()
    k = secrets.token_urlsafe(18)
    with open(KEY_PATH, "w") as fh:
        fh.write(k)
    os.chmod(KEY_PATH, 0o600)
    return k


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


class Handler(SimpleHTTPRequestHandler):
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

    # ---------- routes ----------
    def do_GET(self):
        route = self.path.split("?")[0]
        if route == "/settings":
            # public: this is what every viewer's interface is built from
            return self._json(200, {"settings": read_settings()})
        if route == "/settings/whoami":
            return self._json(200, {"admin": self._is_admin()})
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
        return super().do_GET()

    def _is_admin(self):
        supplied = self.headers.get("X-Admin-Key") or ""
        # constant-time compare so the key can't be guessed by timing
        return bool(supplied) and hmac.compare_digest(supplied, admin_key())

    def _body(self, limit=256 * 1024):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > limit:
            return None
        return self.rfile.read(n)

    def do_POST(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)

        if parsed.path == "/settings":
            if not self._is_admin():
                return self._json(403, {"error": "admin key required"})
            raw = self._body()
            if raw is None:
                return self._json(400, {"error": "empty or oversized body"})
            try:
                obj = json.loads(raw)
            except ValueError:
                return self._json(400, {"error": "invalid json"})
            if not isinstance(obj, dict):
                return self._json(400, {"error": "expected an object"})
            write_settings(obj)
            print("settings saved (%d keys)" % len(obj), flush=True)
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


def make_server(port):
    handler = functools.partial(Handler, directory=ROOT)
    return ThreadingHTTPServer(("0.0.0.0", port), handler)


def main():
    port = int(os.environ.get("PORT", "9700"))
    cert, key = os.path.join(ROOT, "cert.pem"), os.path.join(ROOT, "key.pem")

    # warm the model in the background so the first utterance isn't slow
    for _n in (MODEL_NAME, "base.en"):      # warm both sides of the trade
        threading.Thread(target=get_model, args=(_n,), daemon=True).start()
    if voice_list():
        threading.Thread(target=get_voice, args=(voice_list()[0],), daemon=True).start()

    if os.path.exists(cert) and os.path.exists(key):
        tls_port = port + 1
        srv = make_server(tls_port)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print("HTTPS on 0.0.0.0:%d  (mic + local STT work here)" % tls_port, flush=True)
    else:
        print("no cert.pem/key.pem — HTTPS disabled, mic will be blocked", flush=True)

    print("HTTP  on 0.0.0.0:%d  (no-store)" % port, flush=True)
    print("admin key: %s" % admin_key(), flush=True)
    print("           append ?admin=<key> to the URL to unlock settings", flush=True)
    make_server(port).serve_forever()


if __name__ == "__main__":
    main()
