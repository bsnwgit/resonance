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
- [Embedding it in another application](#embedding-it-in-another-application)
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
shared-settings model, administration — its own HTTPS listener behind local
accounts with roles, with a live preview of the real display — the backend
adapter that puts a real assistant behind it, and the embed API that lets
another application put this interface inside its own page.

**Not done, in the order it matters:** the deployment shapes, because a single
person running this on their own laptop should not have to configure accounts
to talk to it. Then identity and memory, so a conversation can mean something
an hour later — the embed is deliberately memoryless until that lands. Then
packaging it as a library other projects can install.

The [Roadmap](#roadmap) carries the reasoning for each, including the
decisions already taken about how identity and memory should work.

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
Users keep exactly four controls: microphone, mute, push-to-talk versus
hands-free, and whether the transcript is shown.

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

### The built-in manual

**DOCUMENTATION** at the foot of the panel opens six documents covering the
display and every tab of the admin interface. They live as markdown in
`docs/`, are read in a modal over the whole window rather than in the 425px
column, and each has a **DOWNLOAD PDF** button.

Available to any signed-in account, not just admins: a viewer can read the
configuration, so a viewer should be able to read what it means. *Using
Resonance* is written for people with no account at all — print it and put it
next to the screen.

The PDF is generated on the server with no dependency of any kind. It is set
in Courier throughout, which is a decision rather than an aesthetic accident:
the base-14 fonts need no embedding, and a monospaced face makes string width
exactly `len(s) × 0.6 × size`, so line wrapping is correct by construction
instead of needing font-metric tables. See `manual.py`.

### What a viewer keeps

The controls a viewer has — mute, push-to-talk versus hands-free, and
whether the transcript is shown — are remembered in their own browser and
survive a reload, so a display stays how they left it. They are stored under
one `localStorage` key and last until that browser's data is cleared.

A stored choice outranks the shared setting, and keeps outranking it after an
admin changes theirs: once someone has muted a display it stays muted for
them. A browser that has never touched a control follows the admin's document
exactly.

Nothing else is kept per viewer. Look, geometry, palette, voice and wake word
remain wholly admin-controlled, because the point of the shared document is
that one person decides what everyone sees.

The microphone is deliberately not remembered — re-opening it on load would
raise a permission prompt nobody asked for.

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
broken. Keep demo mode permanently: it is how you tell whether a fault is the
front-end or the model behind it.

Configure the rest in the admin page under **AI → Assistant**. The panel is
deliberately terse; the reasoning behind each field is here.

### The three providers

**DEMO** answers from the display's own built-in text. Nothing is sent
anywhere, no key is needed, and the system prompt is ignored.

**OPENAI-COMPATIBLE** is a *dialect, not a vendor*. Ollama, OpenClaw, LM Studio
and vLLM all speak it, so one adapter reaches all of them and the only
difference between them is the base URL — which is what the preset buttons
fill in. Pick a preset, set the model, save.

| Preset | Base URL | Model field |
|---|---|---|
| Ollama | `http://127.0.0.1:11434/v1` | the tag, e.g. `qwen2.5:3b` |
| OpenClaw | `http://127.0.0.1:18789/v1` | an agent id, e.g. `openclaw:main` |
| LM Studio | `http://127.0.0.1:1234/v1` | whatever is loaded |
| OpenAI | `https://api.openai.com/v1` | e.g. `gpt-4o-mini` |

**ANTHROPIC** is a shape of its own rather than another preset, because the
wire format genuinely differs: the key rides an `x-api-key` header instead of
`Authorization: Bearer`, an `anthropic-version` header is required, the system
prompt is a top-level field rather than a message in the list, `max_tokens` is
mandatory, and the reply arrives as a list of content blocks rather than a
single string. Base URL is `https://api.anthropic.com` and there is only one,
so it has no preset — the provider button fills it. A key is required, and
saving without one is refused rather than discovered later by whoever is
standing in front of the screen.

### Fields that do not apply everywhere

**temperature** is not sent to Anthropic at all. The current Claude models
reject the sampling parameters outright with a 400, and the older ones stop at
1.0 where this panel's slider goes to 1.5 — a control that quietly breaks half
the models is worse than no control. Steer those with the system prompt
instead. The slider hides itself when Anthropic is selected.

**keep model loaded** (`keep_alive`) is an Ollama extension accepted on its
OpenAI-compatible path. Without it the model unloads after a few minutes idle
and the next question waits for it to load again — measured at 28s for a 7b on
the reference hardware. It means nothing to a hosted provider, and is never
sent to Anthropic.

**installed there:** under the model field is an Ollama trick — it asks
`/api/tags` on the same host and lists what is actually there, so a model name
is chosen rather than typed from memory. Nothing else answers that path, so
the line stays empty for everyone else.

### What the model knows

The server appends the current date and time to the system prompt on every
request, because a model's sense of "now" is frozen at its training cutoff and
it will otherwise answer that question confidently and wrongly. The time is
the **display's** local time: the browser reports its IANA zone with each
question and the server formats accordingly, so a box running on UTC does not
tell somebody in New York at 8pm that it is already tomorrow.

The zone name is validated against the tz database and then discarded — what
reaches the prompt is formatted server-side, never a string the client sent.
An unrecognised zone falls back to the server clock.

Recency is a different matter and is not fixable this way: the model has no
internet, so the prompt asks it to say it does not know rather than guess.
Live information would need a search or tool integration, which does not
exist yet.

### The system prompt

What the assistant is told before every question. This one matters more here
than in a chat box: the reply is **read aloud**, and markdown, bullets, code
fences and emoji are all noise when spoken. The shipped prompt asks for one or
two sentences of plain prose, and **RESET** returns to it. That single
instruction is the largest difference between a voice interface and a text
one.

### Where the key lives

Never in `settings.json`. That document is world-readable by design — every
viewer's interface is built from it — so a credential there would be handed to
anyone who opened the page. The assistant configuration lives in its own
`backend.json` at mode 600, admin-only, and the key is never returned to a
browser: the field shows whether one is stored, not what it is. **FORGET KEY**
clears it.

Measured round-trips on the reference box, cold then warm:
`qwen2.5:1.5b` 1.4s / 1.6s, `qwen2.5:3b` 10.1s / 3.6s, `qwen2.5:7b` 28.2s /
11.1s. Choose accordingly — for a voice front-end the wait is the product.

## Embedding it in another application

An admin creates an **embed key** on the EMBEDS tab. The host application's
*server* exchanges it for a short-lived session; the host's page frames the
result. Server to server, so the layout it asked for and its right to ask are
settled in one call, before a browser is involved.

`docs/embedding.md` — also in the panel, and downloadable as a PDF — is the
integration guide. What is worth having here is the reasoning.

**Parts, not combinations.** Seven components — `visual`, `transcript`,
`input`, `mode` (SPACE/AUTO), `talk`, `audio`, `text` — make 128
arrangements, so a key carries a list of parts rather than the name of a
layout, and never needs extending when somebody wants the 129th. Presets
(`full`, `console`, `voice`, `chat`, `kiosk`, `signage`) are first-class names
over the common ones, and a starting point rather than a separate kind of key.

**Capability and chrome are separate axes, and conflating them is a security
bug.** Hiding the TALK button is not the same as denying the microphone: hide
it while the capability stands and a host page can open a microphone with no
control on screen and no way for the person in front of it to know. The proof
that one field could not serve is `kiosk` and `signage` — identical chrome,
the figure alone, and opposite permissions.

**Both are fixed when the key is created.** One key is one surface: a lobby
kiosk and a support widget are two keys, separately revocable and separately
rate-limited, and the admin list says exactly what each one draws. Fixing the
chrome also means it is signed into the key rather than riding in query
parameters — plain parameters mean any user appends `&talk=1` and grants
themselves a microphone the host never authorised.

**Two admins, and grants only ever travel one way.** This admin sets the
ceiling. The host's own admin may narrow what their users get, on either axis,
over `postMessage` — and can never widen it. The refusal lives in the embed
rather than in an agreement: the host page is untrusted by definition, so
"cannot add" has to be code that ships from here.

**Incoherent arrangements are refused at creation**, in the admin page, naming
the orphaned part — a human sees the mistake immediately rather than a host
developer reading it out of a 400 three weeks later.

**Responsiveness belongs to the embed, not the API.** Desktop console and
phone voice-only is a breakpoint problem, and the narrow-viewport rules key
off the *frame's* width rather than the device's. Solving it by issuing a
different key after sniffing a user agent would be the wrong layer.

**The embed is memoryless**, and that is the sequencing rather than an
omission — see the roadmap.

**The gotcha that catches everybody:** a microphone inside an iframe needs
`allow="microphone"` from the host, the host page itself on HTTPS, and
permissions-policy delegated down. Miss any one and the embed looks broken in
a way that has nothing to do with this server. The admin preview has no
microphone for precisely this reason.

## HTTP API

On every listener:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/stt` | audio in, `{"text": …}` out. `?model=`, `?hint=` |
| `GET` | `/stt/status` | which transcription models are resident |
| `POST` | `/tts` | text in, WAV out. `?voice=`, `?rate=` |
| `GET` | `/tts/voices` | installed neural voices |
| `GET` | `/settings` | the shared interface configuration |
| `POST` | `/ask` | a question to the connected assistant |

Display listeners only — the embed does not exist on the admin port:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/embed/session` | an embed key in, a short-lived session token out |
| `GET` | `/embed?t=` | the display, framed, drawing only what the key grants |
| `GET` | `/embed/session` | what this session was granted — bearer token |

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
| `GET` | `/embeds` | list embed keys — `admin` role |
| `POST` | `/embeds` | create one; the key is returned once — `admin` role |
| `POST` | `/embeds/enable` | enable or disable one — `admin` role |
| `POST` | `/embeds/delete` | revoke one — `admin` role |

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

**Setting `scrollbar-width` makes Chrome ignore `::-webkit-scrollbar`.** The
standard property and the pseudo-elements are not additive: specify the
standard one and the browser drops the webkit rules and falls back to the
operating system's overlay bar, which on macOS is invisible until you scroll.
Measured — the scroller reserved 0px of layout instead of 9. Safari ignores
the standard properties entirely, so neither alone covers both. The
pseudo-elements are unconditional and the standard properties sit behind
`@supports not selector(::-webkit-scrollbar)`.

**A `stop` that returns before the process exits will take the service down.**
`stop && start` raced: the old process still held the listening sockets, the
new one died on `Address already in use`, and the result was nothing running
at all rather than an obvious failure. Stopping now waits for the pid to
actually go, with a ceiling after which it reports failure instead of claiming
success, and starting waits for the bind rather than assuming a second is
enough.

**Two code paths that render the same thing will not stay in step.** The
transcript was revealed by three different routes — token stream, browser
voice, neural voice — and only two of them scrolled. The neural path is the
default engine, so the visible symptom was that a long spoken reply ran off
the bottom and only appeared once something else forced a scroll. Everything
that reveals text goes through one helper now.

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
- **Two separate settings: what it binds to, and what it takes to get in.**
  Everything else here assumes a server several people can reach. One person
  running this on their own machine is a different product, and making them
  fish a generated password out of a log to configure their own laptop is
  absurd.

  These are deliberately not one "mode". Binding and authentication are
  independent, and collapsing them into a single label produces a label that
  lies the moment someone changes the binding. The interface should report the
  actual pair — what it is reachable at, and what it takes to get in — rather
  than a name.

  | bound to | to get in | fits |
  | --- | --- | --- |
  | loopback | nothing | your own machine; nothing else can reach it |
  | one address | nothing | your own home network, your call, stated plainly |
  | one address | a single PIN, no accounts | a home network you would rather not leave open |
  | everything | accounts and roles | anywhere other people are |

  At **loopback with no authentication** the network is already the boundary,
  so accounts add nothing. This install also needs no certificate at all:
  browsers treat `http://localhost` as a secure context, so the microphone
  works unprompted. Start it, open localhost, talk to it — none of the setup
  ceremony below applies. Memory simply works, because one machine is one
  identity and there is nothing to scope it against or authenticate.

  **Beyond loopback with no authentication** is a genuine choice somebody may
  want on their own network, and it is not dressed up as anything else: the
  structural argument for skipping accounts is gone, and what is left is the
  owner accepting a risk on a network they control. It warns loudly at startup
  and banners in the interface. Not refused — but a laptop configured this way
  that later joins an office network must not be quiet about it.

  **A single PIN with no accounts** is the middle rung and costs nothing new —
  the PIN machinery below, applied to the whole display rather than to a named
  identity. No account management, no admin sign-in, just a number at the
  door. For a home server it is probably the right answer: it keeps a guest's
  phone or a smart television out without turning a house into an enterprise.

  **Accounts and roles** stay the default, because the safe default is the one
  that assumes it can be reached.

  Two things worth stating even where none of this applies: binding to one
  specific address rather than every interface is worth doing regardless, so a
  laptop that later joins another network does not follow you onto it — and a
  firewall rule, which is outside this application entirely, does more than
  anything inside it.

- **HTTPS only.** Retire the plain listener. The microphone already refuses to
  work on it, so today it mostly generates confusion about why half the
  interface is dead. Make it a permanent redirect to the HTTPS port rather
  than deleting it, or every bookmark and kiosk startup URL dies silently on
  the day it changes. Lets cookies carry `Secure` unconditionally.
- **Identity, in three strengths.** How a device or person identifies itself
  decides what may be kept, because the strength of the claim and the
  durability of the memory should move together.

  | identity | what proves it | memory |
  | --- | --- | --- |
  | named, no PIN | nothing, it is a place | none |
  | token | possession of the browser | device memory, lost when browser data is cleared |
  | named + PIN | a credential | server memory, longer retention, follows the person |

  A **token** is issued by the server on first visit: random, unguessable, in
  an `HttpOnly` cookie so page script cannot read it and it rides along with
  every request. Not encrypted in the browser — if the browser holds the key
  that is obfuscation, and the secrecy belongs in the server-side mapping. A
  token is a device, a device has an owner, and what is kept on it is the
  owner's to be responsible for.

  A **declared name** — `?display=workshop` — takes precedence over a token
  and rebinds that device to its record, because a name survives a browser
  wipe and a token does not. On its own it is a bearer identifier with no
  secret: names are guessable, so a name alone can never unlock memory.

  A **PIN** turns a name into a portable identity, and is the difference
  between a place and a person. Hashed server-side with the same PBKDF2 as the
  admin passwords, never compared in the browser. Rate limiting and lockout
  are what make a short PIN viable, reusing the geometric back-off already
  built for admin sign-in, and the obvious sequences are refused. An admin
  resets a forgotten PIN from the device list: with no email here that is the
  only recovery path, and it has to exist in the first version.

  **An admin sets the required length**, so a sensitive area can demand more
  digits than the default. Raising it is not advisory — every existing PIN
  shorter than the new minimum is marked, and the next time that identity
  unlocks it must set a conforming one before it can go any further. Warning
  and letting them past would mean the setting only ever protected accounts
  created after it changed, which is the failure that looks like success.

  The old PIN still authenticates that change: unlock with it, then set the
  new one. Anything else means an admin resetting every identity by hand the
  day the policy tightens. An identity that never comes back stays locked
  until it does, which is the correct outcome, and the admin list shows who is
  still outstanding so the rollout is visible rather than assumed. Lowering
  the requirement invalidates nothing.

  Unlocking grants a session — persistent on a personal device, and on
  anything shared it must end at the conversation boundary, or the next person
  inherits the identity along with the screen.

  **A PIN session is measured in hours, and it is admin-configurable in its
  own right rather than sharing the admin session's setting.** The two are
  different jobs and the numbers should not be able to drift into each other:
  an admin holds the configuration everyone else is looking at the results of
  and is measured in minutes, while somebody who has unlocked a display is
  standing in front of a screen doing their work, and being asked to key a PIN
  in again every half hour would end with the PIN switched off entirely. It is
  the same reasoning that put binding and authentication on separate settings
  above — one label covering two independent things is a label that lies as
  soon as somebody changes one of them.

  Recorded plainly: a PIN is not a password, and this is a lightweight account
  system rather than a small feature. Six digits is a low bar that rate
  limiting carries. It suits an internal tool and a number keyed into a
  screen, and it should not be the only thing standing in front of anything
  genuinely sensitive. It depends on HTTPS only — a PIN must never be
  enterable on the plain listener.

  Devices and identities are listed in the admin page with when they were last
  seen, and deletable there.

- **Memory.** Give conversations meaning across sessions — derived, not
  verbatim. A rolling summary or a small set of retained facts, not a
  transcript: it survives context limits, and it is a far smaller thing to
  hold than everything anybody ever said.

  Whether anything is kept is one property, defaulting from the identity above
  and overridable by an admin in either direction. A named place defaults to
  nothing and can be switched on — naming is really a durability mechanism, so
  the person who names a device is often exactly the person who wants memory
  to outlast a browser wipe. A named device with memory on should be
  conspicuous in the list, since the default is off for a reason. A token
  defaults to remembering, with revocation rather than enrolment as the
  control, so a machine that turns out to be shared can be corrected without
  gating every ordinary one.

  One property, two effects: anything not remembering also drops what it is
  holding at the conversation boundary — the wake word opens one, the sleep
  word and the awake timeout close one. One is about what survives the
  session, the other about what survives the person standing there, and tying
  both to the same setting stops them contradicting.

  Bounded on purpose — a rolling summary and a capped set of facts, oldest
  ageing out — with the retention window admin-configurable, because "longer"
  means one thing in a workshop and another in a room where customers can be
  overheard.

  Visible and deletable in the admin page, and visible and deletable **by the
  person it is about** once there is an identity to attach it to. Memory you
  cannot inspect is memory you cannot correct or trust.

  What changes at the authenticated tier is attribution. Device memory is
  something a browser said; server memory under a named identity is what a
  particular person has been discussing, on a server somebody administers.
  Nothing stops an admin reading it and pretending otherwise would be theatre,
  which is precisely why it is derived rather than verbatim and why whatever
  writes it is told not to retain credentials or addresses. The protection is
  what goes in.

  Deliberately sequenced after the adapter has seen real use. Whether the
  useful unit is a summary per session, extracted facts, or something narrower
  is an empirical question, and guessing means building the wrong shape.

- **Diagnostics.** Technical events keyed to a device: the microphone would not
  open, transcription took four seconds, the voice service returned an error,
  this browser has no recorder. No conversation content. A health view per
  device in the admin page, so a failing screen can be found without anyone
  standing in front of it.
- **The embed, once there is an identity to attach to it.** The memoryless
  embed shipped first, deliberately: it is exactly the `named, no PIN → no
  memory` row above, so it needs no notion of a person at all. What remains
  arrives for free when identity lands — **an embed carries two identities at
  once** and they compose rather than compete: the application is
  authenticated by its key, and the person in front of it still has one of
  the three strengths above. Settings hang off the application, memory off
  the person. That is also the answer to whether three host applications must
  share one look — they do not. What to avoid is the middle: an embed with
  its own private idea of who the user is.

  Also deferred, and reversibly so: **per-request layout**. Chrome is fixed
  when the key is created, which can be relaxed later without breaking an
  integrator and could not be withdrawn once they depended on it. The two
  real arguments for it — progressive disclosure and per-user variation —
  are already covered by the host's ability to narrow at runtime.
- **Package for reuse.** Separate the visualiser core from the demo chat shell,
  give it an instance API, ship ESM + UMD. Still zero dependencies.
- **Separable speech service.** Run faster-whisper and Piper as their own
  process, so the models can sit on different hardware from the interface,
  stay warm when the interface restarts, and be shared by more than one
  consumer. The seam is already HTTP — `/stt` and `/tts` — so this is a
  question of where those routes point rather than a restructuring. Keep
  `serve.py` proxying them so the browser still sees one origin, and neither
  CORS nor a second certificate enters the picture. Worth doing at the point
  there is a second consumer, not before.
- **Voice library.** Add and remove Piper voices from the admin page rather
  than by hand with `curl`, hold several, and choose which are offered.
  Today the library is whatever happens to be sitting in `voices/`, which
  means adding a voice needs shell access to the machine. Transcription
  models are deliberately out of scope: faster-whisper fetches those itself
  on first use, and the panel already picks between them.
- **Barge-in.** Detect speech during playback and duck immediately. Nobody
  tolerates waiting out a wrong answer.
- **State in the geometry.** Distinct colour and motion for thinking, speaking
  and *failing*, so a fault is visible without reading anything.
- **Domain vocabulary hints.** `?hint=` already exists and is unused; a host
  application knows its own hostnames and interfaces.
- **Unprompted speech.** Let a host application make it speak — an alert
  arrives, the geometry wakes, it tells you. That is a different product from
  a chat box. The `signage` embed preset is already the shape that wants it:
  the figure alone, no microphone, speaking only what the host pushes — and
  until this lands there is nothing for the host to push with.

## Progress log

Newest first.

### 2026-08-13 — another application can put this in its own page

- **Embed keys.** An admin creates one on the new EMBEDS tab; a host
  application's server exchanges it for a short-lived session and frames the
  result. The key never reaches a browser, is stored hashed, and is shown
  once.
- **Capability and chrome are separate axes**, fixed at creation and never
  widenable. Hiding a control is not withdrawing a permission, and the panel
  is laid out to teach that rather than blur it.
- **Incoherent arrangements are refused where they are made**, naming the
  orphaned part — the same six rules on the server and in the panel, in the
  same words.
- **The host can narrow at runtime** over `postMessage`, on either axis, and
  cannot widen: anything asked for beyond the key is dropped by the embed
  itself rather than refused by agreement.
- **Bearer token, not a cookie.** A cookie set by an iframe is a third-party
  cookie, and browsers block or partition those — an embed authenticated that
  way works in one browser and silently fails in the next.
- **`frame-ancestors` from the key's origin allow-list**, so a page nobody
  authorised cannot render it at all.
- **Revocation is immediate.** Disabling or deleting a key ends its live
  sessions rather than letting them run to expiry.
- **`docs/embedding.md`** joins the manual, leading with the iframe
  microphone gotcha because everyone hits it.

### 2026-08-12 — identity, and the interface reads better

- **A new mark.** A standing wave: two fixed ends, a node at the centre, the
  envelope swelling between them. Not a metaphor — it is what the visualiser
  does. The full lockup sits above the sign-in.
- **The transcript follows itself down** while a reply is written, on every
  reveal path, and leaves the reader alone if they have scrolled up to
  re-read.
- **A viewer can switch the transcript off** and give the whole frame to the
  field.
- **A viewer's own controls persist** in their browser — mute, push-to-talk
  versus hands-free, transcript on or off — and outrank the shared settings
  until that browser's data is cleared. Deliberately only those three: the
  shared document still defines everything else for everyone.
- **Text throughout was too dim**; every opacity raised and the base UI colour
  lifted. Every button now answers the pointer, and scrollbars match the rest
  of the furniture rather than the operating system.

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
