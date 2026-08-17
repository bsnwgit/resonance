# Assistants

Out of the box the display answers from built-in text. That is not a
placeholder to be rushed past — it is how you prove the whole chain works
before any model exists, and how you tell later whether a fault is the
front-end or the thing behind it. Keep it available.

Set an endpoint's service to **DEMO** and it answers from built-in text,
reaching nothing. There is no display-wide demo switch — whether an endpoint
is pretending is a property of that endpoint, and two places meaning the same
thing is a setting nobody can reason about.

**RUN CHECK**, on the SPEECH tab, walks the chain around the endpoints —
secure origin, settings store, transcription, voices, microphone, recorder,
and whether the default endpoint answers and can be spoken. It is not an AI
test: that is the **TEST** inside each endpoint's own block.

## One display, several assistants

Each assistant has **a name you say out loud**. Say it and everything after it
goes to that one, until you say the sleep word or it times out — so a
follow-up needs no second address, which is the only tolerable behaviour for
speech. Say a *different* name mid-conversation and you switch to that one
instead.

Each names **a model profile** — the service, address, model and key, kept as
a named set under PROFILES ▸ MODELS — and adds its own instructions. Its
greeting and its voice come from the speech profile it names rather than from
fields of its own, so a room with more than one can still hear which replied. Two endpoints may name the same profile: one connection, two
names to say, two sets of instructions.

**One row per endpoint**, and the row is the whole of it: the speech profile
that carries the word reaching it, the model profile it speaks to, and the
instructions it speaks under, saved together by the SAVE inside it. **ADD
INSTANCE** at the foot of the tab makes another and opens it; each row carries
its own TEST, MAKE DEFAULT, SWITCH OFF and DELETE. The key is not here — it
belongs to the profile, and is edited once for every endpoint using it.

Every block's heading says what you say to reach it and what it is wired to —
`say "house" -> house-agent` — so you can find the right one without opening
three of them.

### The one marked default

**Where anything with no name in front of it goes**: typed into the box at the
bottom of the display, sent by an embedded copy, or spoken while the wake word
is switched off. There is always exactly one, and **MAKE DEFAULT** moves it. One that is switched off cannot hold it, and the server moves it for you
rather than leaving the display with nowhere to send anything.

### What a display is told, and what it never is

| | fields | who sees it |
|---|---|---|
| what it looks like | name, greeting, voice | anyone who can reach the port |
| what it answers to | the words, and how closely they must match | any display that has been issued a token |
| **what it is connected to** | service, address, key or house token, conversation agent, instructions, where it falls through to | **nobody, through any browser** |

The words have to reach the browser because that is where the listening
happens. **What it is connected to does not, at any tier** — nothing needs it,
replies come back already labelled with whoever gave them, and it is the one
field that would tell a reader what this machine is wired to. A display cannot
tell anyone, because it is never sent it.

A display is told the words of **every** endpoint, including ones it is not
allowed to use. That is what lets it stay quiet when somebody addresses
another device: it has to recognise the house's name in order to ignore a
command meant for the house rather than passing it into its own conversation.

### Who may use it

Two reasons to restrict an endpoint.

**A room with several microphones in it.** Two people, one of them addressing
the wall screen, and every other device in earshot hearing it too. Push-to-talk
on a phone is the correct setting and is not a control, because nothing makes
anybody set it — so the rule lives on the endpoint instead.

**What an endpoint costs.** A hosted model is worth giving to some devices and
not to every one that can reach the port, and this is where that is decided.

**ANY DISPLAY** is the default, and is what every endpoint did before displays
existed.

**ONLY THESE** names the devices that may reach it — a wall screen, a TV, a
laptop, a phone. Anything else that hears its wake word drops the utterance: no
answer, nothing passed to whatever it was already talking to, nothing said out
loud, no matter how that browser is configured.

Devices enrol themselves by loading the page and are approved under ACCESS;
one that has not been approved yet can be ticked here, and is refused until it
is. Restricting the **default** endpoint is worth a moment's thought: anything
typed into the composer with no name in front of it goes there, so displays
outside the list get nothing back when somebody types.

### The instance name and the wake word are two different things

The **instance name** labels the endpoint in the panel, in the log and in
`{assistant}`; it is never spoken and never matched against. The **wake word**
is what somebody actually says. An endpoint called *Kitchen Lights* is a
perfectly good label and a terrible thing to say out loud.

**The word is not on this tab.** It lives in the speech profile the endpoint
names, on SPEECH ▸ WAKE WORD, along with the spellings it will also accept and
whether matching is forgiving. One endpoint per speech profile is enforced, so
each endpoint still has a word of its own.

### FUZZY and EXACT

FUZZY forgives a mishearing: a transcriber gets short words wrong constantly,
so a name that had to come back spelled correctly would make waking a coin
flip. That is what you want from something that answers questions.

EXACT is for one that *does* things. The same near-miss costs you a few tokens
on one and switches on the lights on the other.

**An exact hit always wins**, wherever it was found. Without that rule a
near-miss on one name could steal an utterance that said another one outright
— the worst failure available here, because the person said the right word and
got the wrong assistant.

### Choosing the words

Choose names that sound **far apart**, not merely different. Differing
syllable counts, vowels and stress survive a noisy room; two names one letter
apart do not. Worth settling before a household learns them, because changing
one afterwards is its own small misery.

Two assistants sharing a word is a display that cannot tell them apart, and it
is **no longer refused at the point of saving** — the words moved to speech
profiles, and the check compared the vestigial copy every endpoint still
carries, which refused every save. What prevents the clash instead is that one
speech profile may be named by only one endpoint. Two *profiles* given the
same word are not caught. Words that merely *sound* close are not checked
either.

**LEARN HOW I SAY IT** captures what the transcriber actually returns when you
say the word, three times, and adds those forms to *Also accept*. It is on the
SPEECH tab beside the word it teaches, not in an endpoint's block. The
captured words land in the field unsaved — save the profile to keep them.

### TEST

Puts one short question to the endpoint whose block it is in, through that
endpoint's own service — so DEMO is tested against the built-in replies and a
connected service against itself, with nothing to keep in step. With several of
them this stops being a convenience: "the assistant works" is no longer
something that can be true or false about this server as a whole, and a test
that quietly exercised a different one would be worse than none.

**On a Home Assistant endpoint, "Sorry, I couldn't understand that" is a
pass.** The built-in agent matches commands, and the test question is not one —
so the reply that proves the address, the token and the agent are all correct
is the one that sounds like a failure. TEST spells that out underneath. The
test question is never a command: a TEST button that switches something on is
one nobody presses twice. To check that the right devices are exposed, ask it
to switch something on out loud.

**TEST does not follow a fallthrough either**, and says so when one is set: it
is checking this endpoint's own connection, and a pass borrowed from a
different endpoint would tell you nothing about this one. The line underneath
names where the same question would have gone in use.

## Model profiles

A profile is one connection under a name: **PROFILES ▸ MODELS**, one row each,
the same caret and the same one-open-at-a-time as every other list. **ADD A PROFILE** makes one; SAVE commits the row; MAKE DEFAULT nominates the
one an endpoint naming nothing gets.

Editing a profile changes what every endpoint naming it reaches, in one place
— which is the point. A key typed once serves all of them, and rotating it is
one edit rather than six.

The four kinds below are what a profile can be.

## Network profiles

A port of this server's own, under a name: **PROFILES ▸ NETWORK**. This is
where the app's networking lives — the only port configured under ADMIN
SETTINGS is the admin portal's.

**A profile is an address and a port**, not just a port. The picker offers the
addresses this machine actually has, each with the interface carrying it, and
**ANY** — every interface — which is where every profile was before this
existed. Offered rather than typed, for the same reason the server's own
binding is: an address this machine does not have is a listener that will not
start, and nothing about a box you can type into would tell you so.

Two profiles may share a port when they answer on different addresses, because
the machine can carry that. ANY collides with everything on its port, which is
what ANY means.

**A profile never reaches further than the server itself.** With ADMIN SETTINGS
▸ IP Address set to one address — or to this machine only — that address wins
for every profile, whatever they name. A setting that says *this machine only*
has to mean it, and a profile able to bind a LAN address anyway would be that
setting quietly not applying.

**The port is checked before anything is allowed to use it.** Saving tries the
port on the address chosen; on ANY it tries every address the machine has, and
allows the save if even one can carry it — a port in use on all of them is
refused, with the addresses named. This happens at the point of saving rather
than at the next restart, when the fix would be editing JSON on the box by
hand.

**A socket this server is already holding does not count as taken**, and only
the same socket. The question a save has to answer is not *is this port free*
but *will it be free once the server has restarted* — so moving a profile from
ANY onto one of its own addresses, or off an address back onto ANY, is allowed,
while the same port held by **another process** on the address you are moving
to is refused. Without that distinction a profile could not be moved at all
without first stopping the server it is running on.

**Only a profile that moved is checked.** The panel sends every profile on
every save, and a row whose address and ports are unchanged is either already
running or already known to be broken — so it is not allowed to refuse an edit
to a different row.

**An endpoint belongs to exactly one network profile**, and answers there and
nowhere else. One that names none answers on whichever profile is nominated
**DEFAULT**, which is where they all were before this existed: an upgrade turns
the display ports into a profile called *Display*, shared, and nothing moves
until you move it.

**Shared or not** is the whole difference between the two things you might
want:

- **Shared** — several endpoints on one port, told apart by wake word. This is
  how the display port has always worked, and it is what an ordinary
  deployment wants.
- **Not shared** — a port that *is* one assistant. A browser opening it gets
  the ordinary interface built from that endpoint's own settings, with no
  other endpoint offered and nothing to address by name. A second endpoint
  claiming it is refused rather than silently never reached.

| Field | What it does |
|---|---|
| Port | 1024–65535. Refused if it is the admin portal's, or one another profile already has. |
| Plain HTTP, redirected here | Optional. A plain port that 307s to this one, which is what 9700 has always done for 9701. Leave it empty for none. |
| More than one endpoint | Whether this port is shared. |
| The port is the grant | **YES** turns the request form off on that port alone — a device that can reach it uses the endpoints straight away, approved or not. **NO** applies the ordinary rules. |

**The default profile is always shared.** It carries every endpoint that names
no profile, so one that could only take a single endpoint would strand the
rest. The panel will not offer MAKE DEFAULT on an unshared profile, and the
server refuses the save either way.

A question arriving on a port for an endpoint that port does not carry is
given the port's own default rather than refused — the same thing the shared
port has always done with an endpoint switched off since the page loaded.

**The port is the grant** is a statement about your network rather than about
this server. It is right when the port is on a VLAN only the intended devices
are on, and wrong the moment it is not. It applies to that port only: the same
device arriving on the shared display port is treated exactly as before.

TLS is the same certificate the display port uses — the microphone needs a
secure context, and a second certificate for the same machine would be one
more thing to renew.

**Ports are bound when the server starts.** Adding a profile, changing a port
or pointing a different endpoint at one takes a restart, the same as the ports
on ADMIN SETTINGS: a listening socket is not something to open and close under
a mouse. A port that turns out to be taken is reported and skipped rather than
stopping the server — everything else still answers, and you need the panel in
order to fix it.

## The four providers

### DEMO

Answers from the display's own built-in text. Nothing is sent anywhere, no key
is needed, and the instructions are ignored. The connection fields hide
themselves, because a panel full of controls wired to nothing is worse than a
short panel.

### OPENAI-COMPATIBLE

A **dialect, not a vendor**. Ollama, OpenClaw, LM Studio and vLLM all speak
it, so one adapter reaches all of them and the only difference between them is
the base URL.

| Server | Base URL | Model field |
|---|---|---|
| Ollama | `http://127.0.0.1:11434/v1` | the tag, e.g. `qwen2.5:3b` |
| OpenClaw | `http://127.0.0.1:18789/v1` | an agent id, e.g. `openclaw:main` |
| LM Studio | `http://127.0.0.1:1234/v1` | whatever is loaded |
| OpenAI | `https://api.openai.com/v1` | e.g. `gpt-4o-mini` |

Set the address and the model, save. A local model needs no API key.

### ANTHROPIC

Its own kind rather than another OpenAI-compatible address, because the
wire format genuinely
differs: the key rides an `x-api-key` header rather than `Authorization:
Bearer`, a version header is required, the system prompt is a top-level field
rather than a message in the list, a reply limit is mandatory, and the answer
arrives as a list of content blocks rather than one string.

There is exactly one endpoint — `https://api.anthropic.com` — so choosing the
provider fills the address in. A key is **required**,
and saving without one is refused at the point of saving rather than
discovered later by whoever is standing in front of the screen.

**Not yet tested against the live service.** This adapter is implemented from
the published wire format and exercised end to end against a server that
answers in it — which proves the request is well formed, not that the real
endpoint accepts every assumption in it. If you are the first to point one at
a real key, press TEST before trusting it in a room.

### HOME ASSISTANT

The house as an endpoint. Say its wake word and what follows goes to Home
Assistant's conversation agent, which answers in words the display reads out —
*"Turned on the kitchen light."*

Set up in three fields:

| Field | What to put in it |
|---|---|
| Home Assistant address | where it lives, e.g. `http://homeassistant.local:8123`. Pasting `…/api` or the full conversation path works too |
| long-lived access token | made in Home Assistant, under a user's profile |
| conversation agent | blank uses whichever agent is set as default over there |

**Make it a Home Assistant user of its own, and not an administrator.** The
token carries that user's permissions and never expires, and every action shows
up in the logbook as that user whoever actually spoke. One account for this
display is the difference between a logbook that tells you something and one
that says the same name for everything.

**What voice may touch is decided in Home Assistant**, by exposing entities to
Assist. There is deliberately no list of allowed devices here — the control
over there already holds no matter what is talking to it, and a second copy
would only be a weaker one that can disagree with the first.

**Start with few entities exposed.** Most of the wait on an LLM-backed agent is
the list of exposed entities going into the prompt on every call, and choosing
among four lights is where a small model succeeds and among sixty is where it
starts guessing.

**Which agent answers changes what to expect.** The built-in intent engine
matches sentences: it is fast — a tenth of a second — does exactly what it is
told, and says it does not understand anything that is not a command. An
LLM-backed one interprets, so *"it's a bit dark in here"* works, and each
request is two model passes rather than one. Set the **timeout** to the agent
you actually have; one chosen for the intent engine will cut off an LLM agent
just before it succeeds.

**It stays awake after a command, like every other assistant.** Home Assistant
reports that it has finished acting, and Resonance deliberately does not act on
that: give another command straight away, without saying the name again. The
usual awake window ends the conversation, the same as everywhere else.

That was not the behaviour on the first day. It slept the moment a command
completed, which is defensible on paper and awful in a room — the display went
quiet with no farewell, and everything said after it was discarded. It looked
broken. If you ever see that again, it is a bug, not a setting.

**When it recognises nothing, ask** hands the question to another assistant.
Somebody will ask the house what the capital of France is, and this is meant to
stop that being a dead end: the model answers, in the house's name and voice,
and nobody is told they used the wrong word.

**Expect it to fire rarely on the built-in agent.** That agent matches the
*shape* of a sentence before it looks for a device, so "what's the capital of
France" comes back as *"Sorry, I am not aware of any device called capital of
France"* — an unknown device, not an unrecognised sentence, and the fallthrough
does not apply. It catches sentences that match no pattern at all, such as "how
are you". This is a known limit rather than a fault, and widening it is held
back on purpose: an unknown device and a general question are indistinguishable
in the reply, so a command for a device you do not have would be answered by a
model that may claim to have done it.

Leave it at *nothing* for an LLM-backed agent, which interprets rather than
matches, answers general questions itself, and so almost never reports that it
recognised nothing.

**If the assistant it hands to cannot be reached, you hear that**, rather than
the house's "I couldn't understand that". The house's words would be true of
the house and misleading about the system — the question did reach something
that could have answered it, and that failed — so a person told the first
thing would go away believing they had phrased it badly. The spoken failure
names the assistant you addressed; the reason appears on the display's status
line.

Only the **timeout** applies from the Limits box, and there is no system prompt:
Home Assistant holds the conversation itself and its agent is instructed over
there. Those controls hide themselves rather than sit on screen doing nothing.

**Tested against a real installation.** Spoken to by name and asked to switch a
real light on and off, over voice, end to end. Press TEST first anyway — it
tells you in one round trip whether the address, the token and the agent are
right, which is three of the four things that go wrong.

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

A Home Assistant token is a key like any other here, and lives in the same
place under the same rules — the field is labelled differently because that is
what Home Assistant calls it, not because it is treated differently.

Keys live with the model profiles, in `displays.json` — admin-only, and not
the world-readable document — one per profile rather than one per assistant.
A key is **never returned to a browser**: the field shows whether one is
stored, not what it is. Leaving it blank keeps the stored key.

**Changing which service a profile answers with drops its key and its
address**, unless you supply new ones in the same save. Carrying one provider's endpoint into
another would send an Anthropic key to whatever happens to be listening on
the old URL, which is worse than an error because it looks like it worked.

An install that predates all this is migrated on first start: `backend.json`
becomes the first assistant, keeping the word the shared settings had, so the
box answers to the same word afterwards as before. `backend.json` is left on
disk rather than deleted — an upgrade that removes the file it read from has
no way back if the migration was wrong.

## System prompt

Sent ahead of every question, and it matters more here than in a chat box: the
reply is **read aloud**. Markdown, bullets, headings and emoji are all noise
when spoken, and a bulleted answer read out is unusable.

Each assistant has its own. A local model and a hosted one want different
instructions, and one wording covering both suits neither. A Home Assistant
endpoint has none at all — its agent is instructed in Home Assistant — so the
box is closed on those.

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

**TEST** puts one short question to that endpoint and reports the reply and the round trip in milliseconds. It uses that one's own
connection, so a pass here means a viewer who says its name will get an answer
too.

Failures report the provider's own message rather than a bare status code,
because "404" tells you nothing about which field is wrong. On the *display*
they are reported against the assistant's name rather than the service — a
display says these out loud, and "openai returned 401" tells the person
standing in front of it nothing they can act on while telling everyone in
earshot what the box is wired to.

| Symptom | Usually |
|---|---|
| "cannot reach ..." | wrong base URL or port, or the model server is not running |
| "404 ... model" | model name does not match what is installed |
| "401" / "invalid api key" | key wrong, or missing for a hosted provider |
| "timed out after ..." | cold model; raise the timeout — or an LLM-backed house agent doing two passes over a long entity list |
| the house says it does not understand | that is a pass for the built-in agent on a test sentence; on a real command, the device is not exposed to Assist or is named something else |
| the house heard a command and did nothing audible | it did not fail silently — an action with nothing to say is spoken as "Done." If you hear nothing at all, look at the note on screen |
| still on DEMO | that one is set to DEMO — nothing was asked of a model |
| the wrong one answered | a near-miss; set the other speech profile to EXACT, or move the words further apart |
| nothing woke at all | the word belongs to none of them, or the gate is off — SPEECH tab |
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
