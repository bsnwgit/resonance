# Progress log

Newest first. The reasoning behind each change, kept so it is not
rediscovered. For what is planned rather than done, see [Roadmap](roadmap.md).

Newest first.

## 2026-08-23 — the panel answers about the application it is sitting in

An embed put this interface on somebody else's page and left it able to talk
about anything except the thing the person was looking at. Now it reaches
their data — but the design question was never "how do we fetch it", it was
**who makes the request**.

- **The browser does, not this server.** Calling their API from here would need
  a service credential on every application (one account for everybody,
  necessarily holding more than any single visitor should see), network reach
  into places that have never accepted an inbound connection, and a schema per
  customer forever. The panel is already framed inside a page authenticated as
  that person, so the call is made there, same-origin, with their own session.
  This server holds no secret of theirs and reaches nothing. The cost is that
  the loop runs *through* a request rather than inside one — `/ask` answers
  with `tool_call` instead of `reply`, the frame performs it through the host
  page, and the same question comes back with `tool_results`.
- **Three authorities, narrowest wins.** The application declares a ceiling in
  a grant file it serves itself; the admin ticks within it; the visitor's own
  login caps whatever survives. The data's owner sets the outer bound and only
  they can raise it, which is what makes this safe to embed in an application
  somebody else runs. **No grant file means reads only** — silence never grants
  a write.
- **Writing is declared, never inferred.** Applications change things behind a
  `GET` and run searches over `POST`; the verb is a hint about neither. The one
  place a verb is trusted is the absence of a grant file, and it is trusted in
  the safe direction.
- **Nothing app-specific is in this server.** It reads an OpenAPI document and
  grants against `operationId` — the one identifier meant to be stable. A grant
  naming a path would follow the next refactor onto a different operation and
  keep working, which is the worst way for a permission to fail.
- **The spec must sit on a registered origin.** Not tidiness: a URL an admin
  can type is a URL this server will fetch, and without the check the field
  reaches every address on this machine's network.
- **The model's output is untrusted input.** An invented operation, a renamed
  parameter, a path segment stuffed with a slash — ordinary failure modes of a
  model, all of which would otherwise arrive at somebody's API as a request
  their page made in their name. Every proposed call is resolved and checked
  here, and `embed.js` checks again at the far end against the operations the
  session declared, so a tampered frame still reaches only the declared paths.
- **A write stops and asks, per action.** The confirmation is drawn by the
  frame rather than the host page — a confirmation rendered by the party that
  wants the action is not one — and names the real values, because a voice
  interface has no address bar to check. There is no session-wide "allow
  writes": that is the same hole with one more click in front of it.
- **Four laps, then it stops.** A model that has misread its tools will call
  the same one for ever, and every lap is a request through somebody's page.

Verified end to end in a browser against a stand-in application: a question
about data not on screen, answered from that application's own search
endpoint; and a write held at a confirmation, taken by voice, and then
performed.

## 2026-08-23 — the sink carries the whole log, not a tenth of it

Syslog was an alert destination. A collector watching this server saw a
screen's microphone fail and could not see the restart before it, the migration
that ran, the failed sign-in, or the request that threw a traceback a second
earlier. Half a picture in the one place an operator actually watches is worse
than none, because it reads as the whole of it.

- **Everything the process prints goes to the sink while it is on.** The
  startup banner, the migrations, the request log, every `print` in the file
  and Python's own tracebacks.
- **Done at the stream, not at the call sites.** `sys.stdout` and `sys.stderr`
  are wrapped in a tee that writes through and mirrors whole lines. There are
  over a hundred `print` calls here, each one a sentence written for a person
  reading `server.log`; routing them through a logging framework would mean
  editing every one, and the first one anybody forgot would be invisible in
  exactly the way this exists to fix. Wrapping the stream makes "all of it"
  true by construction, including whatever is added next.
- **Stdout is `info` and stderr is `err`**, which is what makes the severity
  worth anything at the far end — and why the request log moved to stdout. It
  was the one thing on stderr that is not a fault, and left there it would have
  filed every 200 OK under error. Same file on disk either way: `serve.sh`
  redirects both.
- **The settings are read once a second rather than once a line.**
  `display_settings()` reads and parses `displays.json` every time it is asked,
  which is fine at one call per alert and is a file read per request now. A
  second is short enough that switching the sink on in the panel takes effect
  while you are still looking at it.
- **`Send` governs both.** The severity floor was already there for alerts and
  now decides how much of the log travels too — `everything` ships by default,
  and `errors only` is the answer to a noisy collector rather than switching
  the sink off and losing the alerts as well.
- **Never a second fault.** The mirror is inside the existing fire-and-forget
  sender, which swallows every failure, and it carries a per-thread re-entry
  guard: a mirror that can recurse into itself is one bad edit away from taking
  the server down.

## 2026-08-23 — the panel's controls moved under its field

An embed panel is 400 points wide by default. The composer is one row —
caret, field, buttons — which is right on a display, where it is a line across
the bottom of a whole screen and the field has more width than anybody types
into. In the panel that same row left the field about ninety points: four
buttons and a caret took the rest, and a text field you cannot read your own
sentence in is not a text field. It is also the part of a panel people
actually use.

- **The buttons take a line of their own beneath the field**, in an embed
  only — a display and a wall screen are untouched. `flex-basis:100%` on the
  button group is the whole of it: the caret and the field are earlier in the
  row and keep the first line, so the field gets the width back with no
  wrapper element and no second markup for the embed to drift out of step
  with.
- **Right-aligned, where they already were.** The row grew a line; it did not
  move. Said on the group rather than on the bar, because a full-width line
  ignores its parent's justification — which also keeps it true for a key
  granted no input part, where the buttons are the only thing in the composer
  and the row stays a single line.

## 2026-08-23 — a site is something you maintain, not something you reissue

An embed key's settings were fixed at creation. The stated reason was sound —
somebody's page is already framing it, and widening a key from the panel
changes what that page can do without anybody at that end knowing — but the
only remedy it left was *make another key and delete this one*, and that is a
**new id**. Every authorize profile that had ticked the old one silently stops
naming anything, the far end is sent a credential and wires it in again, and
all of it to correct a hostname somebody typed wrong. The risk was named
correctly and charged to the wrong party.

- **A row under ACCESS ▸ SITES is an editing surface**, carrying the same six
  sections the key was made in. `POST /embeds/update` rewrites the record in
  place: same id, same secret, same grants. Nothing at the far end is sent
  anything and no permission stops naming it.
- **A narrowed key takes its live sessions with it.** This is what the old rule
  was actually asking for. A session token carries the parts, the capability
  and the origins it was minted with, so a key narrowed while its sessions ran
  would be narrower on paper only, for up to a day. Move any of those, the
  session length, or whether the host must name the person, and every session
  that key holds is dropped — the pages framing it mount again within a moment,
  inside the new envelope. A rename drops nothing, because taking somebody's
  page dark to correct a spelling is not a trade worth making.
- **One validator for create and edit.** An edit cannot reach a record a create
  could not have produced — the same coherence rules, the same origin parsing,
  the same ranges, in the same words. What an edit may not touch is the secret
  (REISSUE KEY is the button for that), the audit fields, and `enabled`, which
  has a button of its own: a form carrying it would put a site back on the air
  as a side effect of saving a rename.
- **The row stopped printing what it can now set.** May, Draws, Frames, Session
  and Asking were read out as text because they could not be anything else.
  They are fields now; printing them twice on one row would leave an admin
  editing one copy and reading the other. What stays is the three an edit
  cannot reach — Reaches, Last used, Made.
- **REVERT and SAVE beside DELETE**, on the right of the action bar with the
  spacer between, the way an endpoint's block already splits *what operates it*
  from *what writes to it*. Both dark until the fields have been touched.

## 2026-08-21 — the assistant on somebody else's web page

Embeds existed as a way to frame this interface. This is the round that makes
one droppable into a running web application: one endpoint on their server,
one tag in their template, and a bubble in the corner of every page.

The shape was settled first, out loud, against one stated principle — *assume
it is always facing an insecure network* — and most of the work below follows
from that rather than from the feature request.

- **An embed session is a vetted caller.** It satisfies an assistant's "no
  anonymous callers" on the same reasoning a code-enrolled screen does: an
  admin made the key, named it, chose what it may do, and can revoke it. This
  is the one that matters. An embed means the server is reachable by every
  visitor's browser, which for a public site means the internet — and
  `/ask` was open to anyone who found the port, key or no key. Requiring a
  sign-in was the existing answer and it could not be used, because ticking it
  took every embed down along with the strangers it was aimed at. Now it does
  not, so the door can actually be shut.
- **A one-use code in the URL, never the session token.** The token is a
  bearer credential and it was sitting in an iframe's `src` inside somebody
  else's page — readable by their scripts, their analytics, their error
  reporter, the history and any screenshot. The allow-list does not help: it
  stops another site *framing* this and does nothing against `curl`. The URL
  now carries a code good once and for a minute; the frame trades it at load
  and the token exists only in that page's memory.
- **One session per visitor, with its own rate window.** The key's number is
  the application's total and the bill; a second, smaller one is a browser's
  share. One number could not say both — sized for a busy application it is a
  number one visitor can spend alone. Where the key names the person the
  window follows *them*, so reloading buys nothing. Neither number was
  settable from the panel before; both are now.
- **A key can require the host to name who is asking**, off by default. Their
  server asserts it, never their browser — they authenticated the person and
  hold the key, and a browser saying who it is would be a text field. Required
  means the code request is *refused* without it, so a host that forgets finds
  out on the afternoon they wire it up rather than months later through an
  audit trail full of nobody. Those turns are recorded against the key and the
  person; where a key does not name people, nothing is recorded at all.
- **`embed.js`** — the loader, served from here and running in their page.
  Fetches a code from their own endpoint, frames this with
  `allow="microphone"` set for them, draws the launcher and panel, and renews
  the session. Six applications hand-writing the same forty lines is six
  chances to get the microphone attribute, the message-origin check or the
  renewal subtly wrong, and five of those fail silently. Shadow DOM, closed,
  because this markup lands in pages whose CSS nobody here has seen.
- **Renewal does not reload.** The loader posts a fresh code in and the frame
  swaps its token behind the scenes. Pointing the frame at a new URL would
  have been correct and would have thrown away the conversation, which from
  the other side of the screen is the assistant forgetting the last ten
  minutes for no reason anybody can see.
- **The panel writes the integration.** Creating a key produces working Node,
  Python and PHP for their endpoint and the tag for their page, against an
  address an admin sets — and shaped by the key, so a token that does not
  require a person has no user block in its snippet. The key is *not* in the
  generated code: it is read from `RESONANCE_KEY`, so the snippet can go in a
  chat message and the credential cannot.

Two things found on the way that were not part of the job:

- **`turns.json`, `events.json`, `identities.json` and `alerts.json` were not
  in `.gitignore`.** They hold verbatim conversation text, sign-in records and
  the people who can sign in. Nothing had committed them yet; one `git add -A`
  on a machine where they existed would have. Added, and listed in
  CONTRIBUTING beside the credentials.
- **TODO §1's inventory of the embed message API was describing the preview
  channel** — the admin panel driving the display in its own iframe — which no
  embed can reach. Anybody scoping from it was starting from a list of things
  that do not exist. Corrected in place, with the correction left visible.

**What this does not do**, and none of it by accident: a host still cannot ask
a question and receive the answer, no events reach it, roles are recorded but
gate nothing, the model is not told who is asking, and a *restricted* endpoint
refuses every embed because an allow-list names screens and people. Each is
argued in TODO §1.

**And it cannot be deployed off this machine until the certificate is real.**
A browser will not quietly load an iframe from a certificate it does not
trust, and inside an iframe there is no warning to click past — the frame is
blank for every visitor, with nothing in the console that names the cause. See
TODO §2.

## 2026-08-20 — the door, the clock, and one queue for everybody waiting

A session's worth of work on the two ends of a deployment: who gets in, and
what a screen carries while nobody is talking to it.

- **A personal link opens wherever it is sent.** `/p/` refused an invitation on
  any browser holding a display token — and a display token is scoped per host
  rather than per port, so the browser certain to be carrying one was the panel's
  own. The check only ever fired on the enrolment listener, where invitations
  are the entire point, so it went.
- **One queue for everybody who is not in yet**, chipped ENROLL or FORM. The
  people an admin named and the people who asked from a screen were two boxes
  that asked you to know the difference before you could find either; the chip
  says which a row is, which was the whole of what the split was telling you. A
  refusal now leaves that queue and lands in the log, reason and note included.
- **What an assistant is called moved to its voice.** The wake and sleep words
  sat on the layout for an afternoon; a layout is what an endpoint LOOKS like,
  and what it is called is part of how it sounds — so both live on the speech
  profile the layout names, edited once for every endpoint wearing it.
- **A screen can carry the date and time**, ticked per layout, formatted once
  for the deployment under SETTINGS ▸ ADMIN. It reads the device's clock, turns
  over on the minute, and rides the screensaver rather than vanishing into it —
  painted into the canvas so it travels with the figure instead of burning in.
- **Signing out exists.** A button that names who it is about, and an optional
  spoken phrase that is nobody's default. It ends this screen's session and no
  other: `close_one_session` draws the line that `close_user_sessions` — account
  recovery — deliberately does not.
- **A session ends when the browser goes.** The cookie is a session cookie, a
  closing tab starts a fifteen-second countdown that a reload cancels, and three
  minutes of silence ends one regardless. The last is the only mechanism that
  survives a crash, and the first two are what make it immediate.
- **A logging catalog.** Everything was captured and everything was kept; now
  each kind can be switched off, at capture, and with the sink on every event is
  forwarded as it happens rather than only the ones crossing an alert threshold.
  The door is in the catalog too — signed in, and sign-in refused.
- **A signed-in person is never asked to sign in again.** The gate asked whether
  any endpoint was usable and never whether somebody had already answered it, so
  a missing grant wore the costume of a broken login. It now names the assistant
  and says whose decision it is.

## 2026-08-19 — nothing stands in for a choice nobody made

Two threads, and they turned out to be the same one. Every list in the panel
had a nominated DEFAULT, and every figure on the wall was a variation on the
same figure. Both were things the deployment decided on an admin's behalf.

- **The five nominated defaults are gone** — appearance, geometry, speech,
  models and layout profiles. A row naming nothing is not quietly handed
  somebody else's profile: an endpoint with no model profile is on `demo` and
  says so, a route with no speech profile speaks in the page's own voice, a
  screen with no appearance profile shows what the page ships with. What made
  them worth removing rather than merely defaulting to empty is that they
  **recreated themselves**: a default pointing at a deleted profile silently
  re-pointed at the first in the list, and an empty list invented a profile
  called *Default* out of whatever the tab happened to be showing. Clearing one
  was not something the panel could express.
- **There is no shared appearance document.** It was the other half of the same
  arrangement — the thing a screen fell into when it named nothing. A display's
  settings now have the keys those three tabs own dropped out of them on the
  way to it, so the tabs are a workbench and a profile is what reaches a
  screen. The panel publishes which key belongs to which tab, because the panel
  is the only thing that knows.
- **RIDGE was STACK with a post-process, twice.** First it was the same layered
  polylines rectified and folded; then, after that was rebuilt as vertical
  bars, it was the same signal drawn a different way and still not what was
  asked for. What it is now is a mesh a few hundred rows deep, rectified into a
  landform above its own exact reflection, held at a FIXED angle — the only
  figure here that does not turn — and run edge to edge by taking its span from
  the canvas rather than from the Spread slider. The lesson was not about
  geometry: **a figure is separated from another figure by its topology, not by
  what is done to it afterwards.**
- **STACK went**, since RIDGE stopped being a fold of it. Stored settings still
  name it, so `RETIRED_MODES` rewrites it on the way out, and the builder
  dispatch became a named map with a fallback — the old `?:` chain ended in
  `buildKnot`, so a retired mode drew a KNOT and looked like a bug in KNOT.
- **DNA**, a sixth figure and the first built out of parts: a sphere per base,
  a rod to the axis, and no backbone drawn at all. Three attempts, and the
  first two failed for the same reason — a continuous stroke down the strand is
  what makes a helix read as wire in a spiral. The chain of spheres carries the
  eye instead. The spheres are camera-facing filled spirals rather than
  wireframe rings, because this renderer only strokes lines and a ball drawn as
  rings looks like a ball drawn as rings.
- **A screen with its microphone open could never reach its screensaver.**
  `Mic.start` set `Drive.phase = 'speaking'` and left it there, and the idle
  clock only advances while the phase is `idle`. It was doing nothing for the
  geometry either — `Drive.step` ignores the phase entirely whenever the mic is
  feeding it. Opening a microphone is not the display speaking.

  **It came back on 2026-08-20 by a different route**, which is what settled the
  design. Fixing the caller left the clock still reading a flag that five other
  places set, and any one of them returning early reproduced the symptom exactly
  — an open microphone, no conversation, and a screen that never drifts again.
  A flag that says what the figure should draw is not an answer to whether
  anybody is here. The clock asks what is happening now instead.
- **The figure now goes quiet while the assistant is asleep**, so the
  screensaver reads as one. The gate is on what the mic SHOWS and not on what
  it hears: the first attempt put it at the top of `Mic.step` as an early
  return, which took the voice-activity detector and the recorder with it and
  stopped the display hearing its own name.
- **A layout profile can say *listen from the moment it loads*.** A wall
  screen has nobody to press TALK, and every reload left it deaf. It is a
  request rather than a guarantee — the browser decides — so a refusal falls
  back to the first touch, which is the same touch that asks for full screen.
- **An endpoint can hand a layout profile to the screens it names**, and a
  screen's own choice always wins. Only endpoints that NAME it, and only when
  the answer is unambiguous: a screen can be granted several endpoints, so it
  can have several parents, and two that disagree resolve to nothing rather
  than to whichever the code happened to reach first. That tie-break is the
  same one that once put two assistants on one port.
- **Full screen cannot survive a reload and no setting can change that.**
  Leaving it on navigation is in the specification and the request needs a
  gesture. The panel says so and gives the command that does work — the browser
  started in kiosk mode, which is a window state rather than a page permission.

## 2026-08-19 — a review that found what testing had not

A read of everything the day before had changed, looking for dead code and
faults rather than waiting for them to surface. It found five, three of which
would have been reported eventually as "it does not work" with no clue why.

- **User passwords were not rate limited at all.** `verify_identity_password`
  called `note_login_failure` — the PANEL's ledger, keyed by client address —
  instead of `note_user_login_failure`. Failures went into a map nothing reads
  for people, so `user_login_blocked` never became true and the back-off that
  makes a password survivable was never charged. A rename with one caller left
  behind, and the two names being one word apart is exactly why they now are
  not.
- **The whole request-to-account path was dead.** `req_email` and `setup` were
  written onto a display record but were not in `DISPLAY_DEFAULTS`, and
  `read_displays` rebuilds every record from those keys and drops the rest. So
  both evaporated on the next read: approving a request found no address and
  quietly approved a DEVICE, and the requester's screen never learned there was
  a password to set. Nothing errored.
- **An enrolment link could name a port nothing listens on.** With no
  nominated profile, the link's base took the first profile with a port — and
  a profile no endpoint has been given is never bound. The link is built from a
  profile that is actually carrying something now, and returns empty rather
  than a URL with port 0 in it when there is nothing bound at all.
- **A dropped `/routes` fetch told a working screen it was unconfigured.** The
  new "nothing is set up on this port" state tested an empty list, and an empty
  list is also what a failed load leaves behind. It tests whether the list has
  ever arrived.
- **Approving a request minted a link and never mailed it**, unlike creating
  or reissuing one — and the `mailed` flag the server returned was read by
  nothing, so the panel could not say either way.

Dead code out with it: an uncalled `_blank_routes`, an unused `base64` import,
four CSS rules for elements and classes that no longer exist, and a comment
claiming two settings keys were consulted by a function that had stopped
consulting them.

Also: **the sign-in box is documented properly**, because two different
settings produce it and only one of them is called *Sign in* — an endpoint left
at NOT REQUIRED still shows one to a browser its allow-list does not cover.
There is a table. And **syslog lines carry a name you choose**, in a real RFC
3164 header, so a collector's source column reads as something recognisable
rather than as an address.

## 2026-08-18 — accounts, and authentication moved onto the assistant

Phase 5, built and then rebuilt in a day: the PIN it was designed around went,
and where authentication is decided moved twice before it settled on the thing
being reached.

- **The PIN is gone, in both places it existed.** A person's PIN and the
  panel's own single-PIN sign-in rung were removed together. A PIN was six
  digits keyed into a screen — fine as a lock on a browser that had already
  proved itself by holding a minted URL, and not what a credential typed on a
  login page can be. It also could not reach somebody at a machine that had
  never seen them, which is the thing an account is for. The panel's rung cost
  the log: everything behind one shared number was recorded as "(single PIN)".
- **A person is an email address and a password they set themselves.** The
  panel mints a one-shot enrolment link; opening it forces a password and
  spends the link. An admin never sets or sees one — reissuing the link is the
  single recovery gesture, and it clears the password and signs out every open
  browser. `identities.json` was not migrated: a row from the old model has a
  PIN hash and no address, which is an account nobody can sign in to.
- **The display gate is one question at a time.** It stacked three forms at
  once and asked whoever was standing there to work out which was theirs. It
  is now sign-in, with *Use Code Instead* and *Request Access* as links that
  swap the box for the thing they name. Password-and-confirm appears in
  exactly one place: the setup screen off an enrolment link.
- **A request is for an ACCOUNT, not for a device.** Approving one creates the
  person and mints the link rather than turning a browser into a screen on the
  wall; the form asks for an email above whatever fields an admin defined, and
  the requester's own page is sent to the password box the moment you approve.
- **The panel always asks for a password.** The setting that could open it is
  gone — a switch that opens an admin interface is a switch somebody leaves
  on, and "the network is the boundary" holds until the machine joins another
  network. `ensure_first_admin` runs unconditionally, so no install can reach
  a state where the panel is locked and no key was ever cut.
- **Sign-in became a property of the assistant.** There is no deployment-wide
  switch in either direction. Each endpoint carries its own *Sign in* section,
  because three assistants on one box can want three answers and one switch
  covering all of them could only ever be set to the strictest. REQUIRED means
  **no anonymous caller** — somebody signed in, or a screen enrolled with a
  code, because minting that code and carrying it to the device is the same act
  of vouching a password is. A browser that merely opened the display page is
  neither.

  It refused a device outright until 2026-08-20, and that was the setting
  turning away the population it is most often wanted for: an admin hangs a
  hallway screen, ticks the endpoint onto it, and the grant reaches nothing —
  because being approved is exactly what made it a device, and a device could
  never sign in. The question is whether the caller is KNOWN; a code is how a
  screen becomes known. The trade is that a wall satisfying it has no person
  attached, so it limits a model to callers you vetted rather than attributing
  the bill to a name.
- **A port carries one endpoint, and no port means no port.** Sharing went
  with the sign-in requirement — a door with two assistants behind it can only
  have one lock and would answer for the looser of them. The nominated default
  that collected endpoints naming nothing went with it: two endpoints that had
  simply never been given a port both landed there, chosen by nobody, which is
  the collision the rule could not see.
- **Two holes closed, one of them mine.** A network profile marked *the port
  is the grant* short-circuited the permission test entirely, so an endpoint
  requiring a sign-in quietly required nothing; the flag is gone rather than
  patched. And `_identity` fell back to the setup cookie wherever sign-in was
  off, which would have let an endpoint insisting on a person accept a cookie
  nobody proved — identity now resolves only from a session.
- **The posture warning stopped being shown on displays.** The reason it was
  safe was written beside it: anyone reading it could open the admin port and
  find out anyway. That expired the day the panel started always asking, and a
  description of a server's exposure is not something to hand to every browser
  that loads a screen. It is still said at startup and in the panel.
- **A stray `@property` cost an hour.** Removing `pinned_open` left its
  decorator on the method below, turning `_redirected` into a bool and killing
  every request that called it — the panel sat on "saving…" forever.
  `check.sh` and pyflakes both passed it: a stray decorator is valid Python
  with valid names. Parse-clean is not the same as working.
- **RIDGE**, a fourth visualiser form: the same signal folded into a landform
  above its own reflection.

## 2026-08-18 — a page that did not parse

Not a phase. One statement in the wrong place, and the display page stopped
running entirely — found by opening it on a machine that had not had it open
before.

- **A note gained a second line and took the whole page with it.** The wake-word
  instrumentation added an `Events.add` under `if (h.fuzzy)`, which carried no
  braces because it had only ever held one statement. The new call landed
  outside the body, the `else if` below it lost the `if` it belonged to, and
  the script stopped parsing.
- **It did not look like a syntax error.** An inline script that does not parse
  is not a broken feature — it is a page where NOTHING runs. What a browser
  showed was the static markup alone: the composer and the buttons beside it,
  over an empty frame. No visualiser, no enrolment code box, no request form,
  no PIN box. Four unrelated things missing at once is a shape worth knowing,
  because it points at the parser rather than at any of the four.
- **It survived a deploy because nothing reads these files.** The zero-build-step
  decision is right and it costs this: between saving and a browser, no parser
  sees the page. Hence `check.sh` — both pages' scripts through node, both
  modules through Python, line numbers mapped back onto the HTML file, and a
  missing parser is a failure rather than a skip. It cannot tell you the page
  works; it can tell you it runs.
- **Every brace-less body in both pages was swept for the same shape** — a
  second statement sitting after the one the header owns. This was the only
  one. Of the seven other `Events.add` sites that commit added, six sit inside
  braces and the seventh, `stt_slow`, is a brace-less `if` holding a single
  statement, which is the shape that is safe: what follows it sits at the
  header's indent, not at the body's.

## 2026-08-17 — the panel stopped being a filing cabinet

Not a phase. A day of using the thing and finding that the administration side
had been arranged by what was built when, rather than by what somebody does.

- **The enrolment flow had a half missing.** An admin could mint a code; the
  screen it was for offered no way to use one. The only path was typing
  `/e/CODE` into an address bar — fine for a television with a remote, and the
  long way round for a screen already showing this page. Worse where guest
  requests are off: an unapproved screen drew nothing at all, so a device
  somebody had just made a code for had no path forward of any kind.
- **The code was minted on one tab and displayed on another.** Pressing GET A
  CODE showed nothing where you were standing, and the complaint about a
  missing name was written on the way out and never taken back — so a press
  that worked looked exactly like a press that failed. Rows accumulated in the
  register that nobody knew they had made, holding live codes, on a page
  nobody had been sent to.
- **"9 min left" was a lie for nine minutes.** A code is the one thing on a row
  that spends itself while you read it, so it is a clock now rather than a
  sentence — and how long it runs for is a setting, which can be switched off.
- **One register became four lists on three tabs.** Two questions decide which:
  is it working, and is it a person or a machine. An arrival is a job somebody
  has to do; a working row is a thing they look up; and a person who filled in
  a form has nothing in common with a screen an admin minted a code for except
  where they both end up.
- **Everything that starts working is filed with its own population.** A row in
  no group is a row an allow-list cannot name, so every grant had to be made
  one device at a time — which is the data entry a group exists to remove.
- **The bar says which of two subjects you are in.** Configuring the server,
  and how something comes to be here. Two titles, boxed, each with its own way
  into the manual, and a gap between them doing the work a fifth link would
  have done badly.
- **A network profile is an address and a port**, not just a port. The picker
  offers what the machine actually has, each with the interface carrying it,
  read from the kernel rather than by shelling out or taking a dependency for
  a list of addresses. The port is tried before anything is allowed to use it:
  on one address it must be free there, on ANY it is allowed if even one
  address can carry it. Two profiles may share a port on different addresses,
  because the machine can.
- **Which came with two bugs of its own, in one afternoon.** The check ran over
  every profile the panel sent, so editing one row was refused by the state of
  another — naming a port nobody had touched. And a port this process had
  bound reported itself as taken, because the guard for that covered the three
  app ports and not the profile listeners, which are every port the app
  actually answers on. Fixing that opened a third: "9701 is mine" was true of
  every address on the machine, so moving a profile onto an address somebody
  else held would have been allowed and then failed to bind. The guard asks
  about the address now.
- **A row is a person or a device by how it arrived**, recorded when it is made.
  It used to be inferred from whether the row had ever pressed REQUEST ACCESS —
  a field kept for deciding whether a grant expires, borrowed because it was
  there. Somebody looking at the request form has not pressed it yet, so they
  were filed under the code process, on the one page that had nothing to do
  with them.
- **A screen reloads when ITS configuration moves.** The stamp digested every
  row, so one device opening the display page reloaded every screen in the
  building — and deleting a row reloaded the browser that had just made it,
  which said hello and made another. Delete, watch it return, delete again.
- **Three bugs of my own worth recording**, because they are the same shape: a
  commit row added as a bare div appeared on every page in the panel, since the
  machinery hides sections by an attribute a bare div does not carry; the panel
  is a GRID, so a section without `wide` or `bare` tiles into a narrow column
  beside its neighbours; and ALL on the bulk bar ticked every row this server
  knew about, including rows two tabs away with no APPLY under them. Matching a
  list's markup is not matching a tab, and a control's scope is the page it is
  drawn on.

## 2026-08-16 — a screen that looks perfect and does nothing

Phase 4: staying up unattended. The whole of it is invisible while it works,
which is why it needed its own phase — nobody ever gets to it as part of
something else.

- **The display checks in, and that one decision pays for four others.** A
  screen at rest issues no requests, so without it an outage would end and the
  wall would stay broken until somebody walked up and spoke to it. The same
  check-in keeps `last_seen` honest, gives the server somewhere to answer
  *reload yourself*, carries the maintenance settings out to every screen, and
  is how a screen notices on its own that the server came back.
- **The stamp is a digest, not a modification time.** `last_seen` is written by
  the very check-in that reads it, so a stamp based on the file's mtime would
  change on its own and order every screen in the building to reload itself for
  ever. Only the fields an admin can change are in the digest, and it is
  recomputed only when the file has actually been written — a building full of
  screens costs one `stat` each rather than one hash each.
- **The boot moment is the server's clock, not the device's.** A reload request
  is a moment in server time, and a tablet whose own clock is a year out would
  either obey it for ever or never. The display is told the time at its first
  check-in and hands that value back; a request older than it has already been
  satisfied by the load that is running. Nothing to acknowledge, nothing left
  set to fire again at the next restart.
- **Everything reloads, on every display** — and this went the other way first.
  It was built with the automatic reloads gated to kiosks, on the argument that
  a desk tab has somebody in front of it; that was overruled the same day. A
  screen is stale whether or not it hangs on a wall, and the guard that matters
  is the one already there for the nightly refresh: nothing reloads while
  somebody is talking to the screen or typing into it. A test about the moment,
  not about the kind of device.
- **It never reloads into an outage.** A reload while the server is unreachable
  swaps a working screen for the browser's error page, which has no check-in,
  no timer and no way back — the display would be gone until somebody walked
  over, which is the exact outcome the phase exists to prevent. A reload that
  falls due while it is down is held, and coming back carries it out.
- **A kiosk says it once, aloud, and the line clears itself.** It has no
  transcript and no composer, so speech is the only channel it has; saying it
  twice would make the outage worse than the silence it replaced. Nobody is
  standing in a hallway to dismiss anything, so an alert that needed
  acknowledging at the screen would be an alert that stayed up for a month.
  Anything not a kiosk stays quiet and fails at the moment somebody actually
  uses it.
- **Two bugs found while writing it, both in the new code.** Re-planning the
  nightly refresh on every check-in erased it instead of carrying it out — the
  check-in at the appointed minute moved the appointment to tomorrow a line
  before anything asked whether it was due, every night, for ever. And a tab
  coming back into view asked straight away while the timer's request was still
  in flight, leaving two chains armed, then four, each one doubling the load on
  a server already slow enough for that to happen.
- **A poll with no deadline is not a poll.** A dropped route does not refuse or
  error, it goes silent, and `fetch` will wait minutes — during which a screen
  that has lost its network sits looking perfect. Fifteen seconds and it counts
  as a failure.
- **What no setting here can reach, said plainly.** A tablet that reboots at
  four in the morning comes back to a lock screen with no browser running, and
  there is nothing left for this server to talk to — so kiosk mode, a launcher
  or screen pinning is a deployment instruction in the manual rather than a
  field in the panel.
- **The scheduled server restart was built after all**, the day after the phase
  closed. The entry had recorded it as needing a supervisor, which was true of
  the two options considered — schedule a stop, or wait for systemd. The third
  is a handover: the server launches `serve.sh restart` detached and lets it do
  the killing, so what brings the service back was already running before it
  went away. It waits for the server to fall quiet first, and will not act on a
  time that had already passed when it was set — that one rule stops both the
  restart loop and the admin who schedules a restart for the minute they are
  in. What it still cannot do is catch a `start` that fails to bind, which is
  why it is off by default and why the panel says so.
- **Four ships without its alert.** Raising one when a forced reload fails is
  phase 8's job, and eight did not move up to meet it. A screen the server
  cannot reach at all is visible in the panel as one that stopped checking in;
  what it does not yet do is come and find you.

## 2026-08-15 — the screensaver is still the product

Phase 3: what a wall display looks like. Appearance and screensaver profiles
set centrally, three settings on each device's row, and nothing in any of them
that touches what this server will answer — it is entirely canvas and presentation, which is the whole
reason it was split from phase 2.

- **Full screen is asked for on a gesture, and it does not fight.** An address
  bar and a tab strip across a hallway screen is a browser that happens to be
  running a display. The chrome is not removable by any page; being shown full
  screen is askable, and only off user activation — so the same first touch
  that ends the screensaver asks for it. A manual exit records the time and
  buys sixty seconds, because somebody leaving full screen is nearly always
  commissioning the screen and wants the address bar for a minute; asking again
  on their next tap would make it unusable exactly then. Never in an embed:
  taking over somebody else's viewport from inside their iframe is the rudest
  thing a guest can do.
- **A wall is voice only and speak only from one tick.** Both follow from what
  the thing is rather than being boxes to find. Voice only defaults on, which
  is safe only because `wall` gates it — a row that is not on a wall carries it
  and does not apply it. And push-to-talk holds the SPACE bar: a tablet bolted
  to a wall has no space bar, so a screen whose interaction model needs a
  keyboard nobody standing in front of it has is a workstation somebody screwed
  to a wall. SPACE is removed there, the same way TEXT is, and forced off in
  `setPtt` rather than at each caller.
- **That is also what made the resting prompt true.** The wake gate is inactive
  in push-to-talk, so *say the name* was an instruction that did nothing — the
  prompt correctly refused to draw itself, which is how the default was found
  at all.
- **A screen on a wall now says what to say to it.** One dim line low in the
  frame, for the person walking past who has no way of knowing a silent figure
  listens — and on a voice-only display there is no transcript or composer to
  suggest otherwise. Never on a browser tab, which somebody opened on purpose,
  and not while a conversation is happening, when everything else on screen is
  saying more than it could.
- **While it drifts the prompt is painted into the picture**, travelling with
  the figure and fading with the ease. Left in the DOM it would have been the
  one thing holding still on a screen whose entire purpose at that moment is
  that nothing does; removed altogether it would have been missing for exactly
  the person it is for, who walks up to a screen that has been idle for hours.
- **Dark hours, because idle cannot express "it is three in the morning".**
  Somebody walking past at 3am wakes an idle-dimmed screen to full brightness
  for the rest of the night. So a screensaver profile carries a window and a
  dim of its own, read off the DEVICE's clock — a building with screens in two
  time zones wants each dark at its own two. Equal endpoints are no window; a
  start later than an end wraps midnight, which is the ordinary case. The two
  dims resolve to the darker rather than the sum, so nothing goes past black.
- **A touch target is about fingers, not window width.** The 44-pixel minimum
  was keyed to `max-width: 560px`, which is right for a phone and wrong for
  every tablet: a wall screen in portrait at 800 points never reaches that
  breakpoint and was handing a finger a 22-pixel-high button. On a voice-only
  display that is not cosmetic — TALK is the only thing that can open a
  microphone, so the one control that had to be hittable was the smallest thing
  on the screen. `pointer: coarse` asks what was actually meant; width still
  decides whether the words fit.
- **Portrait was measured rather than assumed, and the geometry was fine.** The
  figure is scaled by the shorter side, so it holds a constant 85% of the width
  in portrait against 50% in landscape and never approaches an edge at any
  aspect — checked at three sizes. What portrait turned up was the touch
  targets above, which are not a portrait bug at all; they were simply invisible
  until somebody looked at a screen shaped like a wall display.
- **A place can have an appearance of its own.** The LOOK tab was one
  document for every viewer, so a deployment with a hallway screen and a laptop
  in it had no arrangement where both were right — one of them was wrong by
  construction. Four values now come from a profile a device names: type size,
  palette, layout and the figure. Everything else stays shared, and that
  shortlist is the design rather than a first cut. An override that could cover
  the whole document would quietly end "change it once for everyone", which is
  the only reason the shared document exists.
- **A missing appearance falls back; a missing screensaver switches off.** Both
  fail quiet and they fail to different places, because the safe answer differs:
  a screen with no appearance still has to look like something, and a screen
  with no screensaver simply does not drift. Deleting a profile clears it from
  every device that named it, so neither state is one somebody has to discover.
- **Values are checked against the list the panel offers, not stored as
  typed.** A palette name that is not a palette is not a screen that looks
  wrong, it is `PALETTES[S.palette].ink` throwing once per frame forever. Out of
  range is refused when a person presses save and clamped when a file is read —
  the same split the screensaver numbers use.
- **The look is re-applied after the settings load, not when it arrives.** The
  display asks for both documents at once and they race; loading the shared
  settings overwrites `S` wholesale. A place's own appearance applied when the
  display answered first would be silently undone a moment later by the very
  document it exists to override.
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
- **Idle is read off what is HAPPENING, not off a flag and not off the wake
  word.** The assistant speaking, a clip playing, a question outstanding, or the
  wake window still open. A display with no wake word at all still thinks and
  still speaks, and the first three are true on that path — which is why this
  never asked `Wake` alone. It asked `Drive.phase` until 2026-08-20, and that is
  a flag set from six places: any one of them returning early left it set, and
  the screen never drifted again. `Listen.busy` is deliberately not among them —
  a listening screen transcribes every noise in the room, so one frame of it
  would reset the whole clock, all day.
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
- **A rig instrument was on every wall in the building.** The frame rate
  readout was hidden for embeds and nowhere else, so every real display carried
  it — fixed at the top left, never moving, small and bright. On a wall that is
  not untidiness: it was the one thing left that drifting the whole figure away
  could not save, which is the exact failure the drift exists to prevent. The
  reasoning was already written beside the rule and had only ever been applied
  to the embed; a tablet in somebody's hallway is as much somebody else's
  product as an embed is.
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

## 2026-08-15 — a name for a set of them, and a panel that reads as one

Groups, and the tidying that came with using the thing for an hour.

- **Twelve ticks is not a permission model, it is data entry.** So a group is a
  name for a set of devices, made under GROUPS and named wherever access is
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

## 2026-08-15 — a code you type into the screen, and a device that can ask

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

## 2026-08-15 — a display is a place, and a place has to be let in

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

## 2026-08-15 — a real house, and what only a house could tell us

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

## 2026-08-15 — the house stopped hanging up

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

## 2026-08-14 — the house is an endpoint

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

## 2026-08-14 — the panel stopped being written for its implementer

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

## 2026-08-14 — three names, three destinations

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

## 2026-08-13 — what it is reachable at, and what it takes to get in

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
- **Beyond loopback with no sign-in is allowed and never quiet** — a line on
  the endpoint that is open, a warning on save, and a loud one at every
  startup. A machine set up this way on a network its owner controls may later
  join one they do not. The endpoint is where the line lives because that is
  the control that decides it; the exposure page keeps a count and a pointer.
  It is dismissable — for the tab, or against the admin account — because a
  warning that cannot be answered is one people learn to read past, and the
  dismissal is of a state: closing the endpoint forgets it.
- **The plain listener redirects to HTTPS**, keeping bookmarks, kiosk URLs and
  QR codes alive with path and query intact. **307, not a permanent redirect**
  — the target is configuration an admin can change, and a cached permanent
  one would strand every browser that ever visited on a dead port.
- **Not built: the middle rung**, a single PIN for the whole display. It is
  identity's PIN machinery pointed at a display, so it lands there rather than
  twice. Present and disabled, and named specifically if the API is asked for
  it.

## 2026-08-13 — another application can put this in its own page

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

## 2026-08-12 — identity, and the interface reads better

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

## 2026-08-12 — administration moved to its own port

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

## 2026-08-12 — established as Resonance

Separated from the application suite this was extracted from and established as
its own project. The repository, the working tree and the deployment all moved
out of that suite's namespace, and the licence notice no longer points at it.
The visual identity is still to be redrawn. Nothing about how the thing works
changed.

## 2026-08-11 — repository created

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
