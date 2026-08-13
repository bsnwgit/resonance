# Connecting an assistant

Out of the box the display answers from built-in text. That is not a
placeholder to be rushed past — it is how you prove the whole chain works
before any model exists, and how you tell later whether a fault is the
front-end or the thing behind it. Keep it available.

**RUN SELF-TEST** walks every link — secure origin, settings store,
transcription, voices, microphone, recorder, backend, render-and-speak — and
names whichever one is broken.

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

It lives in `backend.json`, admin-only, mode 600. It is **never returned to a
browser**: the field shows whether one is stored, not what it is. Leaving the
field blank keeps the stored key; **FORGET KEY** clears it.

## The system prompt

What the assistant is told before every question, and it matters more here
than in a chat box: the reply is **read aloud**. Markdown, bullets, headings
and emoji are all noise when spoken, and a bulleted answer read out is
unusable.

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

**TEST** asks the configured model one short question and reports the reply
and the round trip in milliseconds. It goes through exactly the same path the
display uses, so a pass here means a viewer will get an answer too.

Failures report the provider's own message rather than a bare status code,
because "404" tells you nothing about which field is wrong.

| Symptom | Usually |
|---|---|
| "cannot reach ..." | wrong base URL or port, or the model server is not running |
| "404 ... model" | model name does not match what is installed |
| "401" / "invalid api key" | key wrong, or missing for a hosted provider |
| "timed out after ..." | cold model; raise the timeout |
| still on DEMO | the provider is still DEMO — nothing was asked of a model |
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
