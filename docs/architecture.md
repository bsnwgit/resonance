# Architecture

How Resonance is put together: the settings and admin model, how a real
assistant is wired behind it, and how another application embeds it. This is
the design-level companion to the task-level guides — [Administration](administration.md),
[Assistants](assistant.md) and [Embedding](embedding.md).

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
is asleep, or the reason an endpoint
failed. This is not a debug affordance bolted on — the messages already
existed and were being written to elements present only in the admin panel's
preview, so every explanation was discarded at the one place somebody was
standing. A voice interface that goes quiet is indistinguishable from a broken
one; that applies to its diagnostics as much as to its answers.

> **The trust boundary** — which tier of data reaches a browser and which
> never does — is set out in full in [Security model](security-model.md).

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

The **?** in the strip at the foot of the panel opens seven documents covering
the display and every tab of the admin interface. It is blue, the same blue as
every ? beside a topic heading, so help is one colour wherever you meet it — and
it sits with ACCESS and the search rather than in the menu, because reading a
document is a way of getting somewhere, not something you configure. They live
as markdown in
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

### Admin settings

**ADMIN**, at the foot of the panel, covers how the server is wired
rather than how the interface looks: where it can be reached from, what it
takes to sign in, how long an idle sign-in survives, and the admin portal's
own port. It is stored in `app.json`. What the app answers on is not here — a
port carrying endpoints is a network profile, under PROFILES ▸ NETWORK.

Nothing here takes effect until the process restarts — you cannot move the
floor you are standing on. The panel shows what is configured against what is
actually bound, and says plainly when a restart is owed:

```bash
./serve.sh stop
./serve.sh start
```

The port is checked before it is accepted: 1024–65535, and not one a network
profile is using,
and **not already in use by something else on the machine**. A port that fails
to bind would otherwise only reveal itself at the next restart, with the admin
interface gone and the fix being to edit JSON on the box by hand.

`serve.sh` reads `app.json` too, and records the pid it started. Without that
pid, changing the display port would leave `stop` looking at the new port while
the old process was still running on the old one.

The `PORT` environment variable still overrides everything and still shifts
all three together — `PORT` plain, `PORT + 1` HTTPS, `PORT + 2` admin — so a
second instance can be run without touching the stored configuration or the
network profiles.

Accounts live in `users.json` next to the server, mode `600`, passwords stored
as PBKDF2-SHA256 with 600,000 rounds and a per-account salt. Sessions are
in-memory, cookie-based, `HttpOnly` + `Secure` + `SameSite=Strict`, and expire
after 30 minutes of inactivity. Failed sign-ins back off geometrically per client
address. Changing a password or a role drops that account's live sessions.

**HTTPS only wherever a network is involved.** The admin listener does not
start without a certificate, because it accepts a password and holds the
assistant's API key, and neither may cross the network in the clear. If it is
missing from the startup banner, run `make-cert.sh` and restart.

The one exception is loopback, where the reason does not apply: nothing
crosses a network at all, `http://localhost` is a secure origin in its own
right, and the certificate ceremony is pure obstruction in front of the
install that setting exists to make possible. The panel still asks for a
password there: it is the one interface that always does, whatever else is
configured, because it holds the assistant's API key and the power to grant
anybody access to anything.

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

A route is a name, the profiles it names — **speech** for the word it answers
to and the voice it answers in, **model** for the connection, **network** for
the port it answers on — and its own instructions and limits. You can *hear*
which one answered, which matters the moment two of them can reply to the same
room. The connection is not the route's: several routes can name one model
profile, so the key is typed once and rotated once.

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

Two endpoints sharing a word is prevented by one speech profile belonging to
one endpoint, rather than by comparing words at the point of saving. Words that are merely *acoustically* close are not
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

**A connection is a model profile.** Provider, address, model and key are a
named set under PROFILES ▸ MODELS, and an endpoint names one — so two
endpoints on the same model are one connection rather than the same credential
typed twice, and rotating a key is one edit rather than six.

**OPENAI-COMPATIBLE** is a *dialect, not a vendor*. Ollama, OpenClaw, LM Studio
and vLLM all speak it, so one adapter reaches all of them and the only
difference between them is the base URL.

| Server | Base URL | Model field |
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

It is a shape of its own rather than another OpenAI-compatible address,
because the wire format genuinely differs: the key rides an `x-api-key` header instead of
`Authorization: Bearer`, an `anthropic-version` header is required, the system
prompt is a top-level field rather than a message in the list, `max_tokens` is
mandatory, and the reply arrives as a list of content blocks rather than a
single string. Base URL is `https://api.anthropic.com` and there is only one,
so choosing the provider fills it in. A key is required, and
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

**Listing what a host has installed** — asking Ollama's `/api/tags` on the
same host so a model name is chosen rather than typed from memory — is
implemented (`listModels()`) but currently reaches nothing: the element it
paints into went with the connection when it moved to the model profiles, and
has not been rebuilt there.

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

The server states the current date and time on every request, because a model's
sense of "now" is frozen at its training cutoff and it will otherwise answer
that question confidently and wrongly. It goes in as its own note immediately
before the question rather than in the system prompt, and that placement is
about speed rather than tidiness: a prompt cache matches from the first token,
so a stamp that changes every minute sitting ahead of the system prompt and the
tool definitions threw away everything a server could have reused. On a machine
without a GPU that cost the whole prompt again on every call. The system prompt
and the tools are identical from one question to the next, so they come first
and the clock comes last. The time is
the **display's** local time: the browser reports its IANA zone with each
question and the server formats accordingly, so a box running on UTC does not
tell somebody in New York at 8pm that it is already tomorrow.

The zone name is validated against the tz database and then discarded — what
reaches the prompt is formatted server-side, never a string the client sent.
An unrecognised zone falls back to the server clock.

Recency is a different matter and is not fixable this way: the model has no
internet, so the prompt asks it to say it does not know rather than guess.

**There is now one exception, and it is narrow.** An embed can be granted
operations on the application it is embedded in — see below — and within that
grant the model does reach live data. It reaches nothing else: there is no
web search, and a display on a wall is inside no application and has no page
to make a request from.

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
anyone who opened the page. Keys live with the model profiles in
`displays.json`, admin-only at mode 600, one per profile rather than one per
endpoint — and a key is never returned to a browser: the panel is told whether
one is stored, not what it is. Leaving the field blank keeps what is there.

Changing a profile's provider drops its key and its base URL unless new ones
arrive in the same save. Carrying one provider's endpoint into another would
send a hosted key to whatever is listening on the old URL — a failure in the
one direction that looks like success.

Measured round-trips on the reference box, cold then warm:
`qwen2.5:1.5b` 1.4s / 1.6s, `qwen2.5:3b` 10.1s / 3.6s, `qwen2.5:7b` 28.2s /
11.1s. Choose accordingly — for a voice front-end the wait is the product.

## Embedding it in another application

An admin creates an **embed key** under ENROLLMENTS ▸ EMBED, beside the person and the screen — the three things that arrive here, each admitted and revoked the same way. What exists is listed under ACCESS ▸ SITES, the third register beside the nodes and the assistants, on the same division the other two already draw: ENROLLMENTS is where something arrives, ACCESS is where it lives once it has. The host application's
*server* exchanges it for a one-use code; the host's page frames the result
and trades the code for a session. Server to server, so the layout it asked
for and its right to ask are settled before a browser is involved.

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

**Both are settled on the key, and both are the admin's to change.** One key
is one surface: a lobby kiosk and a support widget are two keys, separately
revocable and separately rate-limited, and the admin list says exactly what
each one draws. Holding the chrome on the key means it is signed into the key
rather than riding in query parameters — plain parameters mean any user
appends `&talk=1` and grants themselves a microphone the host never
authorised.

They were immutable at first, on the reasoning that a page is already framing
this. That named the risk correctly and charged it to the wrong party: the
only way to change anything was to issue a second key and delete the first,
which is a new id — every authorize profile that had ticked the old one
silently stops naming anything, and the far end has to be sent a credential
and wire it in again, to correct a hostname. So the record is editable through
`/embeds/update`, by the same validator that wrote it, and what the risk
actually asked for is met instead: **an envelope that narrows takes its live
sessions with it.** A session token carries the parts, the capability and the
origins it was minted with, so a narrowed key whose sessions kept running
would be narrower on paper only, for as long as a session lasts. Change any of
them and every session that key holds is dropped; a rename drops nothing.

**Two admins, and grants only ever travel one way.** This admin sets the
ceiling. The host's own admin may narrow what their users get, on either axis,
over `postMessage` — and can never widen it. The refusal lives in the embed
rather than in an agreement: the host page is untrusted by definition, so
"cannot add" has to be code that ships from here.

**Incoherent arrangements are refused at creation and at every edit**, in the
admin page, naming the orphaned part — a human sees the mistake immediately
rather than a host developer reading it out of a 400 three weeks later. One
validator serves both, which is what keeps an edit from reaching a state a
create could not have produced.

**Responsiveness belongs to the embed, not the API.** Desktop console and
phone voice-only is a breakpoint problem, and the narrow-viewport rules key
off the *frame's* width rather than the device's. Solving it by issuing a
different key after sniffing a user agent would be the wrong layer.

**A code in the URL, never the token.** A session token is a bearer
credential and the obvious design puts it in the iframe's `src`, which is the
worst place available for one: the host's own scripts set it and can read it
back, and so can their analytics, their error reporter, the history, a
referrer and a screenshot in a ticket. The origin allow-list does not help —
it stops another site *framing* this and does nothing against `curl`. So the
URL carries a code good once and for a minute, and the token it buys exists
only in that page's memory.

**An embed session is a vetted caller.** It satisfies an assistant's "no
anonymous callers" on the same reasoning a code-enrolled screen does: an admin
made the key, named it, chose what it may do, and can revoke it. Without that
the setting was unusable on the one deployment it matters most for — a server
an embed necessarily exposes to every visitor's browser — because ticking it
would have taken the embeds down along with the strangers it was aimed at.

**And it is granted the way a screen is.** An authorize profile's allow-list
holds a fourth kind of member: the embed keys that may use the endpoints it
guards. This shipped a round late and the gap was not academic — the first
deployment it met had every endpoint restricted, so a feature that was
complete, correct and tested reached exactly nothing. A key that can be
created, rate-limited and audited but cannot be granted anything is not a
limitation, it is a feature with no door. No group membership to add up:
groups hold screens and people, both of which are rows in a register, and an
embed key is in neither.

**Two rate windows, not one.** The key's budget is the application's total and
the bill; a second, smaller window is one browser's share of it. One number
could not say both — sized for a busy application it is a number one visitor
can spend alone, sized for one visitor the second visitor finds it empty.
Where the key names the person the window follows *them*, so a reload buys
nothing; where it does not, it follows the session, and the key's own total is
what actually bounds the damage.

**Identity is asserted by the host's server or not at all.** A key can require
the person to be named; their application authenticated them and holds the
key, and a browser saying who it is would be a text field. Required means the
code request is *refused* without it, so the mistake surfaces on the first
call of the integration rather than months later as an audit trail full of
nobody.

**The loader ships from here** — `embed.js`. Six applications hand-writing the
same forty lines is six chances to get the microphone attribute, the
message-origin check or the renewal subtly wrong, and five of those fail
silently. It renews without reloading, so a session ending mid-conversation
does not read as the assistant forgetting the last ten minutes.

**The embed is memoryless**, and that is the sequencing rather than an
omission — see the roadmap.

**Which endpoint an embed reaches is the key's, not the port's.** A display is
at a port and answers as that port's endpoints and no others, which is right
for a screen on a wall. An embed is not at a port: it is a key inside somebody
else's page, and everything else about it — what it draws, what it may do,
which origins may frame it, what it may ask their application for — is decided
on that key. Leaving the assistant to be decided by which hostname their page
happened to name meant moving a site between assistants was an edit and a
deploy on *their* side, for a choice that was never theirs to make and is paid
for on this one. So the key names it, blank means the port's, and a named
endpoint that is later deleted or switched off falls back to the port's with a
line in the log — a panel going silent because somebody renamed an assistant
is the worse failure. The authorize profile is unchanged and is still the
gate: the port stopped being a boundary because it never was one.

### Reaching the host application's data

An embed can answer about the application it is sitting in rather than only
beside it. The design question was never how to fetch the data; it was **who
makes the request**, and the answer decides everything else.

**The browser does.** Calling their API from this server would need a service
credential on every host application — one account for everybody, necessarily
holding more than any single visitor should see — network reach into places
that have never accepted an inbound connection, and a schema per customer
forever. The panel is already framed inside a page authenticated as that
person, so the call is made there, same-origin, with their own session. This
server holds no secret of theirs and reaches nothing of theirs.

**So the loop runs through a request rather than inside one.** `/ask` answers
with `tool_call` instead of `reply`; the frame asks the host page to perform
it; the same question comes back with `tool_results`. Four laps and it stops —
a model that has misread its tools will call the same one for ever, and every
lap is a request through somebody's page in their name. Nothing is parked on
this side between laps: the conversation is client-held everywhere else here,
and a half-finished question in server memory would be state to expire, to
sweep, and to lose on a restart.

**Three authorities, and the narrowest wins.** The application declares a
ceiling in a grant file it serves itself; the admin ticks within it on the
site's row; the visitor's own login caps whatever survives. The owner of the
data sets the outer bound and only they can raise it, which is what makes this
safe to embed in an application somebody else runs. No grant file means read
verbs only — silence never grants a write.

**Nothing here is specific to any application.** Operations are read out of an
OpenAPI document and granted against `operationId`, the one identifier in that
document meant to be stable; a grant naming a path would follow the next
refactor onto a different operation and keep working. Both that document and
the grant file must sit on an origin the site is already registered under —
not tidiness, but the difference between a text box and a text box this server
will fetch from every address on its network.

**The model's output is untrusted input.** An invented operation, a renamed
parameter, a path segment stuffed with a slash are ordinary failure modes of a
model rather than attacks, and each would otherwise arrive at somebody's API
as a request their page made in their name. Every proposed call is resolved
and checked here against what the session was granted, and `embed.js` checks
again at the far end against the operation's own path template — so a frame
that has been tampered with still reaches only the declared paths.

**A write stops and asks, per action.** The confirmation is drawn by the frame
and never by the host page: a confirmation rendered by the party that wants
the action is not a confirmation. It names the real values, because a voice
interface has no address bar to check. There is no session-wide "allow
writes" — that is the same hole with one more click in front of it.

**Both legs of every call are logged, and only the request survives.** Method,
path and query going out — the same line the host's own access log will carry,
so the two can be laid side by side — and status and byte count coming back. A
`no status` is not an HTTP code: it means the browser never received a
response, which separates "their API refused it" from "the call never left the
page". The body is never written: it is their data, and `server.log` travels.

**A proxy in front of this server needs its read timeout raised.** Every lap is
its own request waiting on a whole model pass, and 60 seconds — nginx's default
— is less than two laps on a small local model. It presents as the assistant
being unreachable, which is the one thing it is not.

Only the OpenAI dialect and Anthropic carry tool definitions. Home Assistant
does its own on its own side and is untouched; `demo` cannot. Written up in
full in [Reaching the host application's data](host-data.md).

**The gotcha that catches everybody:** a microphone inside an iframe needs
`allow="microphone"` from the host, the host page itself on HTTPS, and
permissions-policy delegated down. Miss any one and the embed looks broken in
a way that has nothing to do with this server. The admin preview has no
microphone for precisely this reason.

