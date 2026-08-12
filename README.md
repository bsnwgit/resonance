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

- `http://<host>:9700` — everything except the microphone
- `https://<host>:9701` — full function, including the mic

The certificate is self-signed, so expect one browser warning.

## Settings and the admin model

One settings document on the server defines the interface for **everyone** who
opens the URL. Viewers read it; only a holder of the admin key can write it.

The admin key is printed at startup and stored in `admin.key`; override it with
the `ADMIN_KEY` environment variable.

- Admin: `https://<host>:9701/?admin=<key>`
- Everyone else: `https://<host>:9701/`

Without a valid key the settings panel **is not rendered at all**. The key is
confirmed by the server, so it cannot be bypassed from the browser. Users keep
exactly three controls: microphone, mute, and push-to-talk vs hands-free.

> This shared-secret-in-a-URL scheme is prototype-grade. In a host application
> it should ride that application's existing session and roles.

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

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/stt` | audio in, `{"text": …}` out. `?model=`, `?hint=` |
| `GET` | `/stt/status` | which transcription models are resident |
| `POST` | `/tts` | text in, WAV out. `?voice=`, `?rate=` |
| `GET` | `/tts/voices` | installed neural voices |
| `GET` | `/settings` | the shared interface configuration |
| `POST` | `/settings` | replace it — requires `X-Admin-Key` |
| `GET` | `/settings/whoami` | is this key an admin? |

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

`icon.svg` (64×64) and `lockup.svg` (216×64). The mark reads as the product: a
listening lens above a sheared stack of waveform lines, which is the
visualiser's own STACK geometry seen at a tilt.

> Both marks are **being redrawn**. They currently carry the house style of the
> suite this was extracted from, including the old name in the wordmark, and
> are not the identity this project will ship with.

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
