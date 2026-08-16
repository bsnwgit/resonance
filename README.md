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
adapters that put a real assistant behind it, including a house through Home
Assistant, routes, so several names reach several destinations from one
display, displays the server knows about, so a name can be restricted to the
tablets you approved, and the embed API that lets another application put this
interface inside its own page.

**Not done, in the order it matters:** what a wall display actually looks like
— voice only, and a screensaver that is still the product, because burn-in
starts the day the first tablet goes up. Then staying up unattended. Then
identity and memory, so a conversation can mean something an hour later — the
embed is deliberately memoryless until that lands. Then packaging it as a
library other projects can install.

The [Roadmap](#roadmap) carries the reasoning for each, including the
decisions already taken about how identity and memory should work.

## How it works

```
  microphone ─→ VAD ─→ /stt (faster-whisper) ─→ wake-word gate ─→ /ask + route
                                            (which word → which route)   │
   visualiser ←── Web Audio analyser ←── /tts (Piper) ←── reply ←─────────┘
```

**Speech in.** Microphone through an adaptive voice-activity detector, then
transcription by [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
on the server. Push-to-talk (hold space) or hands-free.

**Speech out.** Neural voices via [Piper](https://github.com/rhasspy/piper),
rendered server-side and played through Web Audio. The browser's own voices
remain available as a fallback.

**It says why nothing happened.** A line above the input carries what was
heard and how long each stage took, that a recording came back empty, that it
is asleep and what it heard instead of a name, or why an endpoint failed. A
voice interface that goes quiet is indistinguishable from a broken one, and
that applies to its diagnostics as much as to its answers.

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

Those two are what a modest box wants, and they are the ones measured here.
**The panel offers every model faster-whisper can fetch** — `tiny.en` through
`large-v3`, the distilled variants, and the multilingual models, which are the
only way this transcribes anything other than English. Nothing here knows what
hardware somebody will run it on, so the list is not curated down to this one.
A model that is not already on disk is downloaded inside the first request
that asks for it.

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
| `http://<host>:9700` | redirects to 9701 — see below |
| `https://<host>:9701` | the display in full, including the mic |
| `https://<host>:9702` | **administration**, behind a sign-in |

The certificate is self-signed, so expect one browser warning.

**On your own machine, none of that applies.** Set *reachable at* to **this
machine only** in APP SETTINGS and restart, and there is no certificate to
make, no browser warning, and no first-run password to fish out of a log:

| listener | purpose |
| --- | --- |
| `http://localhost:9700` | the display in full — the mic works here |
| `http://localhost:9702` | **administration**, no sign-in |

Browsers already treat `http://localhost` as a secure origin, so `getUserMedia`
runs and nothing crosses a network for TLS to protect. Two settings decide
which of these you get — what it is reachable at, and what it takes to get in —
and they are independent. See *App settings & accounts* in the manual.

## Settings and the admin model

One settings document on the server defines the interface for **everyone** who
opens the display. The display only ever *reads* it. Writing happens on a
separate listener, on a separate port, behind a username and password.

**The public listeners have no route that accepts a write.** Not a guarded
route — no route. `admin.html` is not served on them either, and returns 404.
Users keep exactly four controls: microphone, mute, push-to-talk versus
hands-free, and whether the transcript is shown.

**A display says why nothing happened**, on a dim line above the input: what it
heard and how long each stage took, that a recording came back empty, that it
is asleep and what it heard instead of a name, or the reason an endpoint
failed. This is not a debug affordance bolted on — the messages already
existed and were being written to elements present only in the admin panel's
preview, so every explanation was discarded at the one place somebody was
standing. A voice interface that goes quiet is indistinguishable from a broken
one; that applies to its diagnostics as much as to its answers.

### What reaches a browser, and what never does

Three tiers, and the boundary between them is the whole of the model:

| tier | contents | who can read it |
| --- | --- | --- |
| **never leaves the server** | API keys, the Home Assistant token, adapter base URLs, password hashes | nobody, through any browser |
| **served to the display** | the settings document: appearance. The routes document: names, greetings, voices, wake words and how strictly each matches | today, anyone who can reach the port |
| **held by the browser, unreadable by it** | the device token, in an `HttpOnly` cookie | the server, on presentation |

The first row is the one that matters and it is absolute: no credential and no
upstream address is in any response the display listeners produce. Reading
everything a browser can obtain gets you no closer to reaching Home Assistant
or a paid API than reading nothing.

**You cannot keep a secret in a page you serve to somebody.** A token
embedded in `index.html` can be read out of it by whoever received the file,
so it is obfuscation rather than access control — the same reason the identity
design refuses to encrypt anything in the browser and keeps the secrecy in the
server-side mapping.

So the boundary is not *which fields are hidden*. It is **which devices may
ask at all**, and there are two mechanisms for that:

- **The network.** Bind to one address, firewall the port, and put the wall
  displays on their own isolated VLAN. An unapproved device cannot open a
  connection, so there is nothing to authorise. This is available now and is
  the strongest of the two.
- **The device token** — built. Server-issued on the first visit, `HttpOnly` so
  page script genuinely cannot read it, and an admin approves the device.
  `curl` does not have the cookie. A guest's phone is issued a token of its own
  and refused, because nobody approved that one.

#### The limitations, stated exactly

**A person using an approved device can read what that device reads.** This is
not fixable — the page runs on hardware they hold — and it is worth being
clear about how little it costs:

- On a **wall display**, that person is standing in your hallway, and they can
  already operate the house by talking to it. Reading the wake words they
  would have to say anyway is not the exposure in that room.
- On a **personal device**, that person is its owner, who says those wake
  words daily. The document tells them nothing they did not already have.
- In **neither case** does it yield a credential, an endpoint, or anything
  that would let them reach Home Assistant except by asking this server —
  which is the thing they were already allowed to do.

**Two people sharing one approved device cannot be told apart.** Approval is
per device. Distinguishing the people using it needs the PIN, and even then it
governs what is *remembered* rather than what may be *read*.

**A display learns the wake word of a route it may not use, and that is
deliberate.** It has to: recognising the house's name is the only way it can
*drop* an utterance addressed to the house instead of passing it into whatever
conversation it was already having. Withholding the word would not make the
phone in the room safer — it would make it answer on the house's behalf. What
the word buys whoever reads it is nothing: saying it into an unapproved device
is refused at `/ask`, by this server, on every request.

**What is exposed today:**

| | to | |
| --- | --- | --- |
| the settings document | anything that can reach the port | appearance values |
| a route's name, greeting and voice | anything that can reach the port | what makes a newly hung display look right before anybody approves it |
| a route's wake words and strictness | any browser that has said hello, approved or not | the gate rule above |
| a route's adapter, address and key | nobody, through any browser | not published at any tier |

The network is still the stronger of the two boundaries, and the VLAN is still
the right answer for wall displays. What the token changes is that reaching the
port is no longer the same as being able to *use* what is on it.

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

Nothing else is kept per viewer. Look, geometry, palette and voice remain
wholly admin-controlled, and the wake words are not in that document at all —
they belong to the routes — because the point of both is that one person
decides what everyone sees.

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

**HTTPS only wherever a network is involved.** The admin listener does not
start without a certificate, because it accepts a password and holds the
assistant's API key, and neither may cross the network in the clear. If it is
missing from the startup banner, run `make-cert.sh` and restart.

The one exception is loopback, where the reason does not apply: nothing
crosses a network at all, `http://localhost` is a secure origin in its own
right, and the certificate ceremony is pure obstruction in front of the
install that setting exists to make possible. With sign-in set to nothing
there is no password either — everyone who can reach that listener is an
admin, which is the whole of the setting and why it is only defensible when
the network is already the boundary.

> This is local-account authentication, deliberately: no directory, no third
> party, nothing leaves the machine to log in — the same principle as the
> speech pipeline. Inside a host application it should ride that
> application's existing session and roles instead.

## Connecting a real assistant

Out of the box it answers from built-in text, so the whole chain can be
commissioned before any backend exists. **RUN CHECK** on the SPEECH tab walks
each link — secure origin, settings store, transcription service, voices,
microphone, recorder, routes, the default route answering, render-and-speak —
and names whichever one is broken. Keep demo permanently: it is how you tell
whether a fault is the front-end or the model behind it.

**Demo is per route, and there is no display-wide switch for it.** There was
one, and it duplicated the route's own `demo` provider while silently
overriding it — two settings meaning the same thing, one of them invisible
from where the other is configured.

Configure the rest in the admin page under **AI → Assistants**. The panel is
deliberately terse; the reasoning behind each field is here.

### Routes, which the panel calls assistants

**The two words are deliberate, and they are not a synonym for each other.**
`route` is what the mechanism does — a name resolving to a destination — and
it is what the document, the API paths and the rest of this file call it. The
panel says *assistant*, because that is what an admin is setting up, and
because "route" already means something else entirely to anyone who has
configured a network. Code and interface are allowed to have their own
vocabularies; pretending one word serves both is how panels end up written for
their implementers.

**A route is a name that reaches a destination.** Say its wake word and
everything after it goes there until the sleep word or the awake timer — the
route binds to the *conversation* rather than to the sentence, so a follow-up
needs no second address. Saying a different route's name mid-conversation
switches to it, and the conversation does not come along: what was said to
one assistant is another party's words, and handing them over would pay for
them twice.

A route is a name, a wake word and its aliases, how strictly it matches, an
adapter and its configuration, and optionally its own greeting and voice — so
you can *hear* which one answered, which matters the moment two of them can
reply to the same room. Each carries its own model, prompt, context length
and key.

Exactly one is the **default**, and it is where anything with no name in
front of it goes: typed into the composer, sent through an embed, or spoken
while the wake gate is off.

**A route is published in two halves, and one of them not at all.**

| | fields | who sees it |
| --- | --- | --- |
| **presentation** | name, greeting, voice | anyone who can reach the port |
| **routing** | wake word, aliases, matching | the same today; behind the device token when displays land |
| **connection** | adapter kind, base URL, API key or house token, conversation agent, prompt, where it falls through to | nobody, through any browser |

The wake words must reach the browser because that is where matching happens.
The adapter kind must not: nothing needs it, replies come back already
labelled with the route that gave them, and it is the one field that tells a
reader what this box fronts. `public_routes()` enumerates what is published
rather than what is withheld, so a field added to a route later is private
until somebody decides otherwise.

**Matching strictness belongs to the route.** The matcher wakes on
near-misses, which is right for an assistant and wrong for a light switch:
the same false-positive rate costs a few tokens on one route and actuates
hardware on the other. An **exact hit always beats a fuzzy one**, wherever
each was found — otherwise a near-miss on one route steals an utterance that
named another outright, which is the worst failure available here.

Two routes cannot share a word, including through an alias, and it is refused
at the point of saving. Words that are merely *acoustically* close are not
checked — that wants the matcher that does the waking rather than a string
comparison, and it arrives with personal wake words.

**Upgrading is automatic and reversible.** `backend.json` becomes route one
on first start, taking its wake word from the shared settings so the box
answers to the same word afterwards as before. Both source documents are left
on disk: an upgrade that deletes what it read from has no way back if the
migration was wrong.

### The four providers

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

**ANTHROPIC** — **verified against a stub speaking its wire format, never
against the live service.** Stated here rather than left to be discovered:
every field below is implemented from the published shape and exercised
end to end against a server that answers in it, which catches a malformed
request but cannot catch a wrong assumption about what the real endpoint
accepts. Treat the first real key as the test.

It is a shape of its own rather than another preset, because the wire format
genuinely differs: the key rides an `x-api-key` header instead of
`Authorization: Bearer`, an `anthropic-version` header is required, the system
prompt is a top-level field rather than a message in the list, `max_tokens` is
mandatory, and the reply arrives as a list of content blocks rather than a
single string. Base URL is `https://api.anthropic.com` and there is only one,
so it has no preset — the provider button fills it. A key is required, and
saving without one is refused rather than discovered later by whoever is
standing in front of the screen.

**HOME ASSISTANT** — the house as an endpoint. **Proven against a real
installation, 2026-08-15**: spoken to by name, a real light switched on and off
by voice, the reply read aloud in that endpoint's own voice. Unlike the
Anthropic adapter above, this one no longer rests on a stub — though the stub
came first and caught the wire-format faults before a house was ever involved.

It is an adapter, not a second concept. Its conversation API is chat-shaped —
`POST /api/conversation/process` with a bearer token, text in and
`response.speech.plain.speech` out — which is the same shape the other two
produce, so it reaches the display through the machinery that was already
there. An "action target" beside the adapter would have been a second
mechanism for something the first one does.

Address is the Home Assistant origin, e.g. `http://homeassistant.local:8123`.
Pasting `…/api`, or the conversation path itself out of the documentation,
works too — what is typed is stored, and the path is normalised per request.

Three fields of the reply do more than carry the words:

- **`continue_conversation` is read and deliberately not acted on.** It was for
  one day. The reasoning was sound on paper — a completed command has nothing
  to follow, so close — and wrong in a room: the display went silently to sleep
  after every command, so the next sentence was dropped at the wake gate, and
  the next, and the next. Measured on the first real installation: five
  consecutive utterances transcribed and discarded, and a person reasonably
  concluding the thing had locked up. **The house had become the one endpoint
  you cannot speak to twice**, and the remedy — say a wake word again — is not
  discoverable from silence.

  The awake window already ends conversations, everywhere, identically. Closing
  a few seconds earlier is not worth an endpoint that behaves unlike all the
  others, and `true` needs nothing done to it, because staying awake is already
  what happens — which is what makes *"which room?" → "the kitchen"* work.
- **`conversation_id`** is held for exactly as long as the route binding —
  handed back on every turn, dropped on sleep and on switching endpoints. It
  is what makes *"which room?" → "the kitchen"* mean anything. The display
  treats it as opaque: it never reads one and never invents one.
- **`data.code == "no_intent_match"`** is the fallthrough signal, below.

**Give it a non-admin Home Assistant user of its own.** A long-lived token
carries that user's permissions and never expires, and every action appears in
the logbook as that user regardless of who spoke.

**What voice may touch is configured in Home Assistant**, by exposing entities
to Assist. This deliberately grows no allow-list of its own: that would be a
second, weaker copy of a control that already holds no matter what talks to
HA. The house's logic belongs to the house — which is the same reason the
system prompt is not sent, and why an LLM-backed agent's interpretation
belongs over there.

**Expose few entities to start with.** It shrinks the prompt on every call,
which is most of the latency, and it makes the choice easier, which is where a
small model actually fails. Choosing among four lights tests the design;
choosing among sixty tests the model.

**Home Assistant has no model of its own.** What it has is the harness: a
conversation-agent framework, integrations pointing at a model *you* supply,
and the exposure layer that turns entities into tools that model may call. So
adopting this still costs a model and somewhere to run it — a *second* one,
beside whatever endpoint Resonance already points at, and the two want
different things: conversational quality on one side, reliable tool calling on
the other.

**Not taken: the Wyoming satellite route.** It is HA's expected way to
integrate a voice device, and it inverts this product — HA would own wake word,
transcription and speech, leaving a microphone with a screen. The conversation
API keeps the seam at text, which is the one place these two systems agree.

### When a house recognises nothing

Nobody remembers which name owns which capability, so somebody will ask the
house a general question. **when it recognises nothing, ask** names another
endpoint to hand it to: the house reports `no_intent_match`, the model answers
instead, and the person is never told they used the wrong word. Structured, so
this is a branch rather than string-matching an apology.

The answer keeps the **house's name and voice** — the person addressed the
house, and an answer arriving in a different voice would announce the mistake
the fallthrough exists to hide. The house's `conversation_id` survives, so the
next turn still goes to the house.

**One hop, and never the target's own fallthrough.** A chain is a question
travelling somewhere nobody chose, at a cost per link, and two endpoints
pointing at each other would do it for ever. Deleting an endpoint clears
whatever pointed at it, rather than leaving an id naming nothing.

**When the fallthrough itself fails, the house's own words are not spoken.**
They would be a lie about the system: *"Sorry, I couldn't understand that"* is
true of the house and false of the arrangement, because the question *was*
placed with something that could have answered it and that failed. Speaking it
dresses a dead model as a badly phrased question — the same defect as a light
command failing quietly, wearing a politer hat — and the person has already
waited the full timeout to hear it. So the failure is spoken, naming the
endpoint that was addressed, with the reason on the display's status line. The
second endpoint is not named aloud: nobody addressed it.

**TEST does not follow the fallthrough**, because it exists to test that
endpoint's own connection and a pass that came from somewhere else would be
worthless. It says so now — *"in use a question like this would go to X
instead"* — after the house's refusal was read as a broken fallthrough twice
in one morning.

**With an LLM-backed agent this is an option you leave off.** That agent
interprets rather than matches, so `no_intent_match` essentially never fires
and the fallthrough is dead weight. It is the built-in intent engine that
needs it.

**And on the built-in engine it fires far less than this design assumed.**
Measured against a real installation, 2026-08-14:

| said | code |
|---|---|
| "how are you" | `no_intent_match` |
| "what's the capital of France?" | `no_valid_targets` |
| "tell me a joke" | `no_valid_targets` |
| "turn on the purple flamingo lantern" | `no_valid_targets` |

The engine matches a sentence *shape* before it looks for a device, so
*"what's the X"* and *"tell me a X"* both parse as **get the state of a device
called X** — and a general question comes back as an unknown device rather than
an unrecognised sentence. `no_intent_match` is left with the sentences that
match no pattern at all, which is a much smaller set than "things the house
cannot answer".

**Widening it to `no_valid_targets` is not free, which is why it has not been
done.** The last two rows of that table are byte-for-byte identical replies —
same code, same wording, same shape. So a command for a device the house does
not have cannot be told apart from a general question, and falling through
would hand *"turn on the garden fountain"* to a language model, which may
answer *"I've turned it on"*. Somebody then walks away believing the house
acted, which is the one failure this adapter exists not to have.

**Left as it is, deliberately, 2026-08-14.** What the person hears in the
meantime is the house's own *"I am not aware of any device called capital of
France"* — confusing, but true, and audible. If it is revisited, the shape is:
fall through on both codes, and append one line to the target's prompt for that
call only — *you cannot control any devices; if asked to, say you were unable
to* — which turns a mis-routed command into an honest refusal rather than a
claim. That reduces the hazard; it does not remove it, because a small model
can ignore an instruction. The real answer is an LLM-backed agent, where
neither code fires.

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

**Home Assistant takes only the timeout.** No model, no prompt, no reply limit,
no context length, no temperature, no keep-alive: it holds the conversation
itself against a `conversation_id`, and what its agent is told is configured
over there. Those controls hide themselves rather than sit on screen wired to
nothing — the same rule that hides temperature for Anthropic.

**Set that timeout to the agent, not to "Home Assistant".** The two agents are
orders of magnitude apart: the built-in intent engine answers in about a tenth
of a second, while an LLM-backed one is *two* model passes — one to emit the
tool call, another to write the reply once HA has executed it — each carrying
the exposed-entity tool definitions in its prompt. On modest or CPU-only
hardware that is tens of seconds, and a timeout chosen for the first cuts off
requests that were about to succeed.

**A failure has to be audible.** A chat backend failing quietly is an
annoyance; a light command that failed quietly is indistinguishable from one
that worked, and somebody walks away believing the house did something.
Unreachable, rejected token and HA-side error are all spoken — as *"I could not
reach the house just then"*, naming the endpoint and never the reason. The
reason goes to the note on screen, because `401 from the conversation API`
tells the person standing there nothing they can act on while telling everyone
in earshot what this box is wired to. An action that succeeds and says nothing
is spoken as **"Done."** for the same reason: silence is how a failure sounds.

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
anyone who opened the page. The routes live in their own `routes.json` at mode
600, admin-only, one key per route, and a key is never returned to a browser:
the field shows whether one is stored, not what it is. **FORGET KEY** clears
it for the selected route.

Changing a route's provider drops its key and its base URL unless new ones
arrive in the same save. Carrying one provider's endpoint into another would
send a hosted key to whatever is listening on the old URL — a failure in the
one direction that looks like success.

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
| `GET` | `/stt/status` | which transcription models are resident, and which this server will accept |
| `POST` | `/tts` | text in, WAV out. `?voice=`, `?rate=` |
| `GET` | `/tts/voices` | installed neural voices |
| `GET` | `/settings` | the shared interface configuration |
| `GET` | `/routes` | the routes: presentation to anyone, the routing half only to a caller holding a display token, and `allowed` per route for that caller |
| `POST` | `/ask` | a question — `{"route": …}` picks one, absent means the default. `{"conversation_id": …}` continues one the endpoint is keeping, and the reply carries that id back. `403 {"refused": "display"}` where this display may not use that route |
| `POST` | `/display/hello` | a display announcing itself: declared name in, its identity out, and a token in an `HttpOnly` cookie if it had none. Same-origin only |
| `POST` | `/display/request` | a device asking for access, answering the form the admin built — or `{"renew": true}`, which asks again on the answers already held. Same-origin only |
| `GET` | `/e/<code>` | an enrolment code, typed into the device being enrolled. Spends the code, sets the cookie, and redirects to the display with `?enrol=` saying how it went. Display listeners only |

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
| `POST` | `/settings` | write the configuration — `admin` role. A bare object replaces it; `{settings, merge}` writes only the keys it carries |
| `GET` | `/app` | ports and session length, plus what is actually running |
| `POST` | `/app` | change them — `admin` role, restart to apply |
| `GET` | `/users` | list accounts — `admin` role |
| `POST` | `/users` | create an account — `admin` role |
| `POST` | `/users/role` | change a role — `admin` role |
| `POST` | `/users/delete` | remove an account — `admin` role |
| `GET` | `/routes/all` | every route in full, less the keys — `admin` role |
| `POST` | `/routes/new` | create one — `admin` role |
| `POST` | `/routes/save` | change one — `admin` role |
| `POST` | `/routes/default` | choose which answers the unaddressed — `admin` role |
| `POST` | `/routes/enable` | enable or disable one — `admin` role |
| `POST` | `/routes/delete` | remove one, and its key — `admin` role |
| `POST` | `/routes/test` | one real round trip against that route — `admin` role |
| `GET` | `/displays` | every display, plus the address an enrolment code is typed into — `admin` role |
| `POST` | `/displays/new` | create a row before its device exists, and issue its code — `admin` role |
| `POST` | `/displays/reissue` | kill the row's live token now and issue a new code; name and permissions kept — `admin` role |
| `POST` | `/displays/decide` | approve — with the endpoints it may use, in the same call — or refuse, with a message for them, a note for you, and whether it may ask again — `admin` role |
| `POST` | `/displays/settings` | whether guests may ask, how long a grant lasts, the two limits, and the request form — `admin` role |
| `GET` | `/groups` | every group, plus the two populations one can be drawn from — `admin` role |
| `POST` | `/groups/save` | create one, rename it, or set its membership — `admin` role |
| `POST` | `/groups/delete` | remove one, and take it off every endpoint that named it — `admin` role |
| `POST` | `/displays/approve` | approve one, or withdraw it; may name it in the same call — `admin` role |
| `POST` | `/displays/rename` | change what it is listed as; blank hands the row back to the name the device declares — `admin` role |
| `POST` | `/displays/delete` | revoke: its token stops matching, and it is removed from every route's allow-list — `admin` role |
| `GET` | `/embeds` | list embed keys — `admin` role |
| `POST` | `/embeds` | create one; the key is returned once — `admin` role |
| `POST` | `/embeds/enable` | enable or disable one — `admin` role |
| `POST` | `/embeds/delete` | revoke one — `admin` role |

**Everything else 404s, including files that are not secret.** The server
hands out four files — `index.html`, `admin.html`, `icon.svg`, `lockup.svg` —
and refuses every other path. An allow-list rather than a list of things to
hide, because the directory `serve.py` runs from is a deployment: the base
class serves whatever is sitting in it, and what was sitting in it was the TLS
private key, the account hashes and one API key per route. Deny-by-default
also answers traversal and percent-encoding without either needing a rule.

The last admin account cannot be deleted or demoted; an interface nobody can
administer is a brick. The last route cannot be deleted or switched off for
the same reason: a server with nowhere to send a question is a composer wired
to nothing, recoverable only by editing JSON on the box.

`/routes` is the one path with a public half and a private half, and every
privileged operation sits under `/routes/…` precisely so the admin-only list
can stay a list of paths rather than a list of paths and methods.

`/display/hello` and `/displays` are one letter and a whole boundary apart, for
the same reason. A display has to be able to reach the first from the listener
it is served on; everything an *admin* does to a display is the second, and is
absent from that listener entirely.

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
it read as simply broken. The panel's live status text now states whether each
gate is in effect and why, and the gate grew an ALWAYS mode for anyone who
wants the word required in push-to-talk too.

**And saying so in the panel is not saying so where it happens.** That status
text was written for the admin sitting in front of the settings; the person
standing in front of the *display* got nothing, for a year, because the two
elements it writes to were never in `index.html` at all. The lesson is not
"add a status line" — it is that a message is only delivered where the fault
is experienced, and a panel that reports faults to their configurer instead of
their witness has not reported them.

**A deployment directory is not a document root.** `SimpleHTTPRequestHandler`
serves what is beside it, and beside it were `key.pem`, `users.json`,
`routes.json` and the source. The fix is an allow-list of the four files that
are genuinely pages or artwork; the lesson is that a *denylist* of secrets
cannot be written correctly, because the file holding one credential per route
did not exist yet when it would have been written. Deny by default, and
enumerate what is published rather than what is withheld — the same shape as
`public_routes()`.

**A dangling CSS selector list is invisible to every check.** Deleting a rule
took the `{max-width:560px}` off the end of a shared selector list, leaving
three selectors reading on into the next rule — which was `display:none`, so
the filter field, the tab caption and the whole tab row vanished. The braces
still balanced, the JavaScript still parsed, and CSS has no error to report:
it simply continues to the next block. The check that catches it is that no
comma-terminated selector line may be followed by a comment or a blank line.

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

This stopped being "roughly in order of value" the moment there was a concrete
deployment to build for. A real target decides what blocks what, and several
things that looked independent turn out to sit on top of each other.

### The deployment this is now ordered around

Wall-mounted tablets through a house, driving **Home Assistant by voice**,
while remaining a general assistant. It is a gateway: one name reaches the
house and can switch a light on, another reaches a model running locally, a
third reaches a hosted one — every wake word a field somebody sets, none of
them a default. People also have their own devices, their own conversation
histories, and are standing in the same rooms as the tablets.

Of those three destinations only the house is new work. A local model and a
hosted one are the `openai` dialect and the `anthropic` adapter that already
exist; what changes is that they stop being *the* configuration and become
entries in a set.

That last sentence is where the difficulty lives. Everything else follows from
two people in one room with three listening microphones between them.

### Build order

| | phase | delivers | sits on | open decisions |
|---|---|---|---|---|
| 1a | ~~**Routes**~~ **— done** | three names reaching three destinations, verifiable with no Home Assistant involved | — | none |
| 1b | ~~**The Home Assistant adapter**~~ **— done** | saying the house name switches a light on | 1a | none |
| 2 | ~~**Displays, and binding a route to one**~~ **— done** | only the tablets you approved can actuate the house, whatever anyone's browser is set to | 1b | none |
| 3 | **What a wall display looks like** | voice only, and a screensaver that is still the product | 2 | none |
| 4 | **Staying up unattended** | a tablet nobody touches for a year is still working | 3 | **all of it** · not designed |
| 5 | **Identity and the PIN** | a person, as distinct from a place | 2 | **1** · whether an identity carries its own Home Assistant token |
| 6 | **Personal wake words** | one person addressing a tablet stops triggering another person's device | 5 | none |
| 7 | **Memory** | conversations that mean something across sessions | 5 | **1** · what the retained unit is — deliberately left to experience |
| 8 | **Diagnostics** | a failing screen findable without standing in front of it | 2 | **1** · the retention default |

The last column counts decisions that need **you**, not implementation choices
made while building and shown afterwards. A phase reading *none* is ready to
start.

**Nothing outstanding blocks starting.** Everything before phase 4 reads
*none*, and phase 4 is a design problem to think through rather than a
question to answer — its position will move once it has been. The three
remaining are each answerable when their own phase comes up, and one of them
is deliberately waiting on experience rather than on a decision.

**One is two deliveries rather than one.** Routes stand up on their own — demo,
a local model and a hosted one are three destinations reachable by three
names, and wake-word routing can be shaken out on a test box before Home
Assistant is anywhere near it. If the refactor breaks something, that is when
you find out, rather than while also debugging a new adapter.

**2 is done.** A display is issued an unguessable token on its first visit, an
admin approves it, and a route can be restricted to the ones it names — where
the refusal is silent, at the display and again at the server. What it turned
up while being built is in the log below; the one design point worth having
here is that **restricting a route is opt-in, per route**. Every route was
reachable by anything before this existed, so an upgrade that quietly made them
all refuse would take a working installation off the air to enforce a rule
nobody had asked for yet. `ANY DISPLAY` is the default, and the panel says so
on every route that has it.

**1b is done**, and the phrase that closed it was *"turn off couch lamps"*
answered by *"Turned off the light"* — a real house, a real token, a real light,
spoken to by name. It was built against a stub first, which was worth doing:
the wire-format faults were all found there, and what the real installation
then caught were things no stub could have — an intent engine that reports an
unknown *device* where the design expected an unrecognised *sentence*, and a
hang-up that was correct on paper and made the house the one endpoint you
could not speak to twice.

Both of those are in the log below. Neither was a coding error; both were
assumptions, and only a house could refute them.

**1a is done**, and closed out rather than left half-verified. Proven on real
hardware with a real microphone: several names reaching several destinations,
each answering in its own voice, each line of the transcript credited to
whoever gave it, and LEARN teaching an endpoint the spellings a transcriber
actually returns. The one thing it does not cover is the Anthropic adapter
against the live service — see the note under that provider.

Splitting it from the Home Assistant adapter earned its keep: it turned up
three faults that had nothing to do with Home Assistant, plus two secret
disclosures, all of which would otherwise have been debugged through a new
adapter.

**Four is a placeholder, not a specification** — see its entry. Its position
here is a guess and will move once it has been thought through.

Two and three were one phase until the wall-mounted side outgrew it. They
share a substrate — a display the server knows about — but nothing else:
phase 2 is server-side enforcement and gate logic, phase 3 is canvas and
presentation. Splitting them keeps each verifiable in one sitting, and stops a
safety property waiting on a screensaver.

**Three sits where it does because burn-in is a clock, not a backlog item.**
Every day a tablet runs without it is damage that cannot be taken back, and
that clock starts the day the first one goes on a wall — which, now that two
has landed, is any day from here. Everything after it can wait; this cannot
wait as cheaply.

**The admin interface is part of each phase, not a phase of its own.** A route
you cannot configure is not a feature, and a phase whose settings are only
reachable by editing JSON on the box cannot be tested by the person who wants
it. Each entry below carries its own panel scope.

---

- **Routes, and Home Assistant.** One assistant configuration becomes a set of
  named ones. A route is a name, a wake word and its aliases, an adapter and
  its configuration, and optionally its own voice — so you can *hear* which
  one answered, which turns out to matter when two of them can reply to the
  same room.

  `/ask` takes a route. The adapter machinery underneath does not change.

  **A route is published in two halves, and one of them is never published at
  all.** Wake-word matching happens in the browser, so some of a route has to
  reach it; the rest has no business there.

  | | fields | who sees it |
  | --- | --- | --- |
  | **presentation** | name, greeting, voice | anyone who can reach the port |
  | **routing** | wake word, aliases, match strictness | the same today; behind the device token from phase 2 |
  | **connection** | adapter kind, base URL, API key, Home Assistant token | nobody, through any browser |

  **The adapter kind is on the wrong side of that line to publish.** Nothing
  needs it — routing is by wake word and replies come back already labelled —
  and it is the one field that tells a reader this box fronts a home
  automation system rather than merely an assistant. That is a targeting
  signal rather than a name. If the interface later wants a house route to
  *look* different, the server can send a neutral presentation hint that says
  "style this one apart" without naming what it connects to.

  **Splitting presentation from routing is what lets an unapproved display
  still render.** Appearance and names are harmless and keep a newly hung
  tablet looking correct; the wake words are what actually make it usable, and
  those move behind the device token when phase 2 lands. Until then the whole
  document is readable by anything that can reach the port, which is an
  argument for the network boundary rather than for delaying either phase.

  **The wake word that woke it decides the route, and the route stays bound to
  the conversation rather than to the sentence.** This falls out of what is
  already there: the wake word does not gate each utterance, it sets `awake`
  with a timeout and everything after it passes through until the sleep word
  or the timer. So a follow-up reaches the same destination without being
  re-addressed, which is the only tolerable behaviour for speech.

  **Home Assistant is an adapter, not a second concept.** Its conversation API
  is chat-shaped: `POST /api/conversation/process` with a bearer token, and
  the reply carries `response.speech.plain.speech` — text to read aloud, the
  same shape `openai` and `anthropic` already produce. Inventing an "action
  target" beside the adapter would be a second mechanism for something the
  first one does.

  Two fields of that reply are worth more than they look:

  **`continue_conversation` was going to decide whether to hang up** — read
  the flag, call `sleepNow()` when it is false. Built that way, tried in a
  room, and taken out the next morning: see the entry under the provider. The
  awake window ends conversations for every endpoint, and a house that closes
  a few seconds earlier is a house you cannot speak to twice.

  **`data.code == "no_intent_match"` is the fallthrough signal.** Nobody
  remembers which name owns which capability, and asking the house a question
  it cannot answer will be constant. A route can name another to fall through
  to: the house does not recognise it, the model gets it instead, and the
  person is never told they used the wrong word. Structured, so this is a
  branch rather than string-matching an apology.

  **`conversation_id` has to be held for the awake window.** HA returns one
  and accepts it back, and it is what makes *"which room?" → "kitchen"* work.
  Its lifetime is exactly the route binding's: hold it while awake, send it on
  every turn, drop it on sleep.

  **`agent_id` is a field on the route, not a constant.** HA can have several
  conversation agents, and which one answers changes the design around it:

  - the **built-in intent engine** matches sentences, so it reports
    `no_intent_match` reliably and the fallthrough above is what makes it
    usable
  - an **LLM-backed agent** interprets instead of matching, so "it's a bit
    dark in here" works, and `no_intent_match` then essentially never fires

  **HA has no model of its own.** What it has is the harness: a
  conversation-agent framework, integrations that point at a model *you*
  supply — hosted, or local through its Ollama integration — and the exposure
  layer that turns your entities into tools that model may call. Worth being
  exact about, because it means adopting this still costs you a model and
  somewhere to run it.

  **The LLM agent is the one this deployment wants**, and the interpretation
  belongs on the HA side rather than here — but for a narrower reason than
  "HA does it already". What is not worth rebuilding is the **tool and
  exposure layer**: entity discovery, tool definitions, the calling loop, and
  the gating that decides what may be touched. That is HA's, it is the fiddly
  part, and a copy here would be a second weaker version of a control that
  already holds no matter what talks to HA. The rule from the entity-exposure
  note applies to the reasoning as well as the permissions: **the house's
  logic belongs to the house.**

  One consequence of supplying that model: it is a *second* one, beside the
  route Resonance already points at. On one Ollama instance that is a single
  box serving two callers that want different things — conversational quality
  on one side, reliable tool calling on the other — and those are not always
  the same model.

  Consequence worth stating plainly, because it inverts the paragraph above:
  with an LLM agent, fallthrough is an option you leave off for that route
  rather than the thing that rescues it.

  **What voice may touch is configured in HA**, through exposing entities to
  Assist. Resonance must not grow its own allow-list of entities — it would be
  a second, weaker copy of a control that already holds no matter what talks
  to HA.

  **Give it a non-admin HA user of its own.** A long-lived token carries that
  user's permissions and never expires, and every action appears in the
  logbook as that user regardless of who spoke. Once identities exist, an
  identity can carry its own token, which is the only way to make HA aware of
  who actually asked.

  **Timeout belongs to the route, and tracks the agent rather than "HA".**
  The two agents are orders of magnitude apart: the built-in intent engine
  answers in about a tenth of a second, while an LLM agent is *two* model
  passes — one to emit the tool call, another to write the reply once HA has
  executed it — each carrying the exposed-entity tool definitions in its
  prompt. On modest or CPU-only hardware that is tens of seconds, and a
  timeout chosen for an intent engine would cut off requests that were about
  to succeed.

  The corollary for a first deployment: **expose few entities.** It shrinks
  the prompt on every call, which is most of the latency, and it makes the
  choice easier, which is where a small model actually fails. Choosing among
  four lights is a fair test of the design; choosing among sixty is a test of
  the model.

  **A failure has to be audible.** A chat backend failing quietly is an
  annoyance; a light command that failed quietly is indistinguishable from one
  that worked, and somebody walks away believing the house did something.
  Unreachable, rejected token and HA-side error all get spoken.

  **Not taken: the Wyoming satellite route.** It is HA's expected way to
  integrate a voice device, and it inverts this product — HA would own wake
  word, transcription and speech, leaving a microphone with a screen. The
  conversation API keeps the seam at text, which is the one place these two
  systems agree. Recorded so it is not rediscovered as an oversight.

  **Match strictness belongs to the route.** The existing matcher wakes on
  near-misses, which is right for an assistant and wrong for a light switch:
  the same false-positive rate costs a few tokens on one route and actuates
  hardware on the other. Exact on routes that do things, fuzzy on routes that
  answer.

  **Wake words want to be acoustically distant, not merely different.** Three
  shared names plus a personal one per person is a lot for a fuzzy matcher on
  transcribed speech to tell apart. Differing syllable counts, vowels and
  stress survive a noisy room; two names a letter apart do not. Worth choosing
  on that basis before a household learns them, because changing one
  afterwards is its own small misery.

  *Panel:* one block per endpoint rather than one form — its wake word and its
  connection together, saved together, with its own TEST. For a house route
  that test is worth more than usual, since it answers whether the token, the
  agent and the exposure are all right at once. Built; see the progress log.

  *Built, with one thing the design did not anticipate:* a round trip that
  comes back **"Sorry, I couldn't understand that"** is a **pass**. The
  built-in intent engine matches sentences, and a test sentence is not a
  command — so the reply that proves the address, the token and the agent are
  all correct is the one that reads like a failure. TEST says so in as many
  words rather than leaving an admin to conclude it is broken. The fourth
  thing, whether the right entities are exposed, only a real command answers.

- **Displays, and binding a route to one — built 2026-08-15.** The problem this
  exists for: two people in a room, one of them addressing the wall tablet, and
  everybody else's microphone hearing it too.

  Push-to-talk on personal devices is the correct configuration and is already
  a per-browser setting — and it is not a control, because nothing makes
  anybody set it. **So the enforcement is server-side at `/ask`:** a route
  carries the displays allowed to use it, and a phone that wakes on the house
  name is refused there regardless of how its browser is configured. The
  browser's settings stop being load-bearing.

  **A name cannot be the credential.** `?display=kitchen` is guessable, so
  binding on the declared name alone would let anything that types it reach
  the route. The server issues an unguessable token on first visit and an
  admin approves the device; the name says which place it is, the token says
  it is that place. This is the `token` row of the identity entry below,
  needed here first and for a different reason.

  **The refusal is silent.** No spoken error, nothing in the transcript: that
  utterance was addressed to a different device, and one nobody was talking to
  announcing that it cannot help is noise laid over the answer somebody is
  waiting for.

  **The same rule has to apply mid-conversation**, which is the worse case.
  A device already awake on its own route passes everything it hears straight
  through — so another person's house command would land in a stranger's
  conversation, be paid for, and be answered aloud. The gate rule:

  > Hearing a wake word for a route this display is not allowed to use — drop
  > the utterance. Do not pass it to the current route, and do not switch.

  Stated that way it also gives the behaviour you *do* want: where the display
  **is** allowed the route, hearing its wake word mid-conversation switches to
  it. One person at one tablet changing what they are addressing.

  **An unapproved display renders, and cannot be spoken to.** The appearance
  settings are public, so a new tablet shows the geometry correctly the moment
  it is hung; it holds no approved token, so no wake word reaches a route.
  Hang it, see it appear in the admin list, approve it, and it starts working.
  Wrong-looking and refused would be a worse first five minutes than
  right-looking and inert.

  It is also the answer to the obvious attack, and the reason a token exists
  rather than a URL being treated as secret. Somebody types a wall display's
  URL into their own phone: that phone has no cookie, so it is issued a *new*
  token, which nobody approved. The kitchen tablet's token is in the kitchen
  tablet's cookie jar and was never in the URL. **The URL is a name, not a
  key** — which is the same point as names being guessable, wearing a
  different hat.

  **Places and people bind differently, and the difference is cardinality:**

  | | bound by | how many devices |
  | --- | --- | --- |
  | a **place** — the tablet in the kitchen | token + an admin approving it | exactly one |
  | a **person** | their PIN | as many as they like |

  A wall display is one physical object and two things claiming to be it is
  always wrong, so it is pinned to a single token that an admin blesses. A
  person is not a physical object — phone, tablet and laptop are all
  legitimately them — so their credential is something they *carry* rather
  than something a device *has*. They enter the PIN, that device earns its own
  token, and they are not asked again.

  One mechanism, two ways of granting it: an admin bestows a place's, a person
  earns their own.

  **An unapproved request is recorded and shown**, with the display it asked
  for and when. Not an alarm — a line in the list. It is the enrolment queue
  when it is your own new tablet, and the early warning when it is somebody
  trying a URL they overheard.

  A stored device fingerprint may sit beside that entry as a **hint for the
  person approving** — "this matches your approved kitchen display" — for the
  one case a token cannot survive, which is a browser wiping its data. It must
  never become the credential: fingerprints are forgeable by the client,
  unstable across updates, and identical across two tablets bought together,
  which is every property you do not want in one.

  **A display can also be enrolled deliberately, by a code typed into it.**
  Added after the first build, because approving-what-turns-up is the wrong
  shape when you *knew* the screen was coming: you create the row in the panel,
  name it and tick its endpoints before the device is switched on, and the code
  binds a device to it.

  The constraint that decides everything about the code is that it is **typed,
  on the device being enrolled** — a television with a remote, or an on-screen
  keyboard. So it is six characters, and six characters are only safe because
  of the four rules around them: one use, ten minutes, a back-off after five
  wrong guesses, and an alphabet with no character that can be misread into
  another (`O`/`0`, `I`/`1` and `l` are simply absent). Case, dashes and spaces
  are ignored, so the panel can print `K7QP-4M` and `k7qp4m` still works.

  **And a device can ask, which is the other half of the same problem.** The
  wall-screen case has an admin who knew the screen was coming. The case that
  drives everything else is an endpoint restricted because it *costs* — a
  hosted model given to some people and not to everyone — where the person
  turning up is a colleague on a laptop in another building and the admin has
  never seen the device.

  So: a switch, and a form.

  **Whether an uninvited device may ask at all is a setting**, and turning it
  *off* has a precondition — the default endpoint must be open to any display,
  because that is the only thing an uninvited device can then reach. Enforced
  from both ends: it refuses to switch off with nothing open, and refuses to
  close that door afterwards while it is off. One end only, and it holds until
  the next edit and then breaks silently.

  **The form is the admin's, field for field** — up to five, each labelled and
  optionally required, one of them a box big enough for a reason. This server
  has no opinion about what a request should ask: a campus wants a name and a
  department, a house wants none of it. The answers are what an admin who
  cannot see the device decides on, which is the whole reason the form exists.

  **Approving is granting.** The endpoints are ticked in the same gesture as
  the approval, because the reason to approve anybody is to give them a
  particular assistant — an approval that grants nothing is a row that changed
  colour. Refusing carries two messages, one shown to them and one that never
  leaves the panel, plus a choice of whether that device may ask again, and it
  takes back anything a previous approval gave.

  **A grant to something that asked runs out; a grant to a screen an admin
  invited does not.** Guest access is a lifecycle rather than a session: it
  expires, the person presses ASK AGAIN — not the form again, because their
  answers are held — and the row counts the renewals. A wall screen going dark
  on a timer is not a security property, it is an outage, so an invited display
  never expires whatever the setting says.

  Expiry is read where the request is answered rather than at the door, which
  is what makes a grant run out cleanly mid-conversation: the turn already in
  flight finishes, and the next one is refused.

  **A refusal is per device, not per person** — the same human on their phone
  is a new row with a fresh ask. That is what device identity is, and anything
  stronger needs an identity a person carries.

  **Groups, so a grant is made once.** Twelve people who all get the same
  endpoint is twelve ticks and a re-tick every time somebody gets a new phone,
  which is not a permission model, it is data entry. A group is a name for a
  set of them, made under ACCOUNTS and named wherever access is granted.

  **Two kinds, and they do not mix**: people who asked to be here, and devices
  an admin created and sent a code to. They answer separate questions — *the
  physics department*, *the screens in the east wing* — and one list that could
  hold both would be a list nobody could describe. A group's kind is fixed at
  creation, because changing it would silently empty it.

  **Grants add up, and a group is not approval.** An endpoint reachable by a
  group and by one device on its own is reachable by both; being in a group
  never removes an individual grant. And somebody in a group who was never
  approved, or whose access has run out, is still refused — the group decides
  *which* endpoints, approval decides whether they reach anything at all.

  **REISSUE is the same mechanism pointed at a row that already exists** — a
  browser that wiped its data, a screen replaced in the same place. The row is
  the *place*: its name and every endpoint that names it survive, and the
  device behind it is swapped. **The live token dies when REISSUE is pressed**,
  not when the new code is used — a place is one device, so the moment you
  decide to move it, the old one stops being that place. Leaving it working
  until somebody got round to typing the code would mean two devices holding
  one place for as long as that took.

  *Panel:* a displays list — declared name, token, last seen, approve, rename,
  delete — unapproved requests with what they asked for, and an
  allowed-displays list on each route.

  **What was decided while building it**, none of which changes the design
  above:

  - **Restriction is opt-in, per route, and off by default.** `ANY DISPLAY` is
    what every route was before this existed; `ONLY THESE` names them. The
    alternative — approval required everywhere the moment this ships — would
    have taken every working installation off the air until somebody found the
    panel, to enforce a rule they had not asked for on routes where it buys
    nothing. A personal install on loopback never needs it at all.
  - **A restricted route with an empty list is allowed**, and reads *no display
    may use this endpoint* in the panel. Restricting one before the tablet that
    will use it has been hung is a legitimate order to do things in.
  - **The routing half goes to any browser holding a token, approved or not.**
    See the limitations section: an unapproved display has to recognise the
    house's name in order to drop it, and refusing to tell it the word would
    make it answer on the house's behalf instead.
  - **An embed is not a display and does not inherit one.** Its rights come
    from its key, so it reaches unrestricted routes and no others — a host
    application's page is not a place in your house.
  - **The panel's live preview is not a display either.** It is the panel,
    already signed in as an admin, and it is allowed every route: an admin can
    reach any of them from the panel anyway, and a preview that refused half
    of them would be lying in the other direction.
  - **A waiting display asks again every 20 seconds.** "Hang it, see it appear,
    approve it, and it starts working" has to mean without somebody walking
    back to the tablet to reload it. Only while it is waiting — approval taken
    away is caught at the server, which refuses whatever the page believes.

- **What a wall display looks like.** The two settings that make a tablet on a
  wall a different object from a browser tab. Both hang off the display the
  phase above registered, and neither touches the server's behaviour — this is
  entirely canvas and presentation.

  **Voice only** — the geometry alone, no transcript and no composer. That is
  what a tablet bolted to a wall wants: it is not a workstation, and a screen
  of scrolling text in a hallway is neither useful nor discreet.

  Most of this exists. `data-text="off"` already hides the transcript and the
  composer together, and the embed chrome does the same through
  `data-noparts`. What is missing is somewhere for an admin to say it once,
  per display, rather than it being whatever the last person to touch the
  screen chose.

  It has to **outrank the viewer preference**, which is a reversal worth
  stating: the three viewer controls were built to beat the shared settings
  deliberately, because a person in front of a screen knows better than a
  document does. This is the exception — a policy for a place, not a
  preference of a passer-by. And where it applies the TEXT button is
  **removed, not disabled**. A control that is present and ignores you is
  worse than one that was never offered.

  **A screensaver that is still the product.** A tablet showing a
  mostly-stationary field for years will burn it into the panel. The usual
  answer replaces the screen with something else; this one keeps the same face
  — every appearance setting still applied — and moves it.

  **Scale down, then drift**, rather than drift alone: drawn full-bleed there
  is nowhere to go and translating only clips the edges. Shrinking first
  creates the margin to move within, and lights fewer pixels while it is at
  it. Slow continuous drift rather than a bouncing path — it covers more of
  the panel over a night and is calmer to share a room with.

  **A dim level beside it**, as its own number. Reducing brightness does more
  against burn-in than movement does, and it is independently what a hallway
  screen should do at two in the morning.

  **It ends on the wake word or on touch**, easing back to the centre rather
  than snapping. On a voice-only display touch is the only signal that is not
  speech, so it has to count. The transcript hides while it drifts — text
  sliding around a screen is worse than either state on its own.

  *Panel:* voice only, and the screensaver's idle delay, scale and dim, on
  each display in the list the phase above builds.

- **Staying up unattended.** *Not designed yet — this entry states the problem
  and nothing else. Its position in the order is provisional.*

  Everything built so far assumes a page somebody opened and will close. A
  tablet on a wall is a browser tab running for a year: through server
  restarts, network drops, Home Assistant reboots, certificate renewals and
  its own operating system's ideas about backgrounding, with nobody standing
  in front of it to notice or reload.

  The questions, unanswered:

  - does the page recover by itself when `serve.py` restarts, or does somebody
    walk over and tap reload
  - does a failed request retry, and how does it behave while the server is
    down — quietly, or by saying so
  - does anything leak over weeks: the canvas, the transcript, audio nodes,
    the session
  - what happens when the tablet's browser suspends a background tab, or the
    screen sleeps, or the device reboots at 4am after an update
  - how does anyone *find out* it stopped working, given the whole point of
    the two phases above is that it shows very little

  The failure mode worth designing against is specific: **a screen that looks
  perfect and does nothing.** The geometry is still moving because it is
  driven locally, the drift is still drifting, and nothing has reached the
  server in a week. That is worse than a blank screen, which at least gets
  reported.

  It is not much work. It is invisible work, which is why it needs its own
  entry — nobody ever gets to it as part of something else.

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
  between a place and a person — for what may be *remembered*. What may be
  *reached*, and for how long, stays with the display it was entered at; see
  the session paragraph below. Hashed server-side with the same PBKDF2 as the
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

  **A PIN session is measured in hours, and it belongs to the display URL that
  triggered it — not to a person, and not to one setting covering all of
  them.** Each `?display=<name>` carries its own session length, set by an
  admin alongside that display's other properties.

  The place is what decides how long unlocking should last, because the place
  is what carries the risk. A workshop screen nobody but the workshop can
  reach and a reception screen in front of the street are the same person on
  the same PIN and want opposite answers, and a per-person number gets both
  of them wrong — too short to be tolerated in the workshop, too long to be
  defensible at reception. An admin securing a room can reason about that
  room; nobody can reason usefully about a number that follows a human
  between the two.

  It also keeps the axes apart, which is the same discipline as capability
  versus chrome in the embed, and binding versus authentication above:
  **memory follows the person, session length follows the URL.** They are
  independent, so they get independent settings. Collapsing them would mean
  choosing between a display that forgets what it knows about somebody and a
  display that stays unlocked all night, when those are not the same question.

  Separate from the admin's setting for the same reason, and the units say so:
  an admin holds the configuration everyone else is looking at the results of
  and is measured in minutes, while somebody who has unlocked a display is
  standing in front of a screen doing their work. Being asked to key a PIN in
  again every half hour would end with the PIN switched off entirely.

  Recorded plainly: a PIN is not a password, and this is a lightweight account
  system rather than a small feature. Six digits is a low bar that rate
  limiting carries. It suits an internal tool and a number keyed into a
  screen, and it should not be the only thing standing in front of anything
  genuinely sensitive. It depends on HTTPS only — a PIN must never be
  enterable on the plain listener.

  Devices and identities are listed in the admin page with when they were last
  seen, and deletable there.

  **This work now also owes the middle rung of the sign-in axis** — a single
  PIN for the whole display, no accounts. Binding and authentication shipped
  with their outer two rungs only, because that rung is this machinery pointed
  at a display rather than at a named person, and building it twice would be
  the waste. The setting is present and disabled until then, so the gap is
  visible rather than silent, and the server names it specifically if
  something asks for it over the API.

  **The token row is pulled forward** into the displays entry above, where it
  is needed to make a route binding hold rather than to make memory durable.
  What is left here is the PIN, and the thing the PIN unlocks: **per-identity
  settings**, a storage tier that does not exist yet. There is shared
  configuration, per-browser preference, and per-embed grant; a setting that
  belongs to a *person* has nowhere to live. Personal wake words are the first
  thing to need it and memory is the second.

  *Panel:* identities, PIN policy and its minimum length, per-display session
  length, and a PIN reset on the device list.

- **Personal wake words.** Two people in a room, both with their own devices,
  and one of them says the name that reaches the model — both devices answer.
  Route binding cannot help: they are both legitimately allowed that route.

  Give an identified person their own wake word and the collision stops
  happening rather than being reconciled after the fact. It is also what
  people expect: an assistant answers to a name you chose.

  **Uniqueness has to be enforced with the matcher that does the waking**, not
  a string comparison. A word acoustically close to the house name, or to
  somebody else's, puts you back where you started — so a candidate is run
  through the same fuzzy matcher against every word already in use and refused
  on a near-hit. What passes validation is then exactly what will not
  cross-trigger, because the same function decided both.

  Shared words stay the default for any display with no identity attached,
  which is every wall tablet. One consequence to expect: a person standing at
  a tablet and using *their* word gets nothing, because that tablet is not
  their device. Correct, and it will still surprise somebody the first time.

  *Panel:* a wake word on each identity, with the collision check answering at
  the point of entry rather than on save.

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

  *Panel:* retention window, what is held per identity, and deletion — for an
  admin over anybody, and for a person over themselves.

- **Diagnostics.** Technical events keyed to a device: the microphone would not
  open, transcription took four seconds, the voice service returned an error,
  this browser has no recorder. A health view per device in the admin page, so
  a failing screen can be found without anyone standing in front of it.

  Sits on the displays entry rather than on identity: the useful key is the
  device with the failing microphone, not whoever happened to be standing at
  it.

  **This entry used to promise "no conversation content", and that boundary
  has moved.** Stated precisely rather than quietly broken, because a promise
  like that is worth only what it is kept to:

  > What was addressed to the device — from the wake word to the end of the
  > conversation — and the routing decision that followed, retained for a
  > window. Nothing outside an active conversation is recorded.

  The reasoning for the change: a voice-only display shows nobody anything, so
  when it mishears there is no record at all and nothing to fix. And the
  captured text is exactly what already leaves the machine — it goes to HA or
  to a model regardless — so this adds retention, not disclosure. Nothing is
  captured unless somebody said a wake word.

  **The words are the least useful part.** What makes a voice fault
  diagnosable is the decision trail beside them:

  - what the recogniser produced, **before** the wake word was stripped
  - which route matched, and how — exact, or fuzzy on which alias
  - what was sent, what came back, how long each leg took
  - errors, verbatim

  "It didn't work" then resolves into *the recogniser heard "hows" and matched
  it fuzzily to the house route*, which is something you can act on. It is
  also the only way to find out that two wake words are cross-triggering,
  which is the standing risk of several shared names in one house.

  Some of this is already computed and thrown away: the interface says *woke
  on "hows" (near "house")* as a note that fades, and on a wall tablet nobody
  is ever there to read it.

  Retention is the control, since there is no other, and it wants a short
  default rather than a generous one.

  *Panel:* health per display and the conversation record, alongside the entry
  that already lists them; retention window; deletion.
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
Four of the remaining entries were nice-to-have while this was a chat window
on a desk. A tablet bolted to a wall, answering a household, moves them:

- **Barge-in.** Detect speech during playback and duck immediately. Nobody
  tolerates waiting out a wrong answer — and a wall tablet is the case where
  you cannot simply stop it, because there is no keyboard and you are holding
  something in both hands.
- **State in the geometry.** Distinct colour and motion for thinking, speaking
  and *failing*, so a fault is visible without reading anything. The two
  adapter kinds now have wildly different tempos — a local intent answers in
  about a tenth of a second, a model takes seconds — and a display that looks
  identical during both teaches people it has frozen.
- **Domain vocabulary hints.** `?hint=` already exists and is unused. **Home
  Assistant knows its own room and entity names**, which is exactly the
  vocabulary the recogniser is going to get wrong: "turn on the bedside lamp"
  fails on the two words that carry the whole sentence. Pulling that list from
  the same server the route already points at is close to free, and it
  improves the case that matters most.
- **Unprompted speech.** Let a host application make it speak — an alert
  arrives, the geometry wakes, it tells you. That is a different product from
  a chat box. The `signage` embed preset is already the shape that wants it:
  the figure alone, no microphone, speaking only what the host pushes — and
  until this lands there is nothing for the host to push with. **Home
  Assistant is a host with things to say**: a door left open, a machine
  finished, somebody at the gate. A house that can only answer when spoken to
  is half of what people want from one.

## Progress log

Newest first.

### 2026-08-15 — the screensaver is still the product

Phase 3: what a wall display looks like. Screensaver profiles set centrally,
two settings on each device's row, and nothing in either that touches what this
server will answer — it is entirely canvas and presentation, which is the whole
reason it was split from phase 2.

- **The numbers are central, not per device.** A deployment has a handful of
  *kinds* of place — a hallway, a bedroom, a shop floor — not one setting per
  screen, so a profile is a name and three numbers and a device names one by
  **id**. Change *night* once and every screen using it changes together; the
  alternative is twelve rows quietly drifting out of step with each other and
  nothing on screen saying which had. By id and not by name, so renaming a
  profile cannot orphan a screen, and clean_savers re-mints a duplicate id
  because two rows claiming one is a row nobody can point at.
- **One tick reveals the rest.** Most rows in a real deployment are a laptop or
  a phone. *On a wall* is the gate, and while it is off the two settings under
  it are stored and not applied — untick, and the screen is an ordinary page;
  tick it again and what was chosen is still there. Three controls that do not
  apply, on every one of fifty rows, is a register nobody reads.
- **Voice only stayed per device, deliberately.** It and the screensaver are
  separate axes: a wall screen can be voice only without ever drifting, and a
  shared television can drift while still showing its transcript. Folding one
  into the other would have made a profile a thing you cannot reuse.
- **A display is never told the list.** `wall_of` resolves the profile server
  side and hands over three numbers. The list of names is a description of a
  building — *ward*, *shop floor*, *back office* — and no screen has any use
  for the names of places it is not in.
- **Named and gone is off on a screen and an error in the panel**, and the two
  are not inconsistent. A screen has to fail quiet, or deleting a profile
  leaves tablets drifting to numbers nobody can find to change; a person
  pressing SAVE has to be told, or a panel left open overnight silently sets a
  device to a profile that no longer exists. Deleting also clears the id from
  every device that named it, the same way deleting a display clears it from
  every endpoint.
- **It does not take the rest of the bar with it.** The first cut hid `#bar`
  entirely, which reads correctly — *the geometry alone* — and would have made
  every voice-only display permanently deaf: a browser will not open a
  microphone without somebody asking it to, and TALK is the only thing that
  asks. Voice only means no text, not no controls.
- **Scale down, then drift.** Drawn full bleed there is nowhere to go and
  translating only clips the edges. The travel is *exactly* the margin the
  shrink bought — `(1 - scale) / 2` of the frame — so the figure reaches the
  edge of the panel and never crosses it. Verified over eight simulated hours:
  peak offset equals the available margin to four decimal places.
- **Two sines that do not divide into each other**, rather than a rectangle
  bouncing between four corners. It covers more of the panel over a night and is
  calmer to share a room with, and the clock behind it never resets — so two
  nights running do not light the same pixels in the same order.
- **The margin collapsing IS the ease back to the centre.** The drift is the
  sine times that margin, and the margin is a function of the same smoothstep
  the scale is. One number eases and the figure returns to the middle at full
  size with nothing animating it there. Six seconds in, so nobody catches it
  starting; under half a second out, so somebody who just touched the screen
  believes it answered them.
- **The dim is black over the finished frame**, not a scaled palette. It is the
  panel's light output that burns in and that is too bright at two in the
  morning, so what has to fall is absolute light — on a pale palette as much as
  a dark one. Capped below 100: a screen dimmed the whole way is a screen
  switched off, and you cannot see that one is still working.
- **The milk wash travels with the figure.** It is drawn from a fixed point in
  the frame, so left alone it would have been the one stationary bright region
  left on the panel — the exact thing the drift exists to prevent.
- **Idle is read off `Drive.phase`, not off the wake word.** A display with no
  wake word at all still thinks and still speaks, and that path never touches
  `Wake`. Every path that keeps a display awake does come through `Wake.touch`,
  though, which is why that is the single place the wake word ends the drift.
- **Off is the default, on every device.** Same rule that made `ANY DISPLAY` the
  default on a route: an upgrade that quietly started moving every screen in a
  building would be this phase deciding something nobody asked it to.
- **PREVIEW sits on the profile, not on the device.** What a scale and a dim
  actually look like is a property of the profile, and the profile is where
  somebody is choosing them. It drives the real preview with unsaved values,
  because nobody picks either number by reading it, and nobody should stand in
  front of a screen waiting out three minutes of idle to find out.
- **The panel says none of this out loud.** Every word of explanation is behind
  the `?` on its section, where the rest of the panel's prose already lives —
  the first cut printed four paragraphs into every device row, which is exactly
  the habit that rule exists to stop. What stays visible in a row is the
  controls and whatever the server is saying right now.
- **A new admin route is not admin-only because it calls `_require("admin")`.**
  `/displays/wall` did, and answered **401** on the display listeners where
  every one of its siblings answers **404** — which is the route confirming it
  exists on a listener it is supposed to be absent from. The gate is a
  hand-maintained list of paths, and a list is a thing somebody forgets. Named
  it, then made the list a belt and `/displays/` a prefix rule underneath it, so
  the next route added is covered whether anybody remembers or not. `/display/`
  singular — how a display gets its token — is one letter and a whole boundary
  away, and untouched.
- **Two CSS rules of equal specificity, and the later one wins.** The
  screensaver's rules sat with the rest of the wall rules near the top of the
  sheet, above `body[data-request] #request`. Both are one id, one attribute and
  one element, so source order decided it and an unanswered request stayed lit
  through the entire drift — the one stationary bright rectangle actually worth
  moving. They are now last in the sheet, with a comment saying why they are
  not where they look like they belong.
- **Proven in a browser, not yet on a panel.** The geometry is verified — the
  travel equals the margin to four decimal places over eight simulated hours,
  and the renderer a wall runs is the same file a tab runs, so there is no
  second implementation that could differ. What no browser can answer is
  whether 70% and dim 45% are the right *kind* of numbers seen from three
  metres in a dim hallway, and whether six seconds of ease-in is short enough
  to miss and long enough not to startle. Those are judgements about a room.
  The third thing a panel would settle — whether the burn-in is actually
  prevented — takes months and cannot be tested at all, which is why the design
  leans on the two mechanisms known to work rather than on measuring one.
- **What it does not do is push to a screen already on the wall.** A device
  waiting on a decision polls every twenty seconds and takes these immediately;
  one that is working has nothing left to ask about and takes them on its next
  load. Making a working screen poll for a setting that changes twice a year is
  the wrong trade, and a display that keeps itself current across a restart is
  what phase 4 is for. The panel says which case a row is in rather than leaving
  it to be discovered.

### 2026-08-15 — a name for a set of them, and a panel that reads as one

Groups, and the tidying that came with using the thing for an hour.

- **Twelve ticks is not a permission model, it is data entry.** So a group is a
  name for a set of devices, made under ACCOUNTS and named wherever access is
  granted — today an endpoint's allow-list, and anything later that grants
  something can name them the same way. That is why they live in a file of
  their own rather than inside the thing that currently uses them.
- **Two kinds, and they do not mix**: people who asked to be here, and devices
  an admin created and sent a code to. Separate populations answering separate
  questions — *the physics department*, *the screens in the east wing* — and
  one list that could hold both would be a list nobody could describe. The kind
  is fixed once the group exists, because changing it would silently empty it.
- **Grants add up, and a group is not approval.** Named by a group and named on
  its own is reachable by both. Somebody in a group who was never approved, or
  whose grant has run out, is still refused: the group decides *which*
  endpoints, approval decides whether they reach anything at all.
- **One section became four**, because they are read at different times: the
  queue, the register of what is working, the guest settings, and the form
  builder. A to-do list and a register are not the same object, and three rows
  needing attention buried among fifty that do not is how a request sits
  unanswered for a week.
- **Each row collapses to its name**, one open at a time across both lists,
  which meant renaming had to move inside the row — an editable box in a header
  is one somebody clicks by accident while trying to look underneath it.
- **Your own account moved behind your own name**, out of a tab about
  everybody else's, and the accounts tab now survives a server with no sign-in
  because groups live on it and a group has nothing to do with signing in.
- **Two labels that read backwards.** The guest switch said CAN ASK / CANNOT
  ASK, which names the mechanism — and in those terms it was inverted, since
  *cannot ask* is the open setting where somebody walks straight into the
  default endpoint. It asks the question somebody came to answer now. And
  REISSUE was offered on a guest's row, where it would have killed their token
  and printed a code for them to type into their laptop; a guest coming back is
  a RENEWAL, and they are not the same button.
- **Every label starts with a capital**, which is a small thing that was wrong
  in seventy-eight places.

### 2026-08-15 — a code you type into the screen, and a device that can ask

Two ways in that the first build did not have, both driven by the same
observation: approving what turns up is the wrong shape when you *knew* the
device was coming, or when you cannot see it at all.

- **The constraint that designs the enrolment code is that it is typed** — on a
  television, with a remote. Nobody pastes onto a TV. So it is six characters,
  the whole address is what the panel shows, and six characters are safe only
  because of the four rules around them: one use, ten minutes, a back-off after
  five wrong guesses, and an alphabet with no character that can be misread
  into another. `O`/`0`, `I`/`1` and `l` are simply absent, so a misread
  character is not a different valid code, it is not a code at all.
- **Every answer from `/e/` is a redirect back to the display**, never a status
  code and a page of JSON. Somebody has just typed a URL into a television;
  what they need next is the screen, with a line on it saying what happened.
- **REISSUE points the same mechanism at a row that already exists** — a wiped
  browser, a replaced screen. The row is the *place*: its name and every
  endpoint that names it survive, and the device behind it is swapped. The live
  token dies on the button press rather than when the new code is used, because
  a place is one device and waiting would mean two of them holding it.
- **The case that drives the rest is an endpoint restricted because it costs.**
  A hosted model given to some people and not to everyone, where the person
  turning up is on a laptop in another building and nobody can walk over and
  read an id off their screen. So a device can ask, on a form the admin built —
  up to five fields, one of them a box big enough for a reason — and the
  answers are what the decision is made on. This server has no opinion about
  what a request should ask.
- **Approving is granting**: the endpoints are ticked in the same gesture,
  because an approval that grants nothing is a row that changed colour.
  Refusing carries two messages, one shown to them and one that never leaves
  the panel, plus whether that device may ask again — and it takes back
  anything a previous approval gave.
- **A grant that was asked for runs out; one an admin issued does not.** Expiry
  is read where the request is answered rather than at the door, so it lands
  cleanly mid-conversation: the turn in flight finishes and the next is
  refused. Asking again is one press against the same row, never a second
  device, and the row counts the renewals.
- **Whether anybody may ask at all is a setting with a precondition.** Off
  means straight in, so the default endpoint must be open to any display —
  enforced from both ends, because in one direction it holds until the next
  edit and then breaks silently, with guests reaching nothing and no error
  anywhere to say why.

### 2026-08-15 — a display is a place, and a place has to be let in

Phase 2. Two people in a room, one of them addressing the wall tablet, and
everybody else's microphone hearing it too — so a route can now be restricted
to the displays you have approved, and the enforcement is not in anybody's
browser settings.

- **A display earns a token by turning up.** Unguessable, server-issued on the
  first visit, `HttpOnly` so nothing on the page can read it or hand it to a
  page that asks. `?display=kitchen` remains a *name*: it says which place this
  is and proves nothing, which is why it was never enough on its own. The
  obvious attack answers itself — somebody who types a wall display's URL into
  their own phone is issued a **new** token, which nobody approved, and the
  kitchen tablet's token was never in the URL to copy.
- **The gate is in two places and they are not redundant.** The display drops
  the utterance, because that is where it can still be nobody's business; the
  server refuses at `/ask`, because the browser is not the one we shipped.
  Either alone is a hole: without the first a house command lands in a
  stranger's conversation and is paid for, and without the second the whole
  thing is a setting somebody can turn off.
- **The refusal is silent, and the mid-conversation case is the one that
  matters.** A display already awake passes everything it hears straight
  through, so the rule had to be *hearing a name this display may not use
  drops the utterance* — do not pass it on, do not switch to it, do not say
  anything about it out loud. Stated that way it also gives the behaviour you
  do want: where the display **is** allowed, that same name switches to it.
- **Which meant publishing the wake word of a route a display may not use.**
  That looks backwards and is not: recognising the house's name is the only
  way to drop it. Withheld, the word does not stay secret — the phone simply
  answers on the house's behalf. It buys a reader nothing anyway; saying it
  into an unapproved device is refused at the server, every time.
- **Restricting is opt-in, per route.** Every route was open to anything
  before this existed, so shipping "approval required everywhere" would have
  taken working installations off the air to enforce a rule on routes where it
  buys nothing. `ANY DISPLAY` is the default and the panel says so; a light
  switch is worth naming displays for, a general assistant usually is not.
- **Unapproved is a working state.** The appearance settings are public, so a
  newly hung tablet draws correctly the moment it is powered on and simply
  answers to nothing — with the reason, and its own id, on the status line.
  Right-looking and inert is a better first five minutes than wrong-looking and
  refused. It asks again every twenty seconds, so approving it from the panel
  is the whole of the commissioning.
- **Then a second way in, because approving-what-turns-up is the wrong shape
  when you knew the screen was coming.** Name it in the panel, tick its
  endpoints, and type `…/e/K7QP-4M` into the device once. The code is six
  characters because it is typed with a remote, and six characters are safe
  only because of the four rules around them — one use, ten minutes, a back-off
  after five wrong guesses, and an alphabet with nothing in it that can be
  misread into something else. REISSUE points the same mechanism at a row that
  already exists, for a wiped browser or a replaced screen: the name and the
  permissions stay, the device is swapped, and the old token dies on the button
  press rather than when the new code is used.
- **Then a third way, because the reason to restrict an endpoint is not always
  a room with microphones in it.** It is often what the endpoint *costs*: a
  hosted model some people get and others do not. There the person turning up
  is on a laptop in another building and nobody can walk over and read an id
  off their screen — so a device can ask, on a form the admin built, and the
  answers are what the decision is made on. Approving ticks the endpoints in
  the same gesture; refusing carries a message for them, a note for you, and
  whether they may ask again. A grant of that kind expires and is renewed with
  one press, because a guest is a lifecycle and a wall screen is not.
- **Deleting a display is the revocation**, and it takes the id out of every
  route's allow-list on the way — a permission naming a device that no longer
  exists is one nobody can see and nobody can withdraw. The same reasoning that
  clears a deleted route's fallthrough.
- **An embed is not a display.** Its rights came from its key, so it reaches
  what anything can reach and nothing that is restricted. Nor is the panel's
  live preview: that is an admin looking at a display, and it is allowed
  everything, because an admin can reach any endpoint from the panel anyway.

### 2026-08-15 — a real house, and what only a house could tell us

Phase 1b closed on *"turn off couch lamps"* → *"Turned off the light"*: a real
installation, a real token, a real light, addressed by name over a microphone.
Everything the stub proved held. What it could not have proved, and what the
house corrected in a morning:

- **The fallthrough fires on the wrong sentences.** Designed around
  `no_intent_match`; the built-in engine matches a sentence shape before it
  looks for a device, so a general question returns `no_valid_targets` and
  never reaches it. Left as it is, deliberately — see the note under the
  provider. The two wordings are the tell: *"I couldn't understand that"* falls
  through, *"I am not aware of any device called X"* does not.
- **The hang-up had to go**, one day after it was written. Its own entry below.
- **The display had no status line.** `micNote()` and `note()` had been
  writing to elements that exist only in the admin panel's preview, so every
  explanation a display could offer — what it heard, why it stayed asleep, why
  a backend call failed — was discarded at the one place somebody was standing.
  That is why two separate faults this morning both presented as *"it just
  stops responding"*. A line above the composer now carries them, and the
  refusal says what it heard: `asleep — heard "…", which names none of …`.
- **Timings that only a real box shows.** 4.4s to decode one sentence on
  `small.en`; 13–29s from local models with nothing resident in Ollama; a 7b
  that will not fit beside two Whisper models and Piper voices in 7.6GB, whose
  runner dies mid-request and surfaces as *"Remote end closed connection
  without response"*. The house itself answers in 90–200ms — it is the fastest
  thing in the chain by two orders of magnitude.

### 2026-08-15 — the house stopped hanging up

One day old, built from the API's own signal, and wrong the first time a real
house answered a real command.

- **`continue_conversation: false` closed the conversation, silently.** The
  reasoning: a completed command has nothing to follow, and *"Turned on the
  light. Goodbye."* is one sentence too many. What it produced: the display
  slept the instant the light came on, and the next sentence was dropped at the
  wake gate. Five in a row, in the log — transcribed, never asked, never in the
  transcript.
- **It reads as a lockup, not as sleep**, because nothing announced it and
  because every other endpoint stays awake for the window. The house became the
  one endpoint you cannot speak to twice, and the fix — say the wake word
  again — is not discoverable from silence.
- **The awake window already does this**, everywhere, identically. That is the
  whole argument: closing a few seconds earlier bought nothing that the timer
  does not already do, and cost the one property a voice interface cannot
  afford to lose — that it behaves the same way twice.
- **`true` needed nothing doing to it.** Staying awake is the default, so
  *"which room?" → "the kitchen"* worked without the flag being consulted at
  all — which is the tell that the flag was never load-bearing.
- **Kept: reading it.** The value is still parsed and still described in the
  adapter, with the reason it is ignored beside it. A signal you decided not
  to act on is worth more in the source than an absence somebody re-adds in a
  year.

### 2026-08-14 — the house is an endpoint

Roadmap phase 1b. Saying the house name switches a light on, and it took no
new mechanism to do it: Home Assistant's conversation API is text in and text
out, so it is a fourth provider beside `demo`, the OpenAI dialect and
Anthropic.

- **Two fields of the reply do more than carry words.** `conversation_id` is
  held for exactly the route binding and handed back each turn, which is what
  makes *"which room?" → "the kitchen"* land. `data.code` is what makes the
  fallthrough a branch rather than string-matching an apology.
- **A third was built and removed the next morning.** `continue_conversation`
  closed the conversation when false, which is right on paper and wrong in a
  room — see the entry below.
- **When the house recognises nothing, another endpoint answers** — in the
  house's own name and voice, so nobody is told they used the wrong word. One
  hop only, and never the target's own: a chain is a question travelling
  somewhere nobody chose, at a cost per link. The house's conversation id
  survives the hand-off, because the binding is still to the house.
- **Silence is how a failure sounds**, which is the difference between this
  adapter and a chat one. A command that quietly did nothing is
  indistinguishable from one that worked, so an unreachable house, a rejected
  token and an HA-side error are all spoken — naming the endpoint, never the
  reason, which stays on the screen rather than going into the air. An action
  that succeeds and says nothing is spoken as "Done."
- **"Sorry, I couldn't understand that" is a passing test.** The built-in
  intent engine matches sentences and a test sentence is not a command, so the
  round trip that proves the address, the token and the agent are all right is
  the one that reads like a failure. TEST now says so in as many words.
- **The house's logic belongs to the house.** No entity allow-list here, no
  system prompt, no reply limit, no context length: HA already gates what voice
  may touch no matter what talks to it, and a copy here would be a second
  weaker version of a control that already holds. Those fields hide themselves
  rather than sit on screen wired to nothing.
- **A panel that always sent the base URL back defeated a server-side guard.**
  Changing an endpoint's provider is supposed to drop its address and key —
  otherwise a hosted key goes to whatever is listening on the old URL, which
  is the failure that looks like success. The server refused to carry them
  across; the panel handed the old value back with every save, so the guard
  never fired. Cleared in the panel now, where it can be seen happening.
  Found while adding a third provider to the same switch.

### 2026-08-14 — the panel stopped being written for its implementer

The routing worked; the interface describing it did not. Reworked against
repeated, specific complaints, each of which turned out to be pointing at
something real.

- **Routes became endpoints, and each is one block.** A list plus three shared
  sections that repainted for whichever row was selected asked you to hold
  "which one am I editing" across three collapsed sections, and made a second
  endpoint feel like a mode rather than a thing. Each endpoint is now one
  block — its wake word and its connection together, saved together — headed
  with what you say and what it is wired to. Three of them in a column is its
  own answer to whether more than one is supported.
- **Its sections are separate boxes, not one long form.** Five of them, tiling
  rather than stacked, each summarising itself so the whole configuration
  reads off the closed headings: *"house" +2 more · exact*, *400 tokens · 8
  turns · 120s*. Opening one is for changing it, not for finding out what it
  says. The endpoint's actions run along the foot of its box.
- **The word `route` left the interface.** It means something else entirely to
  anyone who has configured a network, and the panel had two sections one
  letter apart. It survives in the document, the API paths and this file,
  where it accurately describes a name resolving to a destination. Code and
  interface are allowed their own vocabularies; pretending one word serves
  both is how a panel ends up written for the people who implemented it.
- **Three bugs behind one complaint.** ADD created the endpoint and left the
  only section holding its name collapsed — `focus()` on an element inside a
  hidden section does nothing, so there was nowhere to type, and editing a
  saved wake word looked impossible for the same reason. Any repaint tore the
  blocks down and rebuilt them, discarding work in progress. And a successful
  save never cleared "saving…", which reads as a hang.
- **One place means demo.** A display-wide DEMO / CONNECTED AI switch
  duplicated each endpoint's own `demo` provider *and silently overrode it* —
  you could point an endpoint at a real model and still get built-in replies,
  with the reason on a different tab. Gone; the endpoint decides. Testing an
  endpoint is the TEST in its own block, which goes through its own adapter,
  so it will test Home Assistant against Home Assistant with no change. What
  the old self-test really did was check the chain *around* the endpoints, so
  it moved to SPEECH as RUN CHECK, beside the microphone and voices.
- **Each tab commits itself.** One SAVE FOR EVERYONE across three tabs meant
  pressing it while looking at MOTION also published what had been left
  half-adjusted on LOOK. Each tab now saves only its own settings, which
  needed `{settings, merge}` on `/settings` — merging inside the write, so two
  admins cannot undo each other. Which tab owns which setting is learned from
  where the control sits, and anything the panel can change that no tab claims
  is called out in the row. That check immediately found one.

### 2026-08-14 — three names, three destinations

Roadmap phase 1a. One assistant configuration became a set of named ones, and
the assistant tab became a list rather than a form.

- **A route is a name that reaches a destination**, and it binds to the
  *conversation* rather than to the sentence — the follow-up goes where the
  first question went. Saying another route's name mid-conversation switches
  to it and **drops the conversation**: those words were addressed to
  somebody else, and forwarding them would pay for them twice.
- **Published in two halves, and one of them not at all.** Presentation and
  routing reach the browser because that is where matching happens; the
  adapter kind, base URL and key do not, at any tier. `public_routes()`
  enumerates what is published rather than what is withheld, so the next
  field added to a route is private by default.
- **Exact beats fuzzy, wherever each was found.** Without that rule a
  near-miss on the first route in the list steals an utterance that named the
  second one outright — the person said the right word and got the wrong
  assistant. It is the one thing in the matcher worth a test, and it has one.
- **Strictness belongs to the route**, because the same false-positive rate
  costs a few tokens on one and actuates hardware on the other. `hows` no
  longer reaches a strict `house`.
- **Per-route greeting and voice**, so a room with three of them can hear
  which answered rather than read it.
- **A per-route TEST**, replacing one that asked "does the assistant work".
  With several routes that stopped being a question with an answer, and a
  test quietly exercising the default while you looked at another route would
  be worse than none.
- **Upgrading is automatic and reversible.** `backend.json` becomes route one
  and keeps the wake word out of the shared settings, so the box answers to
  the same word afterwards as before. Both source documents stay on disk.
- **Three faults found by building this before the adapter**, which is the
  whole argument for splitting the phase: a route switched to Anthropic kept
  the local base URL *and* the previous key, so a hosted credential would have
  gone to a model on this network on an `x-api-key` header — failing in the
  one direction that looks like success. Disabling the default route left the
  default pointing at it, so the composer would have gone quiet. And the wake
  state readouts in the panel had never worked at all: the code that writes
  them runs in the display, where the elements do not exist. All three fixed.
- **The wake word left the SPEECH tab**, because with several routes the word
  is what picks between them and it belongs to the thing it picks. What is
  left there is the gate's behaviour, which is one thing for the whole
  display. LEARN went with it and now teaches one named route — it cannot
  save, so the words it captures come back up the preview channel into the
  panel's field, unsaved, for an admin to commit.

### 2026-08-13 — what it is reachable at, and what it takes to get in

- **Two settings, not one mode.** Binding and authentication are independent,
  and a single label covering both starts lying the moment somebody changes
  half of it. The panel shows the pair and states the arrangement underneath
  in the words it means.
- **A personal install exists.** Bound to loopback there is no certificate to
  make, no first-run password to fish out of a log, and the microphone works
  unprompted — `http://localhost` is already a secure origin, so the rule that
  kept the admin page off plain HTTP has nothing left to protect there.
- **Binding to one address** rather than every interface, chosen from the
  addresses the machine actually has. An address it does not have is a server
  that will not start, and it would take the admin page with it.
- **Beyond loopback with no sign-in is allowed and never quiet** — a banner in
  the panel before saving, a warning on save, a loud one at every startup, and
  a banner across the display itself. A machine set up this way on a network
  its owner controls may later join one they do not.
- **The plain listener redirects to HTTPS**, keeping bookmarks, kiosk URLs and
  QR codes alive with path and query intact. **307, not a permanent redirect**
  — the target is configuration an admin can change, and a cached permanent
  one would strand every browser that ever visited on a dead port.
- **Not built: the middle rung**, a single PIN for the whole display. It is
  identity's PIN machinery pointed at a display, so it lands there rather than
  twice. Present and disabled, and named specifically if the API is asked for
  it.

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
