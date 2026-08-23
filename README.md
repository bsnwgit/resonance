<p align="center">
  <img src="lockup.svg" alt="Resonance — voice and visual interface" width="400">
</p>

<p align="center">
  <b>Talk to your AI assistant out loud, from across the room.</b><br>
  <sub>Local speech in, local speech out, and a display you can read at a glance.</sub>
</p>

---

## What this is

Resonance is the **screen and the voice** you put in front of an AI assistant —
not the assistant itself.

You hang a tablet on a wall. It sits there showing a slowly moving line-field.
You say a name; it wakes, listens, and answers aloud, and the figure on screen
moves with the actual audio — your voice going in, its voice coming out. From
across a room you can tell whether it heard you, is thinking, or has started to
answer, without reading a word.

Speech-to-text and text-to-speech both run **on your own machine**. No audio
and no transcript is sent to a third party.

It is deliberately **not a model**. It is the interaction layer, and you point
it at whatever should do the actual answering.

### What that looks like in practice

One display can front **several** assistants at once, each with its own wake
word, voice and destination:

```
"Hey house, kitchen lights on."     → Home Assistant switches the light
                                      → "Turned on the kitchen light."

"Hey Otto, why is the NAS noisy?"   → a model running on your own hardware
                                      → answers aloud, keeps the conversation
                                        open for a follow-up

"Hey Claude, draft that email."     → a hosted API
```

Three names, three destinations, one screen. Every wake word is a field
somebody sets — none of them is baked in.

### Who it is for

Use it if you want an assistant you can talk to **while your hands and eyes are
busy** — in front of a rack, a wall of graphs, a fault in progress, or a
kitchen — and you are not willing to ship room audio to somebody else's
servers. It is built to run on a modest box you own and to drive tablets on a
LAN.

Don't use it if you want a chat window. That already exists and is better at
being one.

## Status

**Working prototype, in active use for evaluation.** Standalone, with no
dependency on any other project.

Settled: the look and interaction model, the local voice pipeline, shared
settings, administration behind local accounts with roles, the backend
adapters, routes, approved displays, the embed API, wall-display and
screensaver modes, and unattended operation — a tablet on a wall is a browser
tab running for a year, so it checks in, says so when it cannot, and reloads
itself when it can again.

Next, in order: **memory**, so a conversation can mean something an hour later;
then packaging as a library other projects can install. See the
[Roadmap](docs/roadmap.md) for the reasoning behind each.

## How it works

```
  microphone ─→ VAD ─→ /stt (faster-whisper) ─→ wake-word gate ─→ /ask + route
                                            (which word → which route)   │
   visualiser ←── Web Audio analyser ←── /tts (Piper) ←── reply ←─────────┘
```

**Speech in.** Microphone through an adaptive voice-activity detector, then
transcription by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) on
the server. Push-to-talk (hold space) or hands-free.

**Speech out.** Neural voices via [Piper](https://github.com/rhasspy/piper),
rendered server-side and played through Web Audio. The browser's own voices
remain as a fallback.

**Wake and sleep words.** Both editable, both with a *learn* mode that records
what the transcriber actually returns for your pronunciation and accepts those
forms thereafter. A conversation stays open for a configurable window; the
sleep word ends it immediately.

**It says why nothing happened.** A line above the input carries what was
heard, how long each stage took, that a recording came back empty, that it is
asleep, or why an endpoint failed. A voice interface that goes quiet is
indistinguishable from a broken one.

<img src="icon.svg" alt="" width="96" align="right">

**The visualiser.** Canvas 2D, no WebGL, **zero runtime dependencies**. It is
a stationary field, not a scrolling chart: standing modes carry the voice,
formant bins place spikes at real spectral positions, and every line has its
own uncorrelated noise floor. Four geometries, five palettes, a turntable
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

<details>
<summary>Which voice and transcription model to start with (measured, six CPU cores, no GPU)</summary>

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

Those two are what a modest box wants. **The panel offers every model
faster-whisper can fetch** — `tiny.en` through `large-v3`, the distilled
variants, and the multilingual models, which are the only way this transcribes
anything other than English. A model that is not already on disk is downloaded
inside the first request that asks for it.

</details>

## Run

### On your own machine

Nothing to generate, no warning, no first-run password to fish out of a log.
Set *reachable at* to **this machine only** in ADMIN and restart:

| listener | purpose |
| --- | --- |
| `http://localhost:9700` | the display in full — the mic works here |
| `http://localhost:9702` | **administration**, behind a sign-in |

Browsers treat `http://localhost` as a secure origin, so the microphone opens
and nothing crosses a network for TLS to protect.

### On a network, driving real displays

The microphone requires a secure origin, so generate a certificate first:

```bash
./make-cert.sh <your-ip-or-hostname>
```

```bash
./serve.sh start
```

| listener | purpose |
| --- | --- |
| `http://<host>:9700` | redirects to 9701 |
| `https://<host>:9701` | the display in full, including the mic |
| `https://<host>:9702` | **administration**, behind a sign-in |

The certificate is self-signed, so expect one browser warning.

**Out of the box the display answers from built-in text** (the `DEMO`
provider), reaching nothing. That is not a placeholder to rush past — it is how
you prove the whole chain works before any model exists, and how you tell later
whether a fault is the front-end or the thing behind it.

To put something real behind it, open ADMIN and set an endpoint's service to
`OPENAI-COMPATIBLE`, `ANTHROPIC` or `HOME ASSISTANT`. See
[Assistants](docs/assistant.md).

## Documentation

**The manual.** These seven are also built into the admin panel — the **?**
beside the SETTINGS title opens them in a modal, and each has a DOWNLOAD PDF
button. Readable by any signed-in account, not just admins.

| | |
| --- | --- |
| **[Using Resonance](docs/using-resonance.md)** | For anyone standing in front of the display. No account, nothing to install — print it and put it next to the screen |
| **[Appearance & geometry](docs/appearance.md)** | The palette, layout and glass, the figure and how it moves |
| **[Speech in & out](docs/speech.md)** | Transcription models, voices, wake and sleep words, and why HTTPS is not optional |
| **[Assistants](docs/assistant.md)** | One display, several assistants: the four providers, routes, and Home Assistant |
| **[Administration](docs/administration.md)** | The panel, the live preview, approving displays, and keeping an untouched screen working |
| **[Admin settings & accounts](docs/app-settings.md)** | Ports, restarts, session lifetime, and the two roles |
| **[Embedding it elsewhere](docs/embedding.md)** | Putting it on somebody else's web page, inline or as a bubble: keys, the code you hand their developer, and what the server needs first |
| **[Integrating it](docs/integrating.md)** | The other side of that one, addressed to the host developer: the exact contract, the timings, what fails and how. Send them this link |

**Project reference.** In the repository, not in the panel.

| | |
| --- | --- |
| **[Architecture](docs/architecture.md)** | How the pieces fit: the settings model, assistant wiring, the embed |
| **[Security model](docs/security-model.md)** | What reaches a browser, what never does, and the limits of both |
| **[HTTP API](docs/http-api.md)** | Every endpoint, and which listener it exists on |
| **[Engineering notes](docs/engineering-notes.md)** | Things that cost real time and are not obvious |
| **[Roadmap](docs/roadmap.md)** | What is planned, and what blocks what |
| **[Progress log](docs/progress-log.md)** | What has been done, and why |

## Driving the visualiser directly

The geometry only ever reads two things, so any source can drive it:

```js
Drive.hit(weight);   // an impulse — a token, a syllable, an event
Drive.level;         // 0..1, current energy
```

Wire an analyser to those and the visualiser follows, whatever is making the
sound. This is the seam that will become the public API when this is packaged.

## Contributing

Branch off `main`, deploy and verify live, then open a PR — see
[CONTRIBUTING.md](CONTRIBUTING.md). PRs are left open for review rather than
self-merged.

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

## Licence

Licensed under the PolyForm Noncommercial License 1.0.0; see
[LICENSE](LICENSE). Security reports go through GitHub's private vulnerability
reporting — see [SECURITY.md](SECURITY.md).
