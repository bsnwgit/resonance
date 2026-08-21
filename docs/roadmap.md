# Roadmap

This stopped being "roughly in order of value" the moment there was a concrete
deployment to build for. A real target decides what blocks what, and several
things that looked independent turn out to sit on top of each other.

## The deployment this is now ordered around

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

## Build order

| | phase | delivers | sits on | open decisions |
|---|---|---|---|---|
| 1a | ~~**Routes**~~ **— done** | three names reaching three destinations, verifiable with no Home Assistant involved | — | none |
| 1b | ~~**The Home Assistant adapter**~~ **— done** | saying the house name switches a light on | 1a | none |
| 2 | ~~**Displays, and binding a route to one**~~ **— done** | only the tablets you approved can actuate the house, whatever anyone's browser is set to | 1b | none |
| 3 | ~~**What a wall display looks like**~~ **— done** | voice only and speak only, an appearance per place, and a screensaver that is still the product | 2 | none |
| 4 | ~~**Staying up unattended**~~ **— done** | a tablet nobody touches for a year is still working | 3 | none · closed 2026-08-17 · alert and drop test in 8 |
| 5 | ~~**Identity**~~ **— done** | a person, as distinct from a place | 2 | none · built 2026-08-18 as accounts; the PIN it was designed around was removed the same day |
| 6 | ~~**Personal wake words**~~ **— done** | one person addressing a tablet stops triggering another person's device | 5 | none · built 2026-08-18 |
| 7 | **Memory** | conversations that mean something across sessions | 5 | **1** · what the retained unit is — deliberately left to experience |
| 8 | **Diagnostics and alerting** — *building* | a failing screen comes and finds you, rather than the other way round | 2 | none · window set to 7 days · still owes 4's network-drop test |

The last column counts decisions that need **you**, not implementation choices
made while building and shown afterwards. A phase reading *none* is ready to
start.

**Nothing outstanding blocks starting.**

**Alerting merged into eight rather than becoming a ninth phase**, because
eight already collects the events an alert would fire on, and building the
watcher separately would be a second pass over the same code. The consequence
landed on four: the server can tell a stuck display to reload itself, and when
that fails there is nothing left for it to do but tell somebody, which is
eight's job. **Four shipped without that alert** rather than eight moving up
beside it — decided 2026-08-16. Everything four is for works today; a display
the server cannot reach at all is visible in the panel as one that stopped
checking in, and what it does not yet do is come and find you.

The two remaining decisions are each answerable when their own phase comes
up, and one of them is deliberately waiting on experience rather than on a
decision.

**Six is built** — 2026-08-18. A person answers to a name they chose, and
uniqueness is decided by the matcher that does the waking rather than by
comparing letters, enforced on the server because a check in a browser is one
an API call walks past. The port and the shipping JS were run over the same 368
cases and agreed on all of them; a corpus of 34 is kept in `serve.py`, because
that coupling is real and nothing in either language enforces it.

**Eight is most of the way there** — 2026-08-18. Its open decision is taken:
the retention window is **seven days**, short on purpose and admin-configurable,
because retention is the only control over a store that holds what was said to
a display. Built: the event store and what a screen reports, the conversation
record and the decision trail that makes a voice fault answerable, the health
view, the four-state alert model, and four sinks — syslog, a webhook, Home
Assistant on its own connection, and email — with quiet hours and a digest.
**What it still owes is the network-drop test**, which needs real hardware and
a pulled cable, and it is the reason this phase is not closed.

**Five is built** — designed 2026-08-17, built 2026-08-18. A session is a
user or a device and the URL decides which; guest and signed-in user are two
strengths of retention rather than two strengths of reach; identities and their URLs are created in the panel and nowhere else;
and Home Assistant keeps one service token whoever is speaking. What came out
of designing it is a piece deliberately left for afterwards: signing a user
into a device several people share but which is not a kiosk. That waits for
one-for-one to be working.

**One is two deliveries rather than one.** Routes stand up on their own — demo,
a local model and a hosted one are three destinations reachable by three
names, and wake-word routing can be shaken out on a test box before Home
Assistant is anywhere near it. If the refactor breaks something, that is when
you find out, rather than while also debugging a new adapter.

**3 is done**, and it grew past its entry the way two did. The entry asked for
two settings; what closed it was those two plus an appearance a place can have
of its own, a wall that is speak only because push-to-talk needs a space bar
nobody has, a line telling a passer-by what to say, dark hours on a clock, and
the full screen. Both profile lists are central and named from a device, which
was the shape asked for once the first version put the numbers on each row.

What it turned up along the way is in the log below, and two of them were
faults nobody was looking for: an admin route answering 401 where its siblings
answer 404, and the frame rate readout — a rig instrument — sitting on every
wall in the building, in the one place a screensaver could not save it.

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

**4 is done and closed**, by him, on 2026-08-17 — with one thing owed and
booked into eight rather than left hanging over it: nothing it built has yet
faced a real network drop on real hardware, and that test is written up in
eight's entry as five things to run rather than as a good intention.

It is the first phase whose value is entirely invisible when it works. What it
turned out to be is a set of small mechanisms that only make
sense together, and one of them — the check-in — pays for four of the others:
last seen, the reload channel, the settings reaching a building of screens, and
a screen noticing on its own that the server came back. Its position held:
designing it moved nothing, and turned up two real leaks in code that had
already shipped, both since fixed.

The one thing worth having here rather than in its entry is **what reloads, and
for whom**. It was built kiosks-only — a desk tab has somebody in front of it,
and taking one out from under them to apply a colour changed upstairs looked
like the worse interruption — and that was overruled the same day: **every
display reloads**, for every reason. A screen showing settings somebody
replaced an hour ago is stale whether or not it hangs on a wall, and one rule
is a rule somebody can predict. What keeps it from interrupting anybody is that
nothing reloads while a person is talking to the screen or typing into it,
which is a test about the moment rather than a class of device — and it was
already there, guarding the nightly refresh.

What does still differ by device is what a screen *says*: a kiosk speaks the
outage aloud because it has no transcript and nobody sitting at it, and
everything else stays quiet and fails when somebody actually uses it.

Two and three were one phase until the wall-mounted side outgrew it. They
share a substrate — a display the server knows about — but nothing else:
phase 2 is server-side enforcement and gate logic, phase 3 is canvas and
presentation. Splitting them keeps each verifiable in one sitting, and stops a
safety property waiting on a screensaver.

**Three sat where it did because burn-in is a clock, not a backlog item.**
Every day a tablet runs without it is damage that cannot be taken back, and
that clock starts the day the first one goes on a wall. Everything after it
could wait; this could not wait as cheaply — which is why it was built before
anything with a longer payoff.

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
  logbook as that user regardless of who spoke.

  **Not taken: an identity carrying its own HA token** — decided 2026-08-17,
  and it closes phase five's open decision. Per-identity tokens are the only
  way to make HA aware of who actually asked, and the price is switching tokens
  between people while the house is being spoken to — one person's request in
  flight while another arrives — which is a worse failure than the attribution
  it buys. One service account, always, whoever is standing there. So HA is a
  property of the endpoint, fixed when an admin configures it, and nothing
  about it becomes person-scoped when identities land.

  The consequence, stated here so it is not discovered later: the logbook shows
  this server's HA user for every action, forever, and the house can never tell
  who asked. Attribution stays on this side, where the transcript already
  credits each line to whoever gave it and the durable version of that is the
  conversation record in phase eight.

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
  | a **person** | their email address and password | as many as they like |

  A wall display is one physical object and two things claiming to be it is
  always wrong, so it is pinned to a single token that an admin blesses. A
  person is not a physical object — phone, tablet and laptop are all
  legitimately them — so their credential is something they *know* rather
  than something a device *has*. They sign in, that browser earns a session,
  and they are not asked again until it expires.

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
  set of them, made under GROUPS and named wherever access is granted.

  **Two kinds, and they do not mix**: people and devices, set per row under
  DEVICES and otherwise inferred from how the row arrived. They answer separate questions — *the
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

  Most of this already existed. `data-text="off"` hides the transcript and the
  composer together, and the embed chrome does the same through
  `data-noparts`. What was missing was somewhere for an admin to say it once,
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

  **An open microphone is not a conversation**, and the idle clock does not
  stop for one. A wall display transcribes every noise in the room — it has to,
  or the wake word is never caught — and none of that is somebody talking to
  it. What holds the clock is the assistant speaking, a clip playing, a
  question outstanding, or the wake window still open; between two sentences
  nothing is speaking for a few seconds, and the window is what stops a screen
  dimming at somebody mid-thought. It asked the FIGURE's own state until
  2026-08-20, which is a flag set from six places — any one of them returning
  early left it set, and that screen never reached its screensaver again with
  nothing on screen to say why.

  **A dim level beside it**, as its own number. Reducing brightness does more
  against burn-in than movement does, and it is independently what a hallway
  screen should do at two in the morning.

  **It ends on the wake word or on touch**, easing back to the centre rather
  than snapping. On a voice-only display touch is the only signal that is not
  speech, so it has to count. The transcript hides while it drifts — text
  sliding around a screen is worse than either state on its own.

  **An appearance a place can have of its own.** Added while building, and
  not in the original entry — the same way phase 2 grew past its own. The LOOK
  tab is one document for everybody, which is right for almost all of it and
  wrong for exactly four values: a hallway read at three metres and a laptop at
  fifty centimetres cannot share a type size, and a wall wants the figure
  filling the frame where a desk wants room for the transcript beside it. So
  type size, palette, layout and the figure become a profile a device names,
  and everything else stays shared.

  **Shortlisted rather than "override anything"**, deliberately. A per-place
  setting that could cover the whole document would quietly end the ability to
  change something once for everyone, which is the reason the shared document
  exists at all.

  **Both profile lists are central and named by id**, and they are separate
  axes: day and night in one hallway share an appearance and differ only in the
  dim, and a laptop can be given larger type without being told to drift.

  **Speak only, and it says what to say.** A wall is voice only and in the
  listening mode from the moment it is marked one — push-to-talk holds a SPACE
  bar that a tablet on a wall does not have. And because a silent figure tells
  a passer-by nothing, a wall carries one dim line naming the wake word, drawn
  into the picture and travelling with it while the screensaver drifts.

  **Full screen on the first touch.** No page can remove a browser's own
  chrome, but it can ask to be shown full screen, and a browser grants that off
  a gesture — so it happens on a touch rather than on load. Only on a wall, and
  a manual exit buys a minute of quiet: whoever left full screen is nearly
  always the person installing the screen.

  **Dark hours beside the idle dim.** Idle asks whether anybody has been here
  recently; only a clock keeps a hallway dark after somebody walks past it at
  three in the morning.

  *Panel:* on a wall, voice only, and one profile from each list, on each
  display in the list the phase above builds — with the profiles themselves set
  once, centrally.

- **Staying up unattended.** Everything built so far assumes a page somebody
  opened and will close. A tablet on a wall is a browser tab running for a
  year: through server restarts, network drops, Home Assistant reboots,
  certificate renewals and its own operating system's ideas about
  backgrounding, with nobody standing in front of it to notice or reload.

  The failure mode this is designed against is specific: **a screen that looks
  perfect and does nothing.** The geometry is driven locally, so it keeps
  drifting and breathing with no server involvement at all — somebody walks
  past, sees it moving, and assumes it is fine, while nothing has reached the
  server in a week. That is worse than a blank screen, which at least gets
  reported within the hour.

  It is not much work. It is invisible work, which is why it needs its own
  entry — nobody ever gets to it as part of something else.

  **The display polls, and that one decision pays for four others.** A wall
  display at rest issues no requests, so without a poll it would not discover
  the server had come back until somebody walked up and spoke to it: the outage
  would end and the screen would stay broken. The same poll keeps `last_seen`
  fresh, gives the server somewhere to answer *reload yourself*, and turns a
  dead screen into something the server can notice on its own.

  **On reconnect it reloads the page rather than resuming in place.** Resuming
  preserves a conversation nobody is having any more — the outage was minutes
  and the person left — while a reload picks up a deploy and any settings
  changed while it was down. Route and appearance are re-fetched as part of
  that, because an admin who corrected a display's configuration during an
  outage should not have to walk over afterwards to make it take.

  **A failed request retries three times and then says so, and the number is a
  setting.** Three is right for a restart and wrong for a severed cable, so the
  count and the interval are configurable rather than baked in.

  **How it says so depends on what the display is.** A wall display speaks the
  failure once, after the third attempt — it has no transcript and no composer,
  so a screen that shows nothing has no other way to tell anybody, and saying
  it more than once would make an outage worse than the silence it replaced.
  Anything not on a wall stays quiet until somebody tries to use it, and then
  fails immediately rather than making them sit out three attempts. Somebody
  who has just spoken is owed an answer now; a hallway nobody is standing in is
  not.

  **The banner clears itself.** Nobody is there to dismiss it, so an alert that
  has to be acknowledged at the screen is an alert that stays up for a month.
  Acknowledgement belongs where somebody actually is, which is the admin page —
  see the diagnostics entry below.

  **A forced nightly refresh, because a tab that never reloads accumulates.**
  Admin-configurable, read off the *device's* clock for the same reason dark
  hours are, and deferred until the conversation ends rather than reloading a
  screen somebody is mid-sentence with. A building can refresh every screen at
  once or stagger them by an interval, and that is a setting rather than a
  default because twelve tablets reconnecting in the same second is a load the
  server did not previously have.

  **The refresh runs alongside fixing the leaks rather than instead of them.**
  It is a net under work not yet done, and treating it as the fix would mean
  shipping a leak and a nightly workaround for it in the same release. Two were
  known, and **both were fixed on their own branch before this was built**,
  which is the order that made the refresh a net rather than a patch:

  - **Every spoken reply leaves an analyser behind.** Speech builds a fresh
    `AnalyserNode` and `BufferSourceNode` per utterance and wires them to the
    context destination; nothing disconnects them, and a node connected to the
    destination is held alive by the audio graph rather than by the reference
    the next utterance overwrites. A house speaking to a tablet a few dozen
    times a day leaves thousands of live analysers behind in a year. Two lines
    in `finishUp()`.
  - **The rendered transcript has no cap.** `convo` is bounded —
    `while (convo.length > CONVO_MAX) convo.shift()` — but the log element it
    is drawn into is not. It never touches a voice-only wall display, and it
    bites a desk tab left open for a month.

  Checked and *not* leaking, so nobody looks twice: there are no blob URLs
  anywhere, the microphone tears itself down with `getTracks().stop()` and
  `ctx.close()`, and every `addEventListener` call is one-time startup wiring
  rather than something added per utterance.

  **The tablet's own behaviour is the device's problem, and one part of it is
  nobody's.** Suspended background tabs, a sleeping screen and a wake are
  browser-side and belong under Maintenance with everything else. A device that
  reboots at 4am after an operating system update does not: it comes back to a
  lock screen with no browser running, and there is nothing left for the server
  to talk to. Relaunching a browser at a URL is kiosk mode, a launcher or
  screen pinning — a deployment instruction in the manual rather than a setting
  in the panel. Saying that plainly is better than a Maintenance page that
  quietly fails to cover it.

  **The server can force a reload and it cannot force a reboot.** Once, on the
  next poll, for a display that is alive but stuck — free, given the poll is
  there. A display that does not come back from that is one the server has no
  channel to at all, which is exactly the condition being detected, and no
  amount of server-side work reaches it. So it stops trying and raises an alert
  instead: the server does what it can and reports what it cannot. That report
  is the diagnostics entry below, which grew to meet this.

  **A scheduled server restart presumes a supervisor, and there is not one.**
  `serve.sh` launches with `setsid nohup`, and the absence of a systemd unit is
  deliberate — it is what lets this be installed without sudo. So the server
  half of Maintenance can schedule a stop and nothing would bring it back.
  Either that setting waits for a supervisor somebody opts into, or the server
  half is restricted to what does not need one. Recorded rather than designed
  around, because a Maintenance page with a restart button that ends the
  service is worse than one without.

  *Built anyway, 2026-08-17, and the third option is the one that was missing:
  it does not stop, it HANDS OVER.* At the appointed minute the server launches
  `serve.sh restart` in a session of its own and lets that script kill it —
  `stop` waits for the sockets, `start` binds a fresh process, and the helper
  outlives its parent because causing that death is what it was launched for.
  No supervisor is needed to bring the service back, because the thing bringing
  it back was started before it went away. Two guards make it safe rather than
  clever: it waits for the server to fall quiet (and a check-in is not use, or
  a building of screens would mean it never restarted at all), and a time is
  only ever acted on if it was already set when that minute arrived — which is
  what stops the fresh 03:00:04 process restarting itself in a loop and stops
  an admin typing 14:23 at 14:23 from cutting themselves off. **The residual
  risk stands and is stated in the panel**: nothing catches a `start` that
  cannot bind.

  *Panel:* a Maintenance section — retry count and interval, the nightly
  refresh window and whether it staggers, and the browser-side device
  behaviour, as a named profile picked per device the way appearance and
  screensaver already are. The server half sits with the other server settings,
  since a restart applies to one server rather than to twelve screens.

  *As built:* the profile that behaviour belongs on already existed by the time
  this was written — the kiosk profile, which is exactly "a named profile
  picked per device" and is already where full screen and the prompt line live.
  So keeping the screen awake is a tick on it rather than a fifth list, and the
  Maintenance section holds the four numbers, all of which are one server's
  business rather than one screen's.

- **Identity, in two strengths.** How somebody arrives decides what may be
  kept, because the strength of the claim and the durability of the memory
  should move together. Settled in person terms 2026-08-17, and rebuilt
  2026-08-18: there were three strengths while a PIN was optional, and a
  password is not — the enrolment link exists to collect one, so a person is
  signed in or they are not.

  | | how it arrives | retention |
  | --- | --- | --- |
  | **guest** | the bare address with no user in it — the default interface, usable, where security is not set to force the request form | none at all: no conversation, no data |
  | **user** | signed in with their email address and password | held server-side, and it follows the person to any machine they sign in on |

  **A session is a user or a device, never both, and the URL decides which.**
  A device added as a device operates as a device — a kiosk, a wall tablet —
  its URL is the place it stands in, and no person exists inside that session.
  A user's URL travels: any browser on any machine, and that session is the
  user, carrying the user's grants. What the machine underneath was approved
  for contributes nothing to it, and a person signed in is not a device that
  has been decorated.

  So the gate stops being a question about displays. `display_may()` becomes
  *may this subject reach this endpoint*, where a subject is one or the other,
  and grants add up the existing way within a kind: named directly, or named
  by a group it is in. The same rule has to reach the client, because the
  display-side drop is what keeps an utterance from being anybody's business
  in the first place.

  **People and places are separate namespaces**, and neither can be spelled in
  the other's notation: a place is `?display=<name>`, a person is a minted path,
  and there is no parameter that could carry either. One that could would be
  the list nobody could describe that groups already refused to be, and it
  would hang everything a place owns — appearance, kiosk mode, route bindings,
  session length — off a person, who has no place to hang any of it on.

  **A device is a device, so spending a person's URL on an approved display is
  refused** — at the moment it is attempted, with the screen saying so, rather
  than accepted and then quietly ignored on some later request. A kiosk is
  precisely the case signing a person in is not for, and until the middle
  ground below exists the honest answer is no. The URL is not spent by the
  refusal and still works everywhere it should.

  Below that line a person wins: a browser holding a token nobody approved is
  somebody who once looked at this page, not a screen on a wall. The precedence
  in full — a declared place name, then an approved display, then an identity,
  then an unapproved token, then a guest — is what *the URL decides which*
  turns into where a request is actually answered.

  **The user URL carries a minted, unguessable component** rather than being a
  readable name. A name is guessable, and a guessable URL that grants reach is
  a password written on a wall — the same fault that made display tokens
  necessary, arriving through the front door. The first visit exchanges it for
  a token the way a display does, so the secret leaves the address bar after
  one use and revocation has a pattern to copy.

  **Everything is created in the panel.** There is no self-registration: no
  email, no verification and nothing here to vouch for a name, so anybody who
  could mint their own identity could mint somebody else's.

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

  A **password**, with an **email address** as the login. Set by the person
  and never by an admin — the panel mints a one-shot enrolment link, they open
  it, choose a password, and the link is spent. An admin who chose it would
  know it, which is the whole reason the link exists rather than a password
  field on the row. Hashed server-side with the same PBKDF2 as the admin
  accounts and held to the same minimum length, never compared in the browser.
  Guessing backs off geometrically per account, on its own ledger so somebody
  fumbling a password cannot lock an admin out of the panel.

  **An invitation is accepted on a listener of its own**, and that is the whole
  of what it is for: the link, the page that asks for a password, and that
  password being set. No assistant, no microphone, no device enrolment — a
  browser that opens an invitation must not come away holding a display token.

  **The same link answers 404 on every other port**, which is the property that
  makes it a door rather than a hint. It used to be spendable at any bound
  listener, on the reasoning that spending a link is not an endpoint's
  business. True, and the cost was that the address in the link was a guess
  that happened to work: nothing could be firewalled to it, no deployment could
  state where people accept invitations, and anybody holding a link could
  substitute any other port they knew.

  So the port is a setting, with the interface it answers on and — optionally —
  a name to put in front of it, because an address people can read beats four
  numbers nobody checks. The name is not a second binding: the listener answers
  on the interface whatever the name says, so the name has to resolve there and
  the certificate has to carry it.

  **What a person may use is a separate question from where they accept.** It
  is a set of endpoint grants, ticked when they are invited and editable on
  their row afterwards, and it is what the acceptance page reads to tell
  somebody where to go next — computed with the same test that will be applied
  when they arrive, so every address it prints is a door that opens.

  Recovery is one gesture: reissue the link. It mints a new one, clears the
  old password, and signs out every browser that was open — a forgotten
  password and a leaked link want the same answer, and neither of them is an
  admin typing something they would then know. It comes out at the same address
  as the first, because it is read off the same endpoint.

  Signing in grants a session, measured in hours and **persistent on that
  browser**. Being asked again every half hour would end with people avoiding
  the assistants that ask.

  > **This replaced a PIN**, designed 2026-08-17 and removed 2026-08-18 along
  > with the panel's own single-PIN sign-in rung. A PIN was six digits keyed
  > into a screen: fine as a lock on a browser that had already proved who it
  > was by holding a minted URL, and not what a credential typed on a login
  > page can be. It also could not reach somebody on a machine that had never
  > seen them, which is the thing an account is for. The paragraphs above are
  > what was built in its place; the reasoning about tokens, declared names
  > and guessability above them is unchanged and still holds.

  **Session length belongs to the user**, now that a password is entered at a
  login page rather than at a screen standing in a room. The earlier design
  put it on the display, and the reasoning was right for the case it was
  written for: the place carries the risk, a workshop screen nobody but the
  workshop can reach and a reception screen in front of the street want
  opposite answers for the same person, and an admin securing a room can
  reason about that room. **That case is the deferred one below** — a
  person signing in at a device they do not own — so the per-display number
  waits there for it rather than being wrong here.

  What survives unchanged is the discipline underneath, the same as capability
  versus chrome in the embed and binding versus authentication above:
  **memory and session length are separate axes and get separate settings.**
  Collapsing them would mean choosing between forgetting what it knows about
  somebody and staying unlocked all night, when those are not the same
  question.

  Separate from the admin's own timeout for the same reason, and the units say
  so: an admin holds the configuration everybody else is looking at the results
  of and is measured in minutes, while somebody who has unlocked their own
  device is doing their work.

  Recorded plainly: this is a lightweight local account system rather than a
  small feature, and there is no directory behind it. It depends on HTTPS
  only — a password must never be enterable on the plain listener, and the
  server refuses it there rather than degrading.

  Devices and identities are listed in the admin page with when they were last
  seen, and deletable there.

  **The middle rung of the sign-in axis is gone rather than owed** — it was
  a single PIN for the whole panel, no accounts, and it was removed 2026-08-18.
  What it cost was the log: everything done behind one shared number was
  recorded as "(single PIN)", because that is all it knew. A deployment with
  one administrator is an account with one member, which is the same login
  screen without the hole in the record.

  **The token row is pulled forward** into the displays entry above, where it
  is needed to make a route binding hold rather than to make memory durable.
  What is left here is the account, and the thing signing in unlocks:
  **per-identity settings**, a storage tier that did not exist before. There is shared
  configuration, per-browser preference, and per-embed grant; a setting that
  belongs to a *person* has nowhere to live. Personal wake words are the first
  thing to need it and memory is the second.

  **Identities get a group kind of their own.** `GROUP_KINDS` is
  `("user", "device")` today, and the `user` kind — labelled *People* — holds
  display rows: the laptops and phones that arrived by opening the display
  page. It was the closest thing to grouping a person available while a refusal
  was still per device. Repurposing it is the obvious move and it is the one to
  refuse — a group's kind is fixed at creation *because changing it would
  silently empty it*, and repurposing the kind does exactly that to every
  People group at once, on upgrade, with nothing to migrate into, since no
  identity those devices belong to exists yet. So identities get their own
  kind and the existing one is relabelled to the population of personal
  *devices* it has always been. Nothing empties, and the panel stops having two
  things called People.

  **Deferred: the device shared between people that is not a community
  device.** An office laptop or a tablet several people use, as against a
  kiosk. One for one is built first — a URL is a user or a device, and the
  session is whichever one opened it — and signing a user into a commonly used
  device comes after, once there is a working thing to look at rather than a
  whiteboard. One piece is already waiting there for it: the per-display
  session length.

  *Panel:* identities, their email addresses and their one-shot enrolment
  links, per-user session length, and reissuing a link as the single recovery
  gesture on the identity list.

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

- **Diagnostics and alerting.** Technical events keyed to a device: the
  microphone would not open, transcription took four seconds, the voice service
  returned an error, this browser has no recorder. A health view per device in
  the admin page, so a failing screen can be found without anyone standing in
  front of it — and something that comes and tells you when one does.

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

  **Alerting is the second half of this entry, and it was very nearly its own
  phase.** Diagnostics is a pull — events collected, a health view somebody
  goes and looks at. An alert is a push: it comes and finds you. Those are
  genuinely different things, and the only reason they are one entry rather
  than two is that building a health view and then separately building the
  thing that watches it is two passes over the same data, with the second pass
  living entirely inside the first one's code.

  One half of it depends on none of that and could ship on its own: a device
  asking to be here is already recorded and shown by the displays entry, so
  alerting on a new request needs nothing this phase collects. It arrives
  immediately rather than in a digest, because it is the one alert here with a
  person attached to it — somebody is standing at a screen waiting to be let
  in.

  **Phase 4's outage behaviour is verified here, against a real network drop.**
  Everything four built for an unreachable server was exercised from the server
  side — the poll, the stamp, the reload channel, the handover restart, both
  states of the code clock — but the half that only a pulled cable can prove
  has never been run: a tablet losing its network, showing the line, speaking
  it once, holding a reload it must not perform while down, and reloading when
  the server answers again.

  It belongs to this phase rather than to four for the reason four shipped
  without its alert: this is where a screen that has gone quiet becomes
  something the server notices and reports, so the rig that proves the
  detection works is the same rig that proves the reporting does. Testing it
  twice, once with nothing watching, is the pass that gets skipped.

  What to run, on real hardware rather than a throttled devtools tab:

  - unplug the network at the screen — the line appears, a kiosk says it once,
    nothing else speaks
  - leave it down past a scheduled nightly refresh — no reload happens while
    it is unreachable
  - plug it back in — the line clears itself and the page reloads
  - change an appearance profile while it is down — the reload comes back
    carrying it
  - press RELOAD in the panel while it is down — it is obeyed on reconnect,
    once, and not again on the next restart

  **What already exists makes this cheaper than the entry looks.** There is no
  diagnostics, health or event endpoint in `serve.py` at all, so that part
  starts from nothing. But `last_seen` per device is already kept and already
  has a staleness check, which makes liveness nearly free once the display
  polls; and the client already computes most of the events and discards them,
  across twenty-odd `note()` sites and a round-trip timing pair that is
  measured and thrown away. A good deal of this phase is *stop discarding this*
  plus somewhere to put it.

  **An alert clears itself and still has to be acknowledged**, which is four
  states rather than two: open or resolved, acknowledged or not. The cell that
  matters is resolved-but-unacknowledged — a screen that dropped off at two in
  the morning and came back four minutes later leaves something in the list
  until a person reads it. Self-healing nobody ever hears about is
  indistinguishable from nothing having happened, and a display that heals
  itself every night is a fault rather than a success.

  **Delivery, cheapest reach first.** The admin list is the baseline and is not
  optional, because the acknowledgement model has to live somewhere. A webhook
  posting JSON is one standard-library client and reaches ntfy, Slack, Discord,
  Gotify and whatever else somebody already runs — the most reach per line of
  code available here. Home Assistant is the strongest for this deployment,
  being already connected and a thing that can speak through the house: a
  screen that dies gets announced by the building it is part of. Email is
  `smtplib` and so costs no dependency, but it wants a server and credentials
  and fails silently more often than the others, so it comes last.

  **Home Assistant as an alert sink wants its own connection entry.** It is
  currently a route's, and hanging alerting off a route means alerting
  disappears when somebody deletes that route — a surprising way to lose the
  thing that tells you a screen is dead.

  **What is worth a threshold.** Liveness, from the poll: not seen for a number
  of intervals, still absent after the one forced reload, and returned after
  being away. The speech pipeline, from the notes that currently fade: a
  microphone that will not open, a browser with no recorder at all — a fact
  rather than an event, so it fires once per device and never again —
  transcription past a number of seconds, and the neural voice falling back to
  the browser voice, which today is a note nobody on a wall is ever there to
  read and is silent degradation of the part people notice most. Routing, from
  the decision trail above: fuzzy wake matches above a rate, which is how two
  wake words cross-triggering is found at all, and `no_intent_match` above a
  rate, which is a house being asked for things it cannot do.

  **Backend latency is the exception, and has to be per route.** A Home
  Assistant intent answers in about a tenth of a second and a hosted model
  takes seconds; one threshold across both either never fires or never stops.

  **Access events belong here too, and want their own severity.** A device
  attempting a route it is not bound to — where the refusal is silent by
  design, so repetition is the only signal that exists — and the admin sign-in
  back-off engaging. Both are here because there is nowhere else for them, and
  neither should sit at the same weight as a slow transcription.

  **Quiet hours, on the device clock, for the same reason dark hours are.**
  Announcing a dead hallway screen through the house speakers at three in the
  morning is how alerting gets switched off in its first week.

  *Panel:* health per display and the conversation record, alongside the entry
  that already lists them; retention window; deletion. Alert channels and which
  severities each carries; per alert, whether it is on, its threshold, its
  severity, and whether it arrives immediately or in a digest; quiet hours.
- **The embed, once there is an identity to attach to it.** The memoryless
  embed shipped first, deliberately: it is exactly the `named, not signed in → no
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

