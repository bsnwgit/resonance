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

## Wake word

Without a wake word, an AUTO display responds to any speech near it —
including two people talking to each other. The wake word is what makes it
usable in an occupied room.

**The words themselves are not here.** Each belongs to an assistant, on the AI
tab: with more than one, the word is what picks between them, so it belongs to
the thing it picks. LEARN, the alternative spellings and each one's own
greeting are all there too. What is on this tab is the gate's behaviour, which
is one thing for the whole display however many assistants it can reach.

| Mode | Behaviour |
|---|---|
| OFF | no gate; anything heard is a question, and goes to the one marked DEFAULT |
| AUTO ONLY | the gate applies in AUTO, and is skipped in push-to-talk |
| ALWAYS | the gate applies in both modes |

**AUTO ONLY** is the sensible default: holding SPACE is already an explicit
statement that you are talking to it, so requiring a wake word as well is
friction for nothing.

**stays awake for** sets how long it keeps listening after being woken.
Activity extends it.

**greeting phrases** are the fallback for every assistant with no greeting of
its own. `{name}` is the word that was said to reach whoever answered, so one line
written here reads correctly whichever one answers.
## Sleep word

One word, shared by all of them: there is one way out of a conversation
whichever assistant you are in it with. It ends the conversation deliberately rather than
waiting for the timeout, and **clears the conversation history**. Farewells
to answer with, aliases for near-misses, and the same three-times learning.

Also here: whether it says a farewell when it times out, or just goes quiet.
On a wall display in a quiet office, quiet is usually the better manners.


## Speech in (mic, STT)

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

**transcription model (STT)** is a dropdown of every model this server will
accept, with what each costs beside it. All of them run on the server — no
audio leaves the box for transcription, whichever you pick.

The list is grouped:

- **English only** — the `.en` models. Better at English than the multilingual
  model of the same size, and smaller.
- **every language** — pick one of these and it will transcribe languages
  other than English. That is the only thing that makes it do so.

Sizes run from `tiny.en` at ~40MB to `large-v3` at ~1.6GB. `small.en` is the
default and the right one for a modest box; `distil-small.en` gets close to it
at nearly the speed of `base.en`; `large-v3-turbo` is most of the best model
at several times its speed, on hardware that can hold it. Nothing here assumes
what you are running it on, which is why the whole list is offered.

**A model not already on disk is downloaded the first time somebody speaks
after you choose it** — up to 1.6GB, inside that request, from a machine that
may have no route to the internet. Choose it when nobody is waiting in front
of the display, then say something to it yourself to pay the download. The
panel lists which models are resident right now.

If people report being misheard, change this before changing anything else.

**The choice interacts with THE EXACT WORD.** An assistant set to match only
its exact name refuses `"Magnolia's"` where a CLOSE ENOUGH one forgives it — so
a smaller model buys speed at the cost of the occasional wake word that does
not land, and the assistants most likely to be set to exact are the ones that
switch things on. Measured on the reference box: `small.en` took 4.4s to decode
one sentence, which is felt on every turn. If you want both, take the faster
model and press **LEARN HOW I SAY IT** on the strict assistant — it captures the
spellings that model actually returns for you and adds them as alternatives.

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

## What the display tells you

A dim line sits above the input box on the display, and it is where every
answer to *"why did nothing happen?"* now appears:

| It says | It means |
|---|---|
| `transcribing…` | the recording is with the server |
| `heard you · woken · 340ms decode, 512ms round trip` | it acted on what you said, and how long each stage took |
| `nothing recognised — try speaking a little louder` | the recording came back empty; nothing to match against |
| `asleep — that named none of "house" or "ada"` | somebody said something near it and no assistant was named. **It does not say what was said** |
| `"house" is not for this display — ignored` | somebody addressed an assistant this display is not allowed to use. Nothing was sent, nothing was answered, and the conversation it was already having was left alone |
| `waiting to be approved — kitchen (d4a19…)` | this display has never been approved. It renders correctly and answers to nothing; the id is what an administrator looks for in DISPLAYS |
| `enrolled as kitchen wall — say "house" or "ada"` | an enrolment code was just typed into this screen and it worked |
| `that code was not recognised — check it and try again` | a mistyped or already-used enrolment code. Case and dashes do not matter, so it is a wrong character rather than a wrong format |
| `that code had expired — ask for a new one` | the code was real but older than ten minutes. REISSUE in the panel gives another |
| `approved as kitchen — say "house" or "ada"` | somebody just approved it, and it noticed on its own |
| `refused: this display may not use house` | a question typed into the box went to an assistant this display is not allowed to use |
| `backend: …` | why an endpoint failed, in full, where the spoken reply gives only the name |

**It never shows what it overheard.** While it is asleep the line says that
something was said and that no assistant was named — never the words. A display
in an occupied room that printed everything within earshot would be putting
other people's conversations on a wall, which is exactly what the wake word
exists to prevent: answering an unaddressed sentence and publishing one are the
same breach. Nothing is written to the line until the gate has decided the
display was being spoken to.

The cost is real and worth knowing: a wake word that is being *misheard* used
to be diagnosable from that line. It is not any more. **LEARN HOW I SAY IT** is
the tool for that instead — it asks before it listens, captures three
deliberate attempts, and adds the spellings the transcriber actually returns.

**A refusal is red.** The line carries both *here is what happened* and *here
is why nothing happened* — what it heard and how long it took, against a wake
word it will not act on, a microphone that would not open, a code that was
wrong. On a screen read from across a room those two need to be tellable apart
without reading the words, so anything reporting a refusal or a failure is in
red and everything else is not.

**It exists because the display used to discard all of it.** Those messages
were written to elements that only existed inside the admin panel's preview,
so a display that mis-heard you, went to sleep or could not reach its endpoint
looked identical from the front — silent. Two separate faults presented as *"it
just stops responding"* before this line existed.

The quoted text is the useful part. A wake word that is *nearly* right —
`"Magnolia's"` for `magnolia` — is refused outright on an assistant set to THE
EXACT WORD, and the line is the only place that distinguishes that from never
having been heard.

Turning the transcript off (**TEXT**) hides this line too: a display showing
only the figure is a deliberate choice, and a running commentary under it is
not what that choice asked for.

## Commissioning check

**RUN CHECK** walks every link in the chain and names whichever is broken:
secure origin, the settings store, transcription, the voice service, the
microphone, the recorder, the endpoints, and whether the default endpoint
answers and can be rendered and spoken.

It lives here rather than on the AI tab because most of what it checks is on
this one. It is not an AI test — each endpoint has its own **TEST**, which
puts a question to that endpoint's own service.

