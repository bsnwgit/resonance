# Speech in & out

## HTTPS is not optional

Browsers will not open a microphone on an insecure origin. Nothing in
Resonance can override that, because it is not Resonance's decision — it is
the browser refusing before any of our code runs.

So: **the display served over plain HTTP works, but has no microphone.** Give
people the HTTPS address. If the certificate is missing, the server says so at
startup and disables both HTTPS and the admin port.

Everything in this document that involves a microphone assumes a secure
origin.

## Speech out (TTS)

### Which engine

**NEURAL (server)** synthesises on the box. It sounds substantially better, it
is identical on every machine that connects, and it needs no support from the
viewer's browser. This is the one to use.

**BROWSER** uses whatever voices the viewer's own browser and operating system
provide. Its advantage is that it needs nothing installed on the server; its
disadvantage is that everybody hears something different, and some browsers
provide nothing at all.

Pick NEURAL unless it is unavailable.

### Voices and delivery

The voice list is populated from what is actually installed, so it reflects
the box rather than a catalogue. **speech rate** applies to both engines;
**pitch** only exists for BROWSER, because the neural voices do not expose it.

**TEST VOICE** speaks a sample. **DIAGNOSE** reports what the server and the
browser each think is available, which is the right first step when a voice
does not come out.

### What drives the figure while it speaks

| Setting | The figure follows |
|---|---|
| TOKEN | the arrival of words |
| TTS | the audio actually being spoken |
| BEEP | a synthetic tone |

**TTS** is the honest one — the shape matches the sound leaving the speaker.
TOKEN moves in time with words appearing rather than being heard, which is
useful if audio is muted. BEEP is for testing.

## Speech in (mic)

### How it decides you have finished

**PUSH TO TALK** — the viewer holds SPACE and releases to send. Explicit,
immune to background noise, and the right choice for a desk in a shared room.

**AUTO (voice detect)** — it decides when you have stopped. The right choice
for a wall display people walk up to.

**MIC ONLY (no transcript)** — the microphone drives the figure but nothing is
transcribed and nothing is sent. This is the setting for a display that is
there to be looked at, or for a space where recording speech would not be
appropriate.

### Accuracy

**FAST (base.en)** and **ACCURATE (small.en)** are two transcription models.
Accurate is noticeably better with accents, names, and technical words;
fast is quicker to return. Both run on the server — no audio leaves the box
for transcription.

If people report being misheard, change this before changing anything else.

### Levels

| Control | What it does |
|---|---|
| mic gain | input level |
| noise gate | how loud a sound must be to count as speech |
| end-of-speech wait | how long a pause ends the turn, in AUTO |

**CALIBRATE (stay quiet 2s)** measures the actual background noise in the room
and sets the gate from it. Use it rather than guessing — a gate set by ear in
a quiet office is wrong the moment the room fills up.

If AUTO cuts people off mid-sentence, raise **end-of-speech wait**. If it
never stops listening, the gate is too low.

### CLEAN and RAW

Two signal-processing profiles, and they genuinely conflict:

- **CLEAN** filters the input for the best possible recognition. Transcription
  improves; the figure moves less, because the processing has removed exactly
  the variation it was drawing.
- **RAW** leaves the signal alone. The figure is livelier and recognition is
  slightly worse.

Choose by what the display is for. A display people ask questions of wants
CLEAN. A display that mostly looks good in a foyer wants RAW.

## The wake gate

Without a wake word, an AUTO display responds to any speech near it —
including two people talking to each other. The wake gate is what makes it
usable in an occupied room.

**The words themselves are not here.** They belong to the routes, on the AI
tab: with several routes the word is what picks between them, so it belongs
to the thing it picks. LEARN, aliases and per-route greetings are all there
too. What is on this tab is the gate's behaviour, which is one thing for the
whole display however many routes it can reach.

| Mode | Behaviour |
|---|---|
| OFF | no gate; anything heard is a question, and goes to the default route |
| AUTO ONLY | the gate applies in AUTO, and is skipped in push-to-talk |
| ALWAYS | the gate applies in both modes |

**AUTO ONLY** is the sensible default: holding SPACE is already an explicit
statement that you are talking to it, so requiring a wake word as well is
friction for nothing.

**stays awake for** sets how long it keeps listening after being woken.
Activity extends it.

**greeting phrases** are the fallback for every route with no greeting of its
own. `{name}` is the wake word of whichever route was addressed, so one line
written here reads correctly whichever one answers.

## Sleep word

One word, shared by every route: there is one way out of a conversation
whichever one you are in. It ends the conversation deliberately rather than
waiting for the timeout, and **clears the conversation history**. Farewells
to answer with, aliases for near-misses, and the same three-times learning.

Also here: whether it says a farewell when it times out, or just goes quiet.
On a wall display in a quiet office, quiet is usually the better manners.
