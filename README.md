<p align="center">
  <img src="lockup.svg" alt="Resonance — voice and visual interface" width="400">
</p>

<p align="center">
  <b>A voice and visual front-end for an AI assistant.</b>
</p>

---

Speak to it, it answers aloud, and a 3D line-field reacts to the real audio —
your voice on the way in, its voice on the way out. Transcription and speech
synthesis both run on your own machine; nothing is sent to a third party.

It is deliberately **not** a model. It is the interaction layer you put in
front of one.

---

## Contents

- [Why this exists](#why-this-exists)
- [Status](#status)
- [How it works](#how-it-works)
- [Install](#install)
- [Run](#run)
- [Settings and the admin model](#settings-and-the-admin-model)
- [Connecting a real assistant](#connecting-a-real-assistant)
- [HTTP API](#http-api)
- [Driving the visualiser directly](#driving-the-visualiser-directly)
- [Engineering notes](#engineering-notes)
- [Contributing](#contributing)
- [Brand](#brand)
- [Roadmap](#roadmap)
- [Progress log](#progress-log)

---

## Why this exists

Most AI interfaces are a text box. That is fine when you are sitting still
with both hands free, and poor when you are looking at something else — a rack,
a screen full of graphs, a fault in progress.

The goal here is an assistant you can *talk to*, that talks back, and that
shows you it is listening without you having to read anything. The visual is
not decoration: amplitude, spectrum and state are all legible at a glance from
across a room.

Two constraints shaped everything:

1. **Local.** Voice interfaces usually ship your audio to somebody else's
   servers. If someone reads a hostname, an address or a credential aloud,
   that is not acceptable. Speech-to-text and text-to-speech both run locally.
2. **Embeddable.** It should be able to sit in front of *someone else's*
   assistant rather than own the model itself.

## Status

Working prototype, in active use for evaluation.

**Standalone.** This began as the AI front-end for one particular suite of
applications and has outgrown that brief, so it is now its own project with no
dependency on any of them. It will be adopted back into those applications once
it is ready to be — as a consumer of this project, not as a part of it.

**Settled:** the look, the interaction model, the local voice pipeline, the
shared-settings and admin model.

**Not done:** packaging it as a library other projects can install, and the
adapter for a real assistant backend. Today it answers from built-in text.

## How it works

```
  microphone ─→ VAD ─→ /stt (faster-whisper) ─→ wake-word gate ─→ askBackend()
                                                                      │
   visualiser ←── Web Audio analyser ←── /tts (Piper) ←── reply ←──────┘
```

**Speech in.** Microphone through an adaptive voice-activity detector, then
transcription by [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
on the server. Push-to-talk (hold space) or hands-free.

**Speech out.** Neural voices via [Piper](https://github.com/rhasspy/piper),
rendered server-side and played through Web Audio. The browser's own voices
remain available as a fallback.

**Wake and sleep words.** Both editable, both with a *learn* mode that records
what the transcriber actually returns for your pronunciation and accepts those
forms thereafter. A conversation stays open for a configurable window,
refreshed by each exchange; the sleep word ends it immediately.

<img src="icon.svg" alt="" width="96" align="right">

**The visualiser.** Canvas 2D, no WebGL, **zero runtime dependencies**. It is
a stationary field, not a scrolling chart: standing modes carry the voice,
formant bins place spikes at real spectral positions, and every line has its
own uncorrelated noise floor. Four geometries, four palettes, a turntable
rotation, and a full glass treatment — all admin-configurable.

## Install

Requires Python 3.10+ and a couple of spare CPU cores. No GPU.

```bash
python3 -m venv stt-venv
./stt-venv/bin/pip install faster-whisper piper-tts
```

Fetch at least one Piper voice into `voices/`:

```bash
mkdir -p voices && cd voices
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main/en
curl -LO $BASE/en_US/amy/medium/en_US-amy-medium.onnx
curl -LO $BASE/en_US/amy/medium/en_US-amy-medium.onnx.json
```

Measured on six CPU cores, no GPU:

| voice | synthesis time per sentence |
| --- | --- |
| `en_GB-alba-medium` | ~170 ms |
| `en_US-amy-medium` | ~330 ms |
| `en_US-ryan-high` | ~1.7 s |
| `en_US-lessac-high` | ~1.8 s |

| transcription model | decode time |
| --- | --- |
| `base.en` | ~450 ms, sloppier on technical vocabulary |
| `small.en` | ~1.4 s, accurate |

## Run

The microphone requires a secure origin, so generate a certificate first:

```bash
./make-cert.sh <your-ip-or-hostname>
```

```bash
./serve.sh start
```

| listener | purpose |
| --- | --- |
| `http://<host>:9700` | the display, everything except the microphone |
| `https://<host>:9701` | the display in full, including the mic |
| `https://<host>:9702` | **administration**, behind a sign-in |

The certificate is self-signed, so expect one browser warning.

## Settings and the admin model

One settings document on the server defines the interface for **everyone** who
opens the display. The display only ever *reads* it. Writing happens on a
separate listener, on a separate port, behind a username and password.

**The public listeners have no route that accepts a write.** Not a guarded
route — no route. `admin.html` is not served on them either, and returns 404.
Users keep exactly three controls: microphone, mute, and push-to-talk vs
hands-free.

### The admin interface

`https://<host>:9702` — sign in, and you get the full control panel with a
**live preview** beside it. The preview is the display page itself in an
iframe, driven over `postMessage`, so you are tuning the real renderer rather
than a mock-up of it. Changes show immediately in the preview and reach
everyone else only when you press SAVE.

On first run an `admin` account is created and its password printed **once**
in the startup output. Change it after signing in.

Two roles:

| role | can |
| --- | --- |
| `admin` | change every setting, manage accounts |
| `viewer` | read the configuration, change nothing |

### App settings

**APP SETTINGS**, at the foot of the panel, covers how the server is wired
rather than how the interface looks: the port each of the three listeners
answers on, and how long an idle sign-in survives. It is stored in `app.json`.

Nothing here takes effect until the process restarts — you cannot move the
floor you are standing on. The panel shows what is configured against what is
actually bound, and says plainly when a restart is owed:

```bash
./serve.sh stop
./serve.sh start
```

Ports are checked before they are accepted: 1024–65535, all three different,
and **not already in use by something else on the machine**. A port that fails
to bind would otherwise only reveal itself at the next restart, with the admin
interface gone and the fix being to edit JSON on the box by hand.

`serve.sh` reads `app.json` too, and records the pid it started. Without that
pid, changing the display port would leave `stop` looking at the new port while
the old process was still running on the old one.

The `PORT` environment variable still overrides everything and still shifts all
three listeners together, so a second instance can be run without touching the
stored configuration.

Accounts live in `users.json` next to the server, mode `600`, passwords stored
as PBKDF2-SHA256 with 600,000 rounds and a per-account salt. Sessions are
in-memory, cookie-based, `HttpOnly` + `Secure` + `SameSite=Strict`, and expire
after 8 hours of inactivity. Failed sign-ins back off geometrically per client
address. Changing a password or a role drops that account's live sessions.

**HTTPS only, by design.** The admin listener does not start without a
certificate, because it accepts a password and a password over plain HTTP
crosses the network in the clear. If it is missing from the startup banner,
run `make-cert.sh` and restart.

> This is local-account authentication, deliberately: no directory, no third
> party, nothing leaves the machine to log in — the same principle as the
> speech pipeline. Inside a host application it should ride that
> application's existing session and roles instead.

## Connecting a real assistant

Out of the box it answers from built-in text, so the whole chain can be
commissioned before any backend exists. **RUN SELF-TEST** in the settings panel
walks each link — secure origin, settings store, transcription service, voices,
microphone, recorder, backend, render-and-speak — and names whichever one is
broken.

There is a single seam to replace:

```js
async function askBackend(text) { /* index.html */ }
```

Everything else is already backend-agnostic. Keep the demo mode permanently: it
is how you tell whether a fault is the front-end or the model behind it.

## HTTP API

On every listener:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/stt` | audio in, `{"text": …}` out. `?model=`, `?hint=` |
| `GET` | `/stt/status` | which transcription models are resident |
| `POST` | `/tts` | text in, WAV out. `?voice=`, `?rate=` |
| `GET` | `/tts/voices` | installed neural voices |
| `GET` | `/settings` | the shared interface configuration |

Admin listener only — everything below returns 404 on the public ports:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/auth/login` | username and password in, session cookie out |
| `POST` | `/auth/logout` | end the session |
| `GET` | `/auth/me` | who am I, and with what role |
| `POST` | `/auth/password` | change a password; your own needs the current one |
| `POST` | `/settings` | replace the configuration — `admin` role |
| `GET` | `/app` | ports and session length, plus what is actually running |
| `POST` | `/app` | change them — `admin` role, restart to apply |
| `GET` | `/users` | list accounts — `admin` role |
| `POST` | `/users` | create an account — `admin` role |
| `POST` | `/users/role` | change a role — `admin` role |
| `POST` | `/users/delete` | remove an account — `admin` role |

The last admin account cannot be deleted or demoted; an interface nobody can
administer is a brick.

## Driving the visualiser directly

The geometry only ever reads two things, so any source can drive it:

```js
Drive.hit(weight);   // an impulse — a token, a syllable, an event
Drive.level;         // 0..1, current energy
```

Wire an analyser to those and the visualiser follows, whatever is making the
sound. This is the seam that will become the public API when this is packaged.

## Engineering notes

Things that cost real time and are not obvious. Recorded so they are not
rediscovered.

**A certificate valid for more than 398 days fails in Chrome**, and often as a
*blank page* rather than the usual click-through warning. `make-cert.sh` uses
365 days.

**Do not bias the decoder toward your wake word.** Both `initial_prompt` and
`hotwords` cause faster-whisper to treat the hinted word as context already
supplied and **omit it from the transcript** — silently breaking the matching
the hint was meant to help. Measured both ways. `?hint=` remains useful for
domain vocabulary you only need spelled correctly when it does appear.

**A general speech model will not reliably spell one short word the way a given
person says it.** A one-syllable wake word comes back with the wrong vowel,
a stray plural, or a trailing full stop. Tuning
the model, the beam size and the thresholds all helped a little and none of it
was enough. The fix was to stop fighting the speller: capture what the
transcriber actually produces for that speaker and accept those forms.

**Silence-only voice detection is a trap.** If the room's noise floor sits above
the gate, the level never returns to zero, the utterance never "ends", and
nothing is ever transcribed — while the visualiser keeps reacting happily. There
is now a maximum-utterance cut, a live level meter, and a calibrate button.

**Never let one threshold serve both the visuals and the speech detector.**
Sharing it means raising the gate so utterances end also forces the user to
shout to be heard. They are separate now: the geometry keeps the configured
gate, detection uses an adaptive threshold that floats above the measured room
floor.

**Browser speech synthesis cannot be tapped by an analyser**, so a browser-voice
envelope has to be estimated from word-boundary events. Rendering the voice
server-side and playing it through Web Audio removes the guesswork entirely —
the geometry follows the actual waveform.

**Turn the browser's audio processing back on when a human is being
transcribed.** Auto-gain and noise suppression were disabled to preserve the
dynamics the visualiser feeds on; the result was quiet audio and constant
mishearing. There is now a toggle, defaulting to clean.

**A control panel hidden by CSS is still shipped.** The settings panel used to
live in the display page and be revealed once an admin key checked out. Every
viewer was still sent the whole thing — 105 elements of it — and the gate was
one bug away from being the only thing standing between them and it. It is a
separate page on a separate port now, and the public listeners do not serve it
at all.

**A top-level `const` is not a property of `window`.** The admin page tried to
read the display's settings out of the iframe with `frame.contentWindow.S` and
got `undefined`, so every slider silently fell back to the browser's default
midpoint — a page full of plausible wrong numbers, with nothing logged. The
display now sends its settings in the message that announces it is ready.

**A visibility gate must be confirmed by the server.** An early version checked
only that an admin key was *present*, not that it was *correct* — so
`?admin=anything` opened the settings panel. Writes still failed, but the
interface users are not supposed to have was one guessed parameter away.

**A deliberately inert feature must say it is inert.** The wake word applied
only to hands-free mode and did nothing in push-to-talk, with no indication —
it read as simply broken. Live status text now states whether each gate is in
effect and why.

## Contributing

Branch off `main`, deploy and verify live, then open a PR — see
[CONTRIBUTING.md](CONTRIBUTING.md). PRs are left open for review rather than
self-merged.

Licensed under the PolyForm Noncommercial License 1.0.0; see
[LICENSE](LICENSE). Security reports go through GitHub's private vulnerability
reporting — see [SECURITY.md](SECURITY.md).

## Brand

`icon.svg` (64×64) and `lockup.svg` (216×64).

The mark is a **standing wave**: two fixed ends, a node at the centre, and the
envelope swelling between them. That is not a metaphor — it is what the
visualiser actually does. It is a stationary field rather than a scrolling
chart, standing modes carry the voice, and the nodes stay put while everything
between them moves. The mark states the mechanism instead of decorating it.

Near-black field, the interface's own pale ink for the live envelope and a
dimmer one for its mirror, and a single blue reserved for the nodes — the
brightest of them at the centre, where the signal is. It reduces to the
twin-lobe silhouette at favicon size and stays legible to 16px.

## Roadmap

Roughly in order of value:

- **Backend adapter.** Replace `askBackend()` with a real assistant, keeping
  demo mode as the fallback.
- **Package for reuse.** Separate the visualiser core from the demo chat shell,
  give it an instance API, ship ESM + UMD. Still zero dependencies.
- **Barge-in.** Detect speech during playback and duck immediately. Nobody
  tolerates waiting out a wrong answer.
- **State in the geometry.** Distinct colour and motion for thinking, speaking
  and *failing*, so a fault is visible without reading anything.
- **Domain vocabulary hints.** `?hint=` already exists and is unused; a host
  application knows its own hostnames and interfaces.
- **Persistent transcripts.** Timestamped and retrievable, for an audit trail.
- **Unprompted speech.** Let a host application make it speak — an alert
  arrives, the geometry wakes, it tells you. That is a different product from
  a chat box.

## Progress log

Newest first.

### 2026-08-12 — administration moved to its own port

The configuration panel left the display page. It is now `admin.html` on a
separate HTTPS listener (9702) behind local accounts with roles, and the panel
carries a live preview of the real display rather than a copy of it.

- **Local accounts**, PBKDF2-SHA256, admin and viewer roles, first-run password
  printed once at startup.
- **Sessions**, HttpOnly + Secure + SameSite cookies, sliding 8-hour expiry,
  geometric back-off on failed sign-ins.
- **The shared key is gone.** `?admin=` means nothing, `X-Admin-Key` no longer
  exists, and the public listeners have no write route at all.
- **`serve.sh` and `make-cert.sh` are executable in git** — they were mode 644,
  so `rsync -a` stripped the bit the server had been given by hand and the
  service would not start after a deploy.

### 2026-08-12 — established as Resonance

Separated from the application suite this was extracted from and established as
its own project. The repository, the working tree and the deployment all moved
out of that suite's namespace, and the licence notice no longer points at it.
The visual identity is still to be redrawn. Nothing about how the thing works
changed.

### 2026-08-11 — repository created

Extracted from a prototype into its own repo with no shared history.

- **Local neural voice.** Replaced browser speech synthesis, which sounded
  synthetic because operating systems mostly ship older concatenative engines.
  Piper renders on the server; the browser engine stays as a fallback. Side
  benefit: playback through Web Audio gives the visualiser a real analyser on
  the assistant's own speech.
- **Shared admin settings.** `GET /settings` public, `POST /settings` behind a
  server-confirmed admin key, written atomically. The panel does not render for
  ordinary viewers.
- **Demo backend and self-test**, so the chain can be commissioned before any
  assistant exists.
- **Sleep word** alongside the wake word — ends a conversation deliberately
  rather than waiting out a timer, so you can talk to someone else without the
  assistant answering.
- **Wake/sleep word learning**, capturing the speaker's actual pronunciation.
- **Settings panel reorganised** into tabs with collapsible topics and a filter
  that searches across all of them.
- **Local speech-to-text**, replacing the browser's cloud recogniser.
- **Push-to-talk**, hands-free mode, and adaptive voice detection.
- **The visualiser** reached its settled form: stationary field, spectral
  spikes, turntable rotation, amplitude-driven colour ramp, blue-glow palette.
