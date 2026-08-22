# Todo

Open questions and work not yet started. Each entry says what is wrong, what
has to be decided before it can be built, and what was actually found in the
code — so the next person to pick it up is not starting the investigation
again.

---

## 1 · Building up embeds

**Putting it on somebody else's web page is built** — see
`docs/embedding.md`. What is here is what that round deliberately did not do,
and one correction to what this section used to claim.

**The correction.** This section previously said the embed had "a message API
in both directions — out: `ready`, `status`, `learned`; in: `settings`,
`routes`, `hello`, and `cmd` over six commands". That was never the embed
channel. It is the PREVIEW channel, which is the admin panel driving the
display in its own iframe, and no embed can reach any of it. Anybody scoping
this from that paragraph was starting from an inventory of things that do not
exist — which is worth remembering next time a list like it is written from
memory rather than from the code.

What the host channel actually carries, now: out `ready`, `narrowed`,
`renewed`, each with the grant and when the session ends; in `narrow` and
`renew`. `embed.js` handles the second of those, so a host only writes one if
they are doing without the loader.

Still open, each of which is a different product:

- **A host cannot ask a question and get the answer back.** It can frame the
  interface and narrow it, and that is all. It cannot put a question in, read
  the transcript, or be told a turn finished — so a page can host the
  assistant but an application cannot integrate with it.

  Worth being clear about what such an API would be FOR before building it.
  The host's server can already `POST /ask` itself. What it cannot do is join
  the conversation the frame is having — the history, the endpoint's own
  conversation id, the route the wake word bound, the voice, the transcript —
  all of which live in that page. So the feature is "ask into this
  conversation", not "reach the model", and if it is documented as the second
  every integrator will build the wrong thing.

- **No events reach the host.** Nothing for a turn starting, a wake word
  firing, an error, or the microphone being refused — all of which the page
  already knows and records against `EVENT_KINDS`.

- **Reading the transcript wants its own capability.** Everything on the cap
  axis today is what a host may DO — ask, mic, speak. Reading is what it may
  KNOW, and on a `kiosk` key that is whatever was said near a hands-free
  microphone in a lobby. It should be a fourth bit rather than folded into
  `ask`, and the same question applies more quietly to events: `wake_fuzzy`
  carries the near-miss word that was heard in the room.

- **The model is not told who is asking.** A key can now require the host to
  name the person, and it reaches the session, the rate window and the ledger
  — but not the assistant. Forwarding it means putting a real name into a
  system prompt, and on a hosted provider that means sending it off the box,
  which for a product whose first constraint is "nothing goes to a third
  party" is its own switch and its own decision. Not an oversight.

- **Roles gate nothing.** They are recorded and otherwise inert. Gating an
  endpoint on a role is the obvious next thing and was deliberately left.

- **Appearance is the deployment's, not the embed's.** An embed renders what
  the shared settings and profiles say. Whether a host should be able to hand
  over a palette or name an appearance profile is undecided, and it is the
  difference between an embed being *this* assistant on somebody else's page
  and being a component.

- **Nothing is versioned.** `rsn: 1` is a marker, not a negotiation: nothing
  advertises which kinds this server understands, so the day one changes shape
  a host has no way to tell which it is talking to. Cheapest to fix on the
  `ready` message, and cheaper still before there are integrations in the
  wild.

---

## 2 · The certificate, and what it still does not cover

**Done, for the internal network.** An internal CA now issues it, and browsers
with the root installed reach every listener with no warning at all.

```
subject   CN = *.server.example.internal
issuer    CN = <your internal CA>            (an internal CA, not self-signed)
valid     21 Aug 2026 → 21 Aug 2027
SAN       DNS:*.server.example.internal         — and nothing else
```

`https://ai.server.example.internal:9701` loads clean. The panel, the assistants and
the enrolment page can all be opened, driven and screenshotted, so the tooling
gap that made the enrolment gate ship with two attributes unset is closed.

**Three things the SAN does not carry**, each verified against a browser rather
than reasoned about:

- **The IP.** `https://10.1.153.21:9701` still warns — there is no IP in the
  SAN. Every bookmark, every *Address in the link*, and the embed address must
  be a name. Anybody still using the IP sees exactly the warning this work was
  meant to remove, and will reasonably conclude nothing changed.
- **The bare domain.** `*.server.example.internal` does not match `server.example.internal` —
  a wildcard matches one label, never its own parent. `ai.server.example.internal`
  works; `server.example.internal` warns.
- **A second level.** `a.b.server.example.internal` is two labels down and is not
  covered either.

**And it is a private CA on a `.lan` domain**, which decides what an embed can
be. A host application whose users' machines carry <your internal CA> gets an embed
that simply works. Anything outside that — a public website, a contractor's
laptop, somebody's phone off the VPN — gets a blank iframe with nothing in the
console naming the cause, because `.lan` does not resolve on the internet and
nothing out there trusts this root. That is the right answer for six internal
tools and not an answer at all for a public one, and the two are worth not
confusing when the next application is added.

**What is left:**

- **A public certificate**, if any embed is ever to sit on a public site. A
  real domain that resolves to this server, and a renewal path.
- **A renewal that is not a diary entry.** This one expires 21 Aug 2027 and
  nothing will say so. It is a year of not thinking about it followed by every
  listener failing at once.
- **`make-cert.sh` is now beside the point** for this deployment and still
  takes one host, so anybody falling back to it lands in the old situation
  without noticing. Worth either teaching it several names or saying plainly
  at the top that the CA is where certificates come from here.

---

## 3 · Password rules an admin can set

**There is one rule and it is a constant.** `MIN_PASSWORD = 10`, in
`serve.py`, and length is the whole of it — nothing asks for a mix of cases, a
digit, a symbol, or anything a password is not. A deployment with a policy to
meet cannot say so, and one that wants something laxer for a house full of
tablets cannot say that either.

What is actually there today:

- **One number for both populations, deliberately.** `password_fault()` says so
  in as many words: "there is one rule in this product for how long a password
  has to be, and a second number for a second population would be two answers
  to one question." It judges a person's password; the panel's own accounts are
  judged by two separate `len(new) < MIN_PASSWORD` tests in the admin routes.
- **So the rule is written out three times.** `password_fault()` for people,
  and twice more where an admin account's password is set or changed. A fourth
  rule added to only one of them is a rule that applies to some passwords.
- **The panel is told the number** — `pw_min` rides along with the identities
  payload — so whatever is chosen has somewhere to be shown without a second
  fetch.
- **512 is the ceiling**, and it is not a policy: it is there so a hash is not
  computed over a megabyte somebody pasted.

**To decide first**, and each answer is a different amount of work:

- **A length, or a policy?** A number in a box is one setting and covers most
  of what a deployment is asked to prove. Character classes are four more
  ticks, and they are the part security guidance has been moving away from for
  a decade — worth deciding on purpose rather than adding because a form
  usually has them.
- **One rule or two?** The comment above is a decision already taken, and a
  panel account and a hallway sign-in are genuinely different risks. Changing
  it means saying why the earlier reasoning no longer holds.
- **What happens to passwords that already exist.** Raising the minimum cannot
  retroactively refuse them: they are hashes, and the length is unknowable. So
  either the rule applies at the next change only — quiet, and leaves weak
  passwords in place — or somebody has to be forced to set a new one, which is
  a mechanism this product does not have.
- **Where it is said.** The rule has to reach the person choosing a password,
  on a page they open from a one-shot link, or they find out by being refused.

Whatever it becomes, it should be **one place that answers "is this password
allowed"**, called by all three sites — the value is a setting, the judgement
is not three copies of an `if`.

---

## 4 · Home Assistant, and ending a conversation properly

**Reported 2026-08-21 and not yet reproduced in detail** — what is written here
is what the code does today, so whoever picks it up starts from the mechanism
rather than from the complaint.

**HA holds the conversation and this server holds nothing.** `ask_homeassistant`
sends `{text, conversation_id, agent_id}` and no history, no system prompt and
no limits: the conversation lives in HA against that id, and the panel hides
those fields on purpose. So "ending a conversation" is two things at once — the
display's awake window, and the id HA is still holding — and only one of them
is ours.

**Where the id is dropped, today:**

- `sleepNow()` — the sleep word, or the awake window running out — calls
  `forgetConversation()` and clears `Wake.convo`.
- switching endpoints mid-conversation clears it, at `index.html` where
  `switching` is true.
- and that is all. **Nothing tells HA.** The id is simply not sent again, which
  leaves whatever HA keeps against it to HA's own expiry.

**`continue_conversation` is read and deliberately ignored**, and the reasoning
is worth reading before changing it: acting on `false` was tried for one day and
measured on the first real installation — the display went silently to sleep
after each command, five further utterances were transcribed and dropped at the
wake gate, and the person concluded it had locked up. Staying awake is what
makes the house behave like every other endpoint. **So if the fault is that a
conversation does not end, the answer is probably not to start honouring that
flag.**

**What to find out first, on the wall display rather than by reasoning:**

- **What actually fails.** A conversation that will not end, one that ends too
  early, or one that ends here and stays open in HA — three different faults
  with three different fixes, and the note this entry came from does not say
  which.
- **Whether the id outlives what it should.** A display asleep for an hour and
  then woken sends no id — but a person walking up mid-window continues
  somebody else's conversation, which is the same leak `forgetConversation`
  exists to prevent on the transcript side.
- **Whether HA should be told.** There is no "end this conversation" call in
  the adapter, and HA's own timeout is the only thing closing them. Whether
  that matters is a question for a real installation with a real agent behind
  it.
