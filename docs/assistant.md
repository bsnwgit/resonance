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

**An endpoint names three things and holds almost nothing itself.** Each is a
named profile, built once on its own tab and pointed at from here:

| It names | Which carries | Built under |
|---|---|---|
| a **connection** | the model it speaks to and the port it answers on | PROFILES ▸ CONNECTION |
| a **layout** | the face, the voice, the greeting, the wake word and the name it answers to | PROFILES ▸ LAYOUT |
| a **permission** | whether a caller must be known, and which callers are allowed | PROFILES ▸ PERMISSIONS |

That is the whole of the row, and each of the three may be named by more than
one endpoint — which is the point of them. A key typed once serves every
endpoint reaching that service; a rule written once governs every endpoint
under it. The service, address, model, key, limits and system prompt are the
*connection's*, not the endpoint's, and are edited once for all of them.

**One row per endpoint**, saved together by the SAVE inside it. **ADD INSTANCE**
at the foot of the tab makes another and opens it; each row carries its own
TEST, MAKE DEFAULT, SWITCH OFF and DELETE.

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

### Permission

One picker on the endpoint, and it answers both of the questions the server
asks of every caller: **must somebody be known at all**, and **is this
particular caller allowed**. They were two sections here — *Sign in* and *Who
may use it* — with five fields between them, repeated on every endpoint that
wanted the same rule. They are a named pair now, built under **PROFILES ▸
PERMISSIONS** and pointed at from here.

- an **authenticate** profile — whether a caller must be known, and how long
  being known lasts
- an **authorize** profile — which callers are allowed, given that
- a **permission** — one of each, under a name, which is what an endpoint names

**An endpoint naming no permission is refused outright**, not opened. The old
default was open, and that was only safe because it was the shape an endpoint
was *born* in — a field somebody had to go and set. A missing pointer is not
that; it is a deployment mid-edit, and mid-edit is not a state to be permissive
in. The same goes for a permission whose authenticate or authorize profile has
since been deleted: half a permission is not a permissive one. Saving is
guarded against leaving one dangling, and the server refuses at the point of
use as well, because a document can also arrive from a backup or a hand edit.

**A permission is shared on purpose.** Change the rule once and every endpoint
using it changes — which is also the thing to know before editing one: what you
change there reaches all of them. Where a rule really is this endpoint's alone,
make it a permission of its own and name it after the endpoint.

#### Authenticate

**Sign in** — whether somebody must be **signed in as a person** to use the
endpoint at all. Nothing here is about *which* people; that is the authorize
half, and the two are independent, so "open to everybody, but they must sign
in" is a thing you can say.

**REQUIRED means no anonymous caller**, not that there must be a person. Two
kinds satisfy it:

- somebody **signed in**, and
- a screen you **enrolled with a code** — minting that code and carrying it to
  the device is itself an admin deciding that screen should be here, which is
  the same act of vouching a password is.

A browser that merely opened the display page is neither, and is refused.

**It refused a device outright until 2026-08-20**, and that was this setting
turning away the population it is most often wanted for. A hallway screen an
admin had hung deliberately could not use an endpoint that asked for a sign-in,
because being approved was exactly what made it a device and a device could
never sign in — so ticking such an endpoint onto such a screen produced a grant
that reached nothing and said so nowhere. The rule now asks whether the caller
is *known*, and a code is how a screen becomes known.

**What it costs you to know:** a wall screen satisfying this has no person
attached, so whoever walks up uses that model unattributed. It limits the model
to callers you vetted; it does not attribute the bill to a name. Where you need
the name, the caller has to be a person — which means a personal browser, not a
screen on a wall.

**Session limit** — minutes of quiet before a sign-in lapses, and the clock is
**the gap between conversations**, not a lifetime. A session in use never runs
out; one nobody has spoken into for the limit does. Zero is no limit, which is
the right answer for a wall nobody signs in at and the wrong one for anything
else. 5 to 480.

The gap is measured between *conversations* deliberately. A page open on a wall
polls this server every few seconds, and none of that is somebody being
present: a timer that slid on requests would never lapse as long as the browser
was switched on, which is the opposite of what the setting is for.

It lives here because it is a property of the door somebody came through rather
than of the person who came through it. Before this it was a field on every
identity, with no control anywhere that could set it and a twelve-hour constant
behind it — a setting nobody could see and nobody could change. Existing
deployments migrate to **no limit**, because that is what they had.

People sign in at the display with the email address and password they set from
their enrolment link. The admin panel is not affected and never was: it always
asks, whatever is set here, and its own idle timeout is a separate setting under
SETTINGS ▸ SECURITY ▸ Sessions.

#### Authorize

**Who may use it.** Two reasons to restrict an endpoint.

**A room with several microphones in it.** Two people, one of them addressing
the wall screen, and every other device in earshot hearing it too. Push-to-talk
on a phone is the correct setting and is not a control, because nothing makes
anybody set it — so the rule lives on the endpoint instead.

**What an endpoint costs.** A hosted model is worth giving to some devices and
not to every one that can reach the port, and this is where that is decided.

**ANY DISPLAY** is what every endpoint did before displays existed.

**ONLY THESE** names the devices, groups and people that may reach it — a wall
screen, a TV, a laptop, a phone. Anything else that hears its wake word drops
the utterance: no answer, nothing passed to whatever it was already talking to,
nothing said out loud, no matter how that browser is configured.

**The lists offer only what a grant can reach.** A screen appears once it is
approved under ACCESS ▸ NODES; a person appears once they have used their link
and chosen a password. Before that a row is refused whatever is ticked, so
offering it was a tick that could not do anything and looked like it had. One
already ticked stays on the list whatever state it is in — a list quietly
dropping a grant would take it away at the next save without anybody asking.

Restricting the endpoint that is **default** is worth a moment's thought:
anything typed into the composer with no name in front of it goes there, so
displays outside the list get nothing back when somebody types.

**The same ticks are on a person's and a device's own row**, under ACCESS —
the list of endpoints there and this list of callers here are two views of one
grant. Ticking an endpoint on a row writes it into that endpoint's authorize
profile, which is the thing being read: **so it grants every endpoint sharing
that profile**, and unticking takes it from all of them. That is what naming a
rule once means. The row redraws with what actually resulted rather than what
was clicked, so the reach is visible immediately.

**ONLY THESE with nothing ticked admits nobody.** That is allowed rather than
refused — restricting an endpoint before the tablet that will use it has been
hung is a legitimate order to do things in — and the profile says so in red
while it is true.

#### What actually puts a sign-in box on a screen

**Two different settings can produce it, and this is worth reading once.** The
display does not show a sign-in box because *Sign in* is REQUIRED. It shows one
because **this browser cannot use anything on this port** — and there is more
than one way to be in that position.

The server answers one question per endpoint, for the caller in front of it:
*may this caller use it?* A NO is a NO, whichever half produced it, and the page
reacts the same way to all of them — by offering the ways past. So an endpoint
you deliberately left open can still meet somebody with a sign-in box, if they
are not on its allow-list.

| Authenticate | Authorize | What somebody who is not signed in sees |
|---|---|---|
| NOT REQUIRED | ANY DISPLAY | **the assistant** — nothing is in the way |
| NOT REQUIRED | ONLY THESE, and they are not on it | **a sign-in box** — not because signing in is required, but because this browser may not use it, and signing in as somebody who *is* listed is one of the ways past |
| REQUIRED | ANY DISPLAY | **a sign-in box** — sign in as anybody and it works. Not on a screen enrolled with a code: that is already a known caller, and it sees the assistant |
| REQUIRED | ONLY THESE | **a sign-in box** — and signing in is not enough on its own; it has to be as somebody the list names. A code-enrolled screen the list names sees the assistant |
| *no permission at all* | | **a sign-in box that never opens it** — the endpoint is refused to everybody, and no caller can become one it accepts |

The one that surprises people is the second row: sign-in says NOT REQUIRED and a
sign-in box appears anyway. Nothing is wrong. **ONLY THESE is itself a statement
that some callers may not use this**, and a browser that is not one of them has
to become one — which means signing in as a person the list allows. The
authenticate half only decides whether that is demanded of *everybody* or just
of the ones the list does not already cover.

**A permission is refused if it is missing a half.** Deleting an authorize
profile two endpoints named would otherwise have opened both of them to
everybody, because an empty allow-list means *unrestricted* — which is why
deleting a profile a permission uses is refused while it is still named.

**When the change reaches a screen.** Both halves are read by the server on
every question, so a screen cannot use something it has stopped being allowed
to use, whatever it thinks. What it *shows* is a different matter: the page
draws the sign-in box from the permissions it fetched when it loaded, so
changing either half under a screen that is already on it takes effect at that
screen's next check-in, when it notices the configuration moved and reloads
itself. Until then it looks unchanged, and a question typed into it comes back
refused in the status line rather than as a box. **RELOAD** on the device's row
does it immediately.

**A tick list says when a grant is worth nothing.** On a PERSON's list, an
endpoint open to everybody reads *open to anyone signed in anyway* — ticking it
grants nothing, because it is reachable already. A device's list says the same
of an endpoint its screen could never satisfy: one requiring a sign-in, where
that screen asked from the page rather than being given a code.

Read the pair as one sentence and it stops being surprising:

- **authenticate** — must the caller be known at all?
- **authorize** — and given a caller, is it one of the ones allowed?

A sign-in box is what the display offers when the answer to either is no.

#### And when there is no box at all

Two states look like a fault and are not:

- **"Nothing is set up on this port"** — no endpoint has been given a
  connection carrying this port. There is nothing here to sign in to; giving an
  endpoint that connection is the fix.
- **A wall screen that stops answering** — an approved device on an endpoint
  whose permission requires a sign-in. It has no person on it and cannot
  acquire one, so it is refused. That is the setting working, not failing.

### The instance name and the wake word are two different things

The **instance name** labels the endpoint in the panel, in the log and in
`{assistant}`; it is never spoken and never matched against. The **wake word**
is what somebody actually says. An endpoint called *Kitchen Lights* is a
perfectly good label and a terrible thing to say out loud.

**The word is not on this tab.** It lives in the **layout** the endpoint names,
on PROFILES ▸ LAYOUT, along with the spellings it will also accept, the sleep
word and whether matching is forgiving — beside the face, the voice and the
name the assistant answers to, because those are one answer to "what is this
assistant" rather than four.

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
is **not refused at the point of saving**: the word is a layout's, and two
layouts given the same word are not caught. Two endpoints naming the *same*
layout are the case that used to bite, and the upgrade splits those — each
endpoint keeps a layout of its own with its own name — but nothing stops
somebody typing one word into two layouts afterwards. Words that merely *sound*
close are not checked either.

**LEARN HOW I SAY IT** captures what the transcriber actually returns when you
say the word, three times, and adds those forms to *Also accept*. It is on the
LAYOUT tab beside the word it teaches, not in an endpoint's block. The
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

A profile is one service under a name: **PROFILES ▸ MODELS**, one row each, the
same caret and the same one-open-at-a-time as every other list. **ADD A
PROFILE** makes one and SAVE commits the row.

**The limits and the system prompt are here**, not on the endpoint. A context
window, a token ceiling, a timeout and the instructions sent ahead of every
question are facts about *what is being spoken to* — and two endpoints on one
model wanting two different ceilings is not a case anybody has. They are set
once, where the model is.

**An endpoint does not name a model directly.** It names a *connection*, which
pairs a model with a network profile: PROFILES ▸ CONNECTION. One name answers
both "what does it speak to" and "where does it answer", because in practice
they are chosen together and a half-configured endpoint is one that speaks to
nothing or answers nowhere.

There is no MAKE DEFAULT here, and nothing is nominated behind it — the same
rule the network profiles have. An endpoint naming no model profile is not
inheriting one; it is on `demo`, says so, and any profile can be removed
because none of them is the one the deployment cannot lose.

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

**A profile binds what it names, and nothing overrides it.** It used to be
clamped: an app-level binding won over every profile, so *this machine only*
meant it for the whole server. That was right while a profile had no other
constraint. Each listener states its own interface now — a profile here,
enrolment under ADMIN, and the panel's own under ADMIN ▸ Admin Portal — so the
setting that says *this machine only* still means it, about the listener it
belongs to.

**The port is checked before anything is allowed to use it.** Saving tries the
port on the address chosen; on **ANY** it must be free on *every* address the
machine has, and a refusal names the one holding it, with its interface. This
happens at the point of saving rather than at the next restart, when the fix
would be editing JSON on the box by hand.

ANY is strict for a reason that is the kernel's, not a policy: ANY binds the
wildcard, and a wildcard bind is refused when the port is held on even one
address. A rule of "allowed if something can carry it" would have saved a
profile that could not then come up — the panel saying yes and the server
saying no at the next restart, in the log, where nobody is looking. If one
address is holding the port and you want the others, name one of the others
here.

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
nowhere else. One that names none **answers nowhere** — there is no nominated
default to fall back to, and that fallback is precisely what used to put two
assistants on one port. An upgrade turns the built-in display ports into a
profile called *Display*, and nothing moves
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

A profile is a **port and an address, and nothing about permission**. It
carried two permission switches once — *More than one endpoint*, and *The port
is the grant* — and both are gone.

**A port carries one endpoint.** Ports were shareable, several assistants told
apart by wake word; that ended when signing in became a property of the
endpoint, because a door with two assistants behind it can only have one lock
and would have to answer for the looser of them. Choosing a port another
endpoint already answers on is refused, and a taken port is not offered in the
endpoint's picker.

**No port selected means no port.** An endpoint that names no profile is
attached to nothing and answers nowhere. It used to fall back to a nominated
default, which is precisely what put two assistants on one port — two
endpoints that had simply never been given one both landed there, chosen by
nobody. The server names such endpoints at startup, and the endpoint's Network
heading reads *no port — answers nowhere*.

There is no MAKE DEFAULT on this page, and nothing is nominated behind it
either. Every profile is a listener and none of them is special: the built-in
display ports became a profile on upgrade and are treated exactly like one you
made yourself. A profile no endpoint has been given is not bound at all, and
the server says so at startup.

**Whether a caller has to sign in is not here.** It is an authenticate
profile's, reached through the permission the endpoint names — see *Permission*
above. A port is a door, not a lock: nothing about reaching one says who is at
it.

TLS is the same certificate the display port uses — the microphone needs a
secure context, and a second certificate for the same machine would be one
more thing to renew.

**Ports are bound when the server starts.** Adding a profile, changing a port
or pointing a different endpoint at one takes a restart, the same as the ports
on ADMIN: a listening socket is not something to open and close under
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

Only the **timeout** applies from the limits on its model profile, and there is
no system prompt: Home Assistant holds the conversation itself and its agent is
instructed over there. Those controls hide themselves rather than sit on screen
doing nothing.

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

On the **model profile**, beside the system prompt — not on the endpoint.

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

**Each model profile has its own**, on PROFILES ▸ MODELS beside the limits. A
local model and a hosted one want different instructions, and one wording
covering both suits neither — but two endpoints on the same model wanting two
different promptings is a case that never came up, and asking for it once per
endpoint meant every endpoint carried a copy to drift out of step. A Home
Assistant profile has none at all — its agent is instructed in Home Assistant —
so the box is closed on those.

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
setting. There is no web search and there is no plan for one.

**One exception, and only inside an embed.** An assistant embedded in another
application can be granted operations on *that* application and does reach its
live data — see [Reaching an application's data](host-data.md). It is not a
general answer to recency: it reaches that application and nothing else, and a
display on a wall is inside no application at all.

**If you are choosing an assistant for a site that uses it, choose for tool
calling.** Only OPENAI-COMPATIBLE and ANTHROPIC carry tool definitions;
HOME ASSISTANT does its own on its own side, and DEMO cannot. A small local
model is exactly where tool calling is least reliable — a 3b will invent
parameter names a hosted model would not — so an endpoint chosen for
conversation is not automatically the right one here.

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
| the wrong one answered | a near-miss; set the other layout to EXACT, or move the words further apart |
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
