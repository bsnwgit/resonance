# Routes, and connecting an assistant

Out of the box the display answers from built-in text. That is not a
placeholder to be rushed past — it is how you prove the whole chain works
before any model exists, and how you tell later whether a fault is the
front-end or the thing behind it. Keep it available.

**RUN SELF-TEST** walks every link — secure origin, settings store,
transcription, voices, microphone, recorder, routes, the route that would
answer, render-and-speak — and names whichever one is broken.

## What a route is

A **route** is a name that reaches a destination. Say its wake word and
everything after it goes there until the sleep word or the awake timer runs
out — so a follow-up needs no second address, which is the only tolerable
behaviour for speech.

A route carries:

| | |
|---|---|
| a name | what it is called, in the panel and in `{route}` |
| a wake word, and aliases | what somebody has to say to reach it |
| how strictly it matches | FUZZY or EXACT — see below |
| a greeting | optional; blank uses the shared phrases |
| a voice | optional; blank uses the shared voice |
| an adapter and its configuration | provider, base URL, model, key, prompt |

Every route has its own connection. Three routes can reach a local model, a
hosted one and something else entirely, with their own prompts, their own
context lengths and their own keys.

### The default

**Where anything with no name in front of it goes**: typed into the composer,
sent through an embed, or spoken while the wake gate is off. There is always
exactly one, marked DEFAULT in the list, and **MAKE DEFAULT** moves it. A
route that is not answering cannot be the default, and the server moves it
for you rather than leaving the composer wired to nothing.

### What of a route reaches a browser

Two thirds of one, and this is worth knowing before you name anything:

| | fields | who sees it |
|---|---|---|
| **presentation** | name, greeting, voice | anyone who can reach the port |
| **routing** | wake word, aliases, matching | the same, today |
| **connection** | provider, base URL, key, prompt | nobody, through any browser |

The wake words have to reach the browser because that is where the matching
happens. **The adapter kind does not, and is not published at any tier** —
nothing needs it, replies come back already labelled with the route that gave
them, and it is the one field that tells a reader what this box is wired to.
A display cannot tell you, because it does not know.

### FUZZY and EXACT

FUZZY wakes on near-misses: a transcriber mishears a short word constantly,
so a wake word that had to be spelled correctly would make waking a coin
flip. That is right for a route that answers questions.

EXACT is for a route that *does* things. The same false-positive rate costs a
few tokens on one route and actuates hardware on the other, so a route wired
to anything physical should match exactly.

An **exact hit always beats a fuzzy one**, wherever each was found. Without
that rule a near-miss on one route could steal an utterance that named
another one outright — the worst failure available here, because the person
said the right word and got the wrong assistant.

### Choosing wake words

Choose them **acoustically far apart**, not merely different. Differing
syllable counts, vowels and stress survive a noisy room; two names a letter
apart do not. Worth settling before a household learns them, because changing
one afterwards is its own small misery.

Two routes cannot share a word — including through an alias — and the panel
refuses it at the point of saving. Words that are merely *close* are not
checked yet.

**LEARN HOW I SAY IT** captures what the transcriber actually returns when
you say the word, three times, and adds those forms as aliases. It teaches
the route selected in the panel, and it needs the route to have been saved
first. The captured words appear in the aliases field unsaved — press **SAVE
ROUTE** to keep them.

### Testing one route

**TEST** asks *that route* one short question. With several routes this stops
being a convenience: "the assistant works" is no longer something that can be
true or false about this server as a whole, and a test that quietly exercised
the default while you were looking at another route would be worse than none.

## The three providers

### DEMO

Answers from the display's own built-in text. Nothing is sent anywhere, no key
is needed, and the system prompt is ignored. The connection fields hide
themselves, because a panel full of controls wired to nothing is worse than a
short panel.

### OPENAI-COMPATIBLE

A **dialect, not a vendor**. Ollama, OpenClaw, LM Studio and vLLM all speak
it, so one adapter reaches all of them and the only difference between them is
the base URL — which is what the preset buttons fill in.

| Preset | Base URL | Model field |
|---|---|---|
| OLLAMA | `http://127.0.0.1:11434/v1` | the tag, e.g. `qwen2.5:3b` |
| OPENCLAW | `http://127.0.0.1:18789/v1` | an agent id, e.g. `openclaw:main` |
| LM STUDIO | `http://127.0.0.1:1234/v1` | whatever is loaded |
| OPENAI | `https://api.openai.com/v1` | e.g. `gpt-4o-mini` |

Pick a preset, set the model, save. A local model needs no API key.

Under the model field you may see **installed there:** followed by a list.
That is an Ollama trick — the panel asks the same host what it actually has,
so a model name is chosen rather than typed from memory and subtly wrong.
Nothing else answers that path, so the line stays empty for other providers.

### ANTHROPIC

Its own choice rather than another preset, because the wire format genuinely
differs: the key rides an `x-api-key` header rather than `Authorization:
Bearer`, a version header is required, the system prompt is a top-level field
rather than a message in the list, a reply limit is mandatory, and the answer
arrives as a list of content blocks rather than one string.

There is exactly one endpoint — `https://api.anthropic.com` — so it has no
preset to choose; selecting the provider fills it in. A key is **required**,
and saving without one is refused at the point of saving rather than
discovered later by whoever is standing in front of the screen.

## Fields that do not apply everywhere

**temperature is not sent to Anthropic at all.** The current Claude models
reject the sampling parameters outright, and older ones stop at 1.0 where this
panel's slider goes to 1.5. A control that quietly breaks half the models is
worse than no control, so the slider hides itself and the system prompt does
the steering instead.

**keep model loaded** is an Ollama extension. Without it the model unloads
after a few minutes idle and the next question waits for it to load again —
measured at 28 seconds for a 7b on the reference hardware. It means nothing to
a hosted provider and is never sent to Anthropic.

## The other settings

| Control | What it does |
|---|---|
| reply limit (tokens) | ceiling on the length of an answer |
| temperature | how varied the wording is |
| turns of context | how much of the conversation is sent back |
| timeout | how long to wait before giving up |

**turns of context** is the one worth thinking about. At zero, every question
is answered cold and "what about the other one?" is meaningless. Higher costs
more per question and eventually confuses a small model. Around eight is a
reasonable place to start.

**timeout** needs to be generous. A cold local model can take half a minute
just to load before it begins answering, and a timeout tuned to a warm model
will look like a dead server every morning.

## Where the API key lives

Never in `settings.json`. That document is world-readable by design — every
viewer's browser fetches it to build the interface — so a key placed there
would be handed to anyone who opened the page.

Keys live in `routes.json`, admin-only, mode 600, one per route. A key is
**never returned to a browser**: the field shows whether one is stored, not
what it is. Leaving the field blank keeps the stored key; **FORGET KEY**
clears it for the selected route.

**Changing a route's provider drops its key and its base URL**, unless you
supply new ones in the same save. Carrying one provider's endpoint into
another would send an Anthropic key to whatever happens to be listening on
the old URL, which is worse than an error because it looks like it worked.

An install that predates routes is migrated on first start: `backend.json`
becomes route one, and it keeps the wake word the shared settings had, so the
box answers to the same word afterwards as before. `backend.json` is left on
disk rather than deleted — an upgrade that removes the file it read from has
no way back if the migration was wrong.

## The system prompt

What this route's assistant is told before every question, and it matters
more here than in a chat box: the reply is **read aloud**. Markdown, bullets,
headings and emoji are all noise when spoken, and a bulleted answer read out
is unusable.

Each route has its own. A house and a general assistant want different
instructions, and one prompt covering both is a compromise neither needs.

The shipped prompt asks for one or two sentences of plain prose. **RESET**
returns to it. That single instruction is the largest difference between a
voice interface and a text one — change it carefully, and listen to the result
rather than reading it.

## What the model does and does not know

Worth understanding before you field complaints about it, because two of these
look like bugs and only one is.

**The date is handled.** A model's sense of "now" is frozen at its training
cutoff, so asked the date it will answer confidently and wrongly — a local 3b
will say 2023 without hedging. The server therefore states the current date
and time in the system prompt on **every** request, so this question is
answered correctly. Nothing to configure.

The time is the *display's* local time, not the server's. The browser reports
its timezone with each question and the server formats accordingly, which
matters whenever the box runs on UTC and the screen does not: at eight in the
evening in New York the server already thinks it is tomorrow. If the browser
does not report a zone, the server's own clock is used.

**Recency is not handled and cannot be.** The model has no internet. Ask it
for today's news, a current price, or anything after its training data ends
and the correct behaviour is to say it does not know — which the system prompt
explicitly asks for. A model that answers those questions confidently is
giving you stale training data dressed as fact, which is worse than a refusal.

If you need live information, that is a search or tool integration, not a
setting. It does not exist yet.

**Local knowledge varies enormously with model size.** A 1.5b will get
straightforward facts wrong in ways a 7b will not. If answers are thin rather
than slow, the model is too small before anything else is at fault.

## Testing and diagnosing

**TEST** asks the selected route's model one short question and reports the
reply and the round trip in milliseconds. It uses that route's own
connection, so a pass here means a viewer who says that route's name will get
an answer too.

Failures report the provider's own message rather than a bare status code,
because "404" tells you nothing about which field is wrong. On the *display*
they are reported against the route's name rather than the adapter — a
display says these out loud, and "openai returned 401" tells the person
standing in front of it nothing they can act on while telling everyone in
earshot what the box is wired to.

| Symptom | Usually |
|---|---|
| "cannot reach ..." | wrong base URL or port, or the model server is not running |
| "404 ... model" | model name does not match what is installed |
| "401" / "invalid api key" | key wrong, or missing for a hosted provider |
| "timed out after ..." | cold model; raise the timeout |
| still on DEMO | that route's provider is DEMO — nothing was asked of a model |
| the wrong route answered | a fuzzy match; set the other route to EXACT, or move the words further apart |
| nothing woke at all | the word is not on any route, or the gate is off — SPEECH tab |
| a confidently wrong answer | the model, not the plumbing — see above |

## Choosing a model

Round trips measured on the reference box, cold then warm:

| Model | Cold | Warm |
|---|---|---|
| qwen2.5:1.5b | 1.4s | 1.6s |
| qwen2.5:3b | 10.1s | 3.6s |
| qwen2.5:7b | 28.2s | 11.1s |

For a voice front-end the wait *is* the product. A smaller model answering in
under two seconds generally feels better to talk to than a larger one that is
cleverer but leaves people staring at a still figure. Set **keep model
loaded** so the first question of the day is not the slow one.
