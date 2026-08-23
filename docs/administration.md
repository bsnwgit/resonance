# Administration

The admin interface is a separate page on a separate port. It is not a mode of
the display and not a panel hidden behind a gesture — it is its own listener,
and on the display's ports it does not exist at all.

## Signing in

Open the admin address, which is the same host on the admin port — `9702`
unless it has been changed. It is **HTTPS only**. There is no plain-HTTP admin
listener, and if the certificate is missing the admin port does not open.

The first time the server starts it creates one admin account and prints the
password to the log, once. If you do not have it, ask whoever installed it, or
look at the top of `server.log` on the box.

Signing in gets you a session that lasts thirty minutes by default, sliding —
it is extended each time you do something, and expires after that long idle.

### If you are locked out

Failed sign-ins back off geometrically, so guessing gets slower quickly. Wait
it out; the delay is per address and clears on its own.

## How the panel is laid out

**It opens on nothing.** The first thing you see is the mark, at three quarters
of the panel's width, and the menus — no topics, no box, and no tab lit,
because none of them is where you are yet. Press anything and it steps back to
a watermark behind the work, where it stays for the rest of the session.

**HOME**, immediately left of your name, brings the whole panel back to that
state. It reloads: every list refetched, and nothing half-edited still sitting
in a field on a tab you can no longer see. Anything you typed and did not save
goes with it. Your sign-in does not — the session is a cookie, not something
the page is holding.

HOME and **SIGN OUT** are the only two filled controls on that bar, because
they are the only two that move the whole panel, and they are filled in
opposite colours: ice takes you back to the start, rust ends the session.
Beside them your name reads as one phrase — name, dash, level — rather than a
name with a badge after it.

The left column is the whole interface. It is organised as a set of topics,
and **one topic is open at a time**: opening another closes the one before it,
so the column stays short enough to take in at a glance rather than becoming a
wall to scroll through. Clicking the open one closes it, which is a legitimate
state to leave it in.

**In the bar across the top** are three boxed labels, each naming the links
beside it. A label is not somewhere you can go — nothing happens when you press
one. It says what the links after it have in common, and the large space before
the next label is what separates one subject from the next. The links are links
rather than tabs, because they do not switch which controls you are editing;
they change the subject entirely.

**Every label is shaded from the display's own palette**, a colour per subject
— the three in the bar in **blue**, PROFILES, LAYOUTS, CONNECTIONS and
ACCESS in **ice**, SEARCH in **milk**. They are the same five colours a display can be set to, taken from
the same values rather than matched by eye, so the panel and the thing it
configures are not two people's idea of one palette. The colour is there to
tell the rows apart at a glance; it is not saying anything you have to decode.

**SETTINGS** — how the server itself is run.

- **ADMIN** — how the server is wired: where it can be reached from,
  maintenance, and the admin portal's own port. What the app answers on is a
  network profile, not here; signing in and session lifetime are on SECURITY,
  with the rest of who-gets-in.
- **SECURITY** — who gets in and on what terms: **signing in** and how long an
  admin session lasts, **AI Requires Permission** — whether a general user
  needs approval at all, how long a grant lasts, how many devices and waiting
  requests there may be — the **certificate** every listener answers with,
  and the **groups** access is granted to.
  ENROLLMENTS ▸ USER answers who is waiting; this is whether anybody is asked
  in the first place.
- **ALERT** — what the server does when a screen goes wrong: where alerts are
  **sent** (syslog, a webhook, Home Assistant, email), **quiet hours** and the
  **digest**, how much of the **server log** is answered with, and how long
  what screens report is **kept**. All of it is configuration. What it
  configures is read on **STATUS**, which is a different page on purpose: one
  is set and the other is watched, and a page doing both is a page you cannot
  safely leave open.
- **ENROLL** — the door itself, as against who is already through it: which
  **port and interface** invitations are accepted on and what **name** the link
  carries, the **request form** somebody fills in from a display, and how long
  an **enrolment code** is worth anything for, and **Enroll Embed Server** —
  the scheme, host and optional port an outside application reaches this server
  by, which is the embed's equivalent of the two above and is nothing to do
  with the address your own screens use. The queues those settings feed are
  under ENROLLMENTS.

**ENROLLMENTS** — how something comes to be here: SETTINGS on its left decides
what the server is, IDENTITY on its right is who is here already, and this is
the one in the middle because it is the one somebody is waiting on.

- **USER** — the people you have minted a URL for, and
  everybody who has asked to be here and not yet been decided about.
- **DEVICE** — where a screen is set up: named, given a code, and watched until
  it takes it.
- **EMBED** — the third thing that enrols, and the one that is neither a person
  nor a screen: an *application*, admitted by a key its server holds rather than
  by a link somebody opens or a code somebody types. This is where one is made
  and where the code you hand its developer is shown, once. What has been issued
  is listed under ACCESS ▸ SITES.

**IDENTITY** — who this server knows about. Two populations that are not one
list: one signs in with a password to configure the server, the other picks up
a URL and talks to the display.

- **ADMIN** — the accounts that can sign in to this panel.
- **USER** — the people the display side knows about: everybody who has used
  their enrolment link and set a password. Somebody who has been given a link
  and not used it yet is on ENROLLMENTS ▸ USER until they do.

At the right of the same bar: **STATUS**, **HOME**, your own name, your role,
**SIGN OUT**, and the **?**. One side of the bar is where you are going, the
other is who you are.

**STATUS** is what the screens are *doing*: health, the alerts they raised, and
the server's own log. It sits out here rather than in a boxed group because it
is not a subject you administer — nothing on it writes anything — and because
it is the page you want from wherever you happen to be standing when something
has gone wrong. **HOME** goes back to the start and reloads the panel — every
list refetched and every half-finished edit gone, which is what "like it was
when I opened it" has to mean. The three are coloured apart: STATUS ice, HOME
green, SIGN OUT rust — the last being the only one that ends something.

**There is one ?**, at the far end past SIGN OUT, and it opens these documents.
It used to be a mark inside each boxed label, which said the labels had manuals
of their own when there has only ever been the one. It is blue, and it is the
same blue as every ? beside a topic heading, so help is one colour wherever you
meet it.

It opens a page rather than a container: every document on its shelf — using
it, administration, the display, assistants and integration — and a search
across all of them at the top. **The search reads the documents themselves, not
their titles.** What comes back is the line that matched and the heading it
sits under, so you can tell which of six mentions is the one you want before
opening anything, and opening a result lands you on that line rather than at
the top. Two characters or more; code blocks are not searched, because matching
a word against a key inside an example sends you to a line that cannot answer
you. Whether it found anything is said directly under the field.

Below the bar, two more rows built the same way — a boxed label, then links
marked by colour and a rule underneath rather than by a box of their own.

**PROFILES** names the first of them, on a line of its own with the row boxed
beneath it: the line runs above the label, turns down at the end of it and
carries on along the top of the row, so what is inside the turn is one subject.
Everything in it is a list of profiles, and the controls for one appear inside
it when you open it. Three groups across the row, each labelled in its own top
edge:

- **LAYOUTS** — **APPEARANCE / GEOMETRY / SPEECH / SCREENSAVER / LAYOUT**.
  What a screen is. LAYOUT reads last because it is the one that *names* the
  four before it rather than describing anything itself. **The wake word and
  the sleep word are on SPEECH**, with the voice — what an assistant is called
  is part of how it sounds — so a layout points at them rather than carrying
  them, and changing the word once reaches every endpoint wearing that
  profile.
- **PERMISSIONS** — **AUTHENTICATE / AUTHORIZE / PERMISSION**. Who may use an
  endpoint. AUTHENTICATE is whether a caller must be known and how long being
  known lasts; AUTHORIZE is which callers are allowed; PERMISSION is one of
  each under a name, and that name is what an endpoint points at.
- **CONNECTIONS**, at the right edge — **MODELS / NETWORK / CONNECTION**. What
  an endpoint speaks to and what it answers on, and the pairing of the two
  under a name. MODELS carries the limits and the system prompt as well, since
  those describe the service rather than the assistant in front of it.

Each of the three groups reads the same way: the last tab in it is the one that
*names* the others, and an endpoint names only those. Three pointers on an
endpoint instead of a dozen fields, and a rule written once rather than copied
onto every endpoint that shares it.

**ACCESS**, at the foot — who and what may reach this server, as opposed to
what you administer about it. It was called CONNECTIONS until the word was
needed for the pair above:

- **AI** — titled **Assistants**: the endpoints, each naming a connection, a
  layout and a permission.
- **NODES** — everything currently connected, in one register. Each row is
  badged for the door it came through — **ASKED** for a device whose user
  filled in the request form, **INVITED** for one you issued a code to — which
  is a fact about the row and not two lists to have filed it under. What those
  devices are *reporting* is not here — that is STATUS.
- **SITES** — every application holding a key to frame this interface. The
  register, not the form: a key is issued under ENROLLMENTS ▸ EMBED and appears
  here the moment it exists, the same move a screen makes from ▸ DEVICE to
  NODES. This is also where a site is *maintained* — a row opens on the key's
  own settings, in the same seven sections the key was made in: name, preset,
  which assistant it talks to, what it may do, what it draws, which origins may
  frame it, whether the host must name the person, and the session and rate
  numbers.

  **SAVE** rewrites the key in place. Same id, same secret, same grants — so
  nobody at the far end is sent anything, and no authorize profile stops naming
  it. Changing a key used to mean issuing a second one and deleting the first,
  which is a new id: every profile that had ticked the old one silently named
  nothing, and somebody's integration had to be re-done, to correct a hostname.

  **Narrow one and its live sessions go.** A session token carries the
  permissions and the origins it was minted with, so a key narrowed while its
  sessions ran would be narrower on paper only, for as long as a session lasts.
  Change what it may do, what it draws, the origins, the session length or
  whether the host must name the person, and every session that key is holding
  is dropped — the pages framing it ask for another within a moment and come
  back inside the new envelope. A rename drops nothing. **The host must name
  the person** is the one edit the far end has to follow: their own endpoint
  must send it from the moment you save, so send them the code on the row
  again.

  **Which assistant a site talks to is set here**, not by the address their
  page frames. Left blank it behaves as it always did — whatever endpoint
  answers on the port their integrator was given — and naming one moves the
  decision off their source and onto this row. Changing it drops the site's
  live sessions so the next question goes to the new one, and the endpoint's
  own permissions still apply.

  **What it may ask its own application for** is the third block on the row,
  and it is a separate decision with a separate SAVE — a permission over
  somebody else's data rather than over this server, edited on a different
  clock from the envelope above it. Type the address of the application's
  OpenAPI document and press **READ SPEC**: it is read, along with the
  `/.well-known/resonance.json` **they** publish saying what they permit, and
  the operations appear with a tick each. Anything that changes something is
  marked **WRITES**.

  **Everything starts off.** Ticking is what grants, and **SAVE OPERATIONS**
  is what commits it — and you can never tick past what their grant file
  allows. An application serving no grant file at all offers its read
  operations and no writes, which is the safe reading of silence rather than a
  limitation to work around: writes become available when its owner publishes
  the file saying so.

  Both documents have to sit on an origin the site is already registered
  under, so a spec address pointing anywhere else is refused when you press
  the button rather than fetched. **Withdrawing an operation drops the site's
  live sessions**, the same way narrowing its chrome does, so the change is
  true at once. The row says when the spec was last read, whether a grant file
  was found, and names anything that has since disappeared from their document
  and been un-ticked because of it — usually a rename at the far end, which
  has already quietly withdrawn something somebody depended on.

  Nothing here reaches their data from this server: every call is made by
  their own page carrying that visitor's login, so nobody can be shown
  anything they could not already open for themselves, and a write stops and
  asks the person by voice or by button with the real values read back. See
  [Reaching an application's data](host-data.md).

  **What it actually asked for is in `server.log`**, both legs of it:

  ```
  embed efe2c22ff5da2 (pktLog) -> GET /api/logs/search?limit=1 (lap 1)
  embed efe2c22ff5da2 (pktLog) <- searchSyslog 200 648B
  ```

  The outgoing line matches what the application's own access log recorded, so
  a disagreement about who dropped a call is settled by laying the two side by
  side. The reply is its status and size only — never the body, which is their
  data and would leave the machine with the log. **`no status` is not an HTTP
  code**: it means the browser never got a response, which is the difference
  between their API refusing and the call never leaving the page.

  **DISABLE** takes a site off the air and keeps the row; **DELETE** is final.
  **REISSUE KEY** mints a new secret on the same site — same id, same settings,
  same grants — for a key that has been lost or leaked; it is not the same as
  deleting and remaking, which would give the site a new id and silently drop
  every grant made to the old one.

  Open a row for the rest. **Reaches** is the line to read first, and the one
  you cannot work out anywhere else: which assistants that key may actually
  talk to. What a key may *do* is set on the key, here; what it may talk *to*
  is decided on the far side, in an authorize profile under PERMISSIONS ▸
  AUTHORIZE — so a site that draws everything and reaches nothing looks
  perfectly configured while answering 403 to every question it is asked. An
  endpoint with no permission, or half a one, is refused to everybody and is
  not listed. **Made** is the audit line: when it was issued, by which admin,
  and the id every log line and every authorize profile names it by.

**SEARCH** shares that bottom row, on the right third of it. Type to search
across every topic in every tab at once — the fastest way to find a control
when you know roughly what it is called but not which tab it lives under. It
searches a topic's whole text, including the prose behind its **?**, and a
topic that matched only on hidden help opens with that help showing rather than
looking like it has nothing to do with what you typed.

**It is there at all times, the opening screen included**, and it is the one
thing that works from there: it looks across every tab, so it is how you get
somewhere without knowing which tab to press. Typing takes the panel off that
screen, because the matches have to land somewhere. Emptying it puts the mark
back if you never chose a tab, and returns you to the tab you were on if you
did.

The red **✕** at the end empties it in one press. A field left filtered with no
obvious way out is how somebody concludes the panel has lost half its settings.

**Your own account is behind your name.** Click it for the box that changes
your password. It is the one thing on this page you do to yourself, so it sits
where your name is rather than as a topic on a tab about everybody else.

## Changes, and who sees them

This is the part worth understanding properly.

Moving a control changes the preview on the right **immediately**, and changes
nothing for anybody else. The state is yours until you commit it.

### Every part of the panel commits itself

There is no single save button, and no per-tab one either. **Every list saves
one row at a time, from inside the row** — a profile, an endpoint, a group, a
device. The row you are looking at is the scope of the button in it.

Wherever a block commits itself, its button sits at the **bottom right** of
that block, with anything that MAKES a new thing at the left of the same row.

Colour says which kind of act a button is: **green** commits, **red**
destroys, **amber** brings something new into existence, **yellow** takes
something back without destroying it, **blue** explains. CREATE and SAVE used
to share green, which made pressing one feel like pressing the other — only
one of them adds a row you then have to name.

There used to be a SAVE FOR EVERYONE at the foot of APPEARANCE, GEOMETRY and
SPEECH, publishing that tab's settings to every display at once. There is not
any more, and the reason is the profiles: those tabs are the **editor** for a
profile, and nothing else. A tab-wide commit sitting beside a list of profiles
would have published whichever one happened to be open to every screen in the
building.

**Nothing on those tabs reaches a display by itself.** There is no shared
appearance behind them and no nominated default in front of them: a display
shows the profiles it NAMES, and the page's own settings for the ones it does
not.

The consequence worth knowing: **moving a control changes the preview and
nothing else.** Nothing reaches a display until you press SAVE in the profile
row you are editing, and REVERT does not exist — closing the row without
saving leaves the stored profile as it was.

### The login message

**SETTINGS ▸ ADMIN ▸ Login Message** gives a screen two spoken lines: one when
somebody signs in, one when a sign-in is refused. It is spoken and the figure
moves with it, and **nothing is written to the transcript** — a sign-in is not
part of anybody's conversation and should not be sitting in the log of whoever
uses the screen next.

**Both are empty by default, which means silent, and that is deliberate.** A
wall in a shared space announcing *that did not work* tells everybody in
earshot that somebody just got a password wrong; announcing the success tells
them who is now signed in. Neither is a thing to switch on for somebody.

**One per line**, and it picks one — the same as the greeting phrases, so a
screen somebody signs into all day does not repeat itself. `{name}` and the
other variables work here too.

**It needs the local voice to be reliable.** A browser only starts speech
synthesis inside the gesture that asked for it, and whether a sign-in worked is
not known until the server has answered — by which time that gesture has been
spent. The local engine plays audio instead and is not subject to that rule, so
on SPEECH ▸ engine LOCAL this always speaks. On the browser voice it may be
dropped silently. Nothing else breaks either way.

### Saves that are not that save

Each of these writes a different document, so each has its own button:

| Button | Writes | Applies |
|---|---|---|
| SAVE, inside a profile row | that profile alone, and every display naming it | immediately |
| SAVE, inside an AI endpoint's box | that endpoint alone | immediately, next question |
| SAVE, on SECURITY | who has to be approved and what a grant is worth | immediately |
| SAVE, inside Enroll Time Limit | how long a code is worth anything for | immediately |
| SAVE, inside Sign in | how you get in | only after a restart |
| SAVE, inside an authenticate, authorize or permission row | that profile alone, and every endpoint naming it | immediately, next question |
| SAVE, inside Sessions | how long an admin session lasts | only after a restart |
| INSTALL, inside Certificate | `cert.pem` and `key.pem` | immediately, on every listener |
| MAKE A CERTIFICATE | the same two files, self-signed | immediately, on every listener |
| SAVE, on ADMIN | the admin port, binding, maintenance | only after a restart, except maintenance |

Offering one button that meant all of them is how somebody presses the wrong
one. The AI tab has no tab-wide save because each endpoint saves itself from
inside its own block, and the profile tabs have none because each profile
does.

An endpoint's action bar is the one row that is not just a commit: **MAKE
DEFAULT, TEST and SWITCH OFF** at the left, then a gap, then **SAVE** and
**DELETE** at the right — the destructive one held apart from the three that
are safe to press while you are still deciding.

## The live preview

The right-hand side is the real display, served exactly as a viewer gets it,
running inside this page. Every control on the left drives that frame live.

- **RELOAD** rebuilds it from the saved settings — useful for seeing what a
  viewer currently gets, as opposed to what you have been fiddling with.
- **OPEN DISPLAY** opens the real thing in a new tab.

The preview has no microphone. That is a browser rule about embedded frames,
not a limitation of the preview, so test anything voice-related in a real tab
with OPEN DISPLAY.

## Roles

**admin** configures everything and manages accounts.

**viewer** can sign in and read the configuration but change nothing. The
controls are visibly inert rather than hidden, so a viewer can see how the
display is set up — and read these documents — without being able to alter it.

The server will not let you remove or demote the last admin account. An
interface nobody can administer is a brick.

## Displays

A display is one device — a screen on a wall, a TV, a laptop, somebody's phone
— as distinct from a browser tab somebody opened. Anything with a browser and a
microphone counts.

**Two populations arrive by two routes, and each has a tab to arrive
through.** A person opens the display page and asks; a device is named here
and takes a code to the screen. They have almost nothing in common except
that both end up connected, so neither has to read the other's queue.

**PERSON** (under ENROLLMENTS) — people, and only people. **One list**,
under a PENDING divider, holding everybody who is not in yet whichever way
they got there:

| chip | what it is | what it is waiting on |
|---|---|---|
| **ENROLL** | you named them and were handed a link | them, to open it and choose a password |
| **FORM** | they asked from a screen | you, to APPROVE or REFUSE |

They were two separate boxes, which asked you to know the difference before
you could find either. The chip says which a row is, and that was the whole of
what the split was telling you.

What a request *asks* is **SETTINGS ▸ ENROLL ▸ Enroll User Form**.

### A person, as against a device

A device is one screen standing in one room. A person moves between a phone, a
laptop and a borrowed browser and is the same person in all three, so they are
not the same kind of row and they are not created the same way.

**You mint a person; they do not sign themselves up.** Name one under
**People**, give them an email address, and you are handed a link to send.
There is no self-registration here and nothing that verifies an address, so
anybody who could create their own account could create somebody else's.

**Tick their assistants while you are there.** The **AI** ticks on that box are
the grant, and they are written into the *authorize* profile of each endpoint
ticked — the same list you would edit under PROFILES ▸ PERMISSIONS, reached
from the other end. A profile named by several endpoints grants all of them.
Tick none and they reach whatever is open to everyone; an endpoint that is open
to everyone is reachable already, so ticking it grants nothing. The same ticks
are on the person's own row afterwards, so a grant made here can be changed
there.

### Where a link is opened

**Every invitation opens on one port, and an admin chose it.** It is under
SETTINGS ▸ ADMIN ▸ **Enrolment** — a port, the interface it answers on, and
optionally a name to put in front of it. The default is **9703**.

**The same link on any other port of this server answers 404.** That is the
point of the port existing: somebody holding a link who also knows a working
address cannot substitute one for the other. It used to be spendable anywhere,
which made the address in the link a guess that happened to work — nothing to
firewall, and nothing a deployment could state.

**Nothing else is on that port.** No assistant, no microphone, no device
enrolment — a browser that opens an invitation must not come away holding a
display token. It answers the link, the page that asks for a password, and that
password being set, and 404s everything else.

**Once the password is set, that page hands over the addresses** of the
assistants they may use, because the enrolment port is deliberately not one of
them. The list is computed with the same test that will be applied when they
arrive, so every line on it is a door that opens.

**The name is optional and is not a second binding.** The listener answers on
the interface whatever the name says; the name is the word put in front of the
port when a link is minted, so it has to resolve to that interface — and the
certificate has to carry it, or every browser will complain. `./make-cert.sh
<name>` writes the SAN.

Changing the port or the interface needs a restart. The name does not: it is
read at the moment a link is made.

**The link buys one thing: the page that asks them to choose a password.** It
is shown once — what is stored is a hash of it, so the panel cannot show it to
you a second time — and it is spent the moment they use it. After that the
account is reached by signing in with the address and the password, from any
machine, including one that has never heard of them.

**You never see the password and cannot set one.** They choose it, and an
admin who chose it would know it. That is the whole reason the link exists
rather than a password field on the row.

**A row moves when they use it.** Until then it sits here, badged
*LINK NOT USED*. The moment they set a password it appears under
**IDENTITY ▸ USER** — the same move a screen makes from ENROLLMENTS ▸ DEVICE
to NODES when it takes its code, and for the same reason: what divides those
two lists is whether the thing has finished arriving.

**REISSUE THE LINK is the whole of account recovery**, and deliberately the
same gesture as creating somebody. It mints a new link, clears the old
password, and signs out every browser they had open. A forgotten password and
a leaked link want the same answer, and neither of them is an admin typing a
password they would then know.

It comes out at the enrolment address, the same as the first one did — there is
only one, so a recovery link can never arrive from a different host than the
one somebody was originally sent, which is how a legitimate link gets treated
as a phishing attempt.

**A session is a person or a device, never both, and the URL decides which.** A
device you approved operates as a device; opening a person's URL on one is
refused where it is attempted, and the URL is not spent by the refusal. Signing
a person in at a screen several people share is deliberately not built yet, and
a kiosk is the case it is least for.

The badge on a row says whether the URL was ever picked up, which is the
question this list is read to answer.

**DEVICE** (under ENROLLMENTS) — a screen, from naming it to the moment it works:

| | |
|---|---|
| **Get a code** | name it, and the code appears with the clock already running |
| **Waiting for their code** | rows minted and not yet used, with REISSUE for one that ran out |

**ACCESS ▸ NODES** — everything that is working, in one register. A row
moves here on its own the moment it is connected, and leaves the tab it arrived
through; the door it came through stays with it as a badge, **ASKED** or
**INVITED**, rather than deciding which list it lands in.

Whether anybody is asked at all is on **SECURITY**, under **AI Requires
Permission** — that is the door rather than the key, and it decides what a
grant is worth once given. ENROLLMENTS ▸ USER answers who is waiting; SECURITY
answers whether anybody has to.

Each profile list has a tab of its own in the profile settings group — what a
screen looks like and what it is allowed to do were never the same question:

| | |
|---|---|
| **Appearance profiles** | what a place looks like, for the handful of values that cannot be shared |
| **Screensaver profiles** | what a kiosk does when nobody is there |
| **Layout profiles** | what a public screen is: voice only, full screen, the prompt line, and which of the lists above it uses |

They are in that order on the tab because it is the order you build in: the two
pieces first, then the thing that names them.

**A layout profile is composed, not self-contained.** It names an appearance and
a screensaver rather than carrying copies of their values, so changing what a
hallway looks like once still reaches every kiosk using it. Day and night in
one hallway share an appearance and differ only in the dim — that case is the
reason the three lists stayed three.

**None of them is the default, and there is no way to make one.** A device
that names no profile shows what the page itself ships with — a working screen
that nobody has dressed, rather than one wearing a profile built for somewhere
else in the building. Every screen is something an admin picked or something
plainly unpicked, and the register says which.

That is the same rule the network profiles have always had, applied to the
rest: a fallback nobody chose is how two things end up somewhere neither of
them was put.

### Setting a fleet in one place

Eight screens on one assistant are eight rows to set by hand, and they are
usually all the same kind of place. So an endpoint names a **layout** — ACCESS
▸ AI ▸ *Layout* — and every screen opened on that endpoint's **port** takes
it.

**The port is the association.** A browser on the Demo port is a Demo screen
because that is the address it was opened at. Nothing to tick and no list to
keep in step: a page is loaded from exactly one address, and a port carries one
endpoint, so there is never more than one answer.

**A screen has no choice of its own any more.** It had one, and it beat the
endpoint's — which is one question with two answers, and the second was only
ever a way for the two to disagree. A port carries one endpoint, an endpoint
names one layout, and a page is loaded from exactly one address, so there is
never more than one right answer. Set it on the endpoint and every screen on
that port takes it.

**Which screens an endpoint permits is a separate question**, on its
*Permission*. It is about who gets in and has nothing to do with how a screen
looks. An earlier version of this setting keyed off that grant instead, and it
was wrong twice over: a layout set on an endpoint applied to nothing until
every screen had also been ticked, and a screen granted two endpoints could
have two parents naming different layouts with no correct way to choose between
them.

**An endpoint with no port reaches nothing**, this included.

There is nothing on the row to read it against, which is the point: the same
device loaded from two addresses would have inherited differently at each, so a
per-row answer was one the register could never honestly print.

**One register became four lists, and every row is in exactly one.** Which one
is two questions: is this thing working, and is it a person or a machine.

A row that has not finished arriving is a job somebody has to do; a row that is
working is a thing they look up. Those are not the same page, and neither is a
person who filled in a form the same as a screen an admin minted a code for.
The two populations arrive by different routes with different buttons, and
neither wants to read the other's queue while doing it.

So an arrival is under **ENROLLMENTS** — ▸ USER while a person waits on a
decision, ▸ DEVICE while a screen has not taken its code — and everything
working is under **ACCESS**, in its own area. A row
moves itself the moment it starts working.

Ordering survives inside each list: anything waiting sorts by how much it wants
attention, and anything working by what was heard from most recently.

**There are two ways one gets in**, and which you use depends on whether you
knew it was coming.

**You are installing it — name it here first.** Type a name into the box and,
if you already know them, set the two things you would otherwise come back and
fill in on the row afterwards:

- **Kiosk mode** — whether the screen runs as a kiosk, chosen before it has
  ever been switched on. **Which layout it wears is not here**, and is not on
  the row either: that comes from the endpoint the screen is opened at. A page
  is loaded from exactly one address and a port carries one endpoint, so there
  is one answer and nothing to disagree about.
- **Network** — which profile it answers on, which also decides the address and
  port in the code you are about to be given. A building with several ports has
  several right answers to *what do I type into this screen*, and the right one
  is the one for the network the screen is on

Both are optional; leaving them alone gives exactly the code it always did.
Press GET A CODE, and you are given an address to type into that screen:

```
https://<host>:9701/e/K7QP-4M
```

**Or open the display page on that screen and type the six characters into the
box it offers** — *Setting this screen up?*, above the request form and on any
screen that is not approved, whether or not anybody may ask for access. The URL
is the better one for a television with a remote and no browser open yet; the
box is the better one for a screen already showing this page, where being sent
back to the address bar to finish is the long way round.

Either way it *is* that display — named, and already holding whatever endpoints
you ticked for it, because the row existed before the screen was switched on.

The code **works once** and is forgiving about how it is typed: case does not
matter, dashes and spaces are ignored, and the characters people misread on a
remote — `O` and `0`, `I` and `1`, `l` — are not in it at all. `k7qp4m` is the
same code as `K7QP-4M`.

**A row waiting for its code shows its name and that address, and nothing
else.** What the screen will be was chosen a line above the list, so restating
it on a row that is about to leave the list would be a second place to set the
same thing. Everything a device has to say about itself, it says once it is
connected.

**A clock runs on the row**, above everything else it says and in the one
colour on it that is not grey: green while there is time, amber in the last
minute, red once it is spent and telling you to REISSUE. How long it starts at
is yours, under SETTINGS ▸ ENROLL ▸ Enroll Time Limit, and **zero switches
it off** — a code is one use, and the row it enrols was approved the moment you
created it, so a deployment that mints codes on Friday and hangs the screens
on Monday is not less safe for it.

**It turned up by itself — approve it.** Somebody opens the display page on a
laptop or a phone, and it appears in the list as WAITING within seconds. Give it
a name and press APPROVE. It does not need reloading: a display that is waiting
asks again every twenty seconds and starts working on its own.

**Or it asks.** Where somebody has to ask first, a device that has not been
given access gets the figure and, where its transcript and composer would be,
your request form — because both of those are wired to endpoints it cannot reach,
and drawing them would be two controls that only ever refuse. It fills the form
in, the row appears here saying what they told you, and you approve or refuse
it.

### Deciding

**Approving is granting.** Press APPROVE and you tick which endpoints that
device may use in the same gesture. The reason to approve anybody at all is to
give them a particular assistant, so the decision and the grant are one thing —
an approval that grants nothing is a row that changed colour.

**Where the tick lands.** It is written into the **authorize** profile of each
endpoint you ticked, which is what the server reads — so it grants every
endpoint sharing that profile, and unticking takes it from all of them. A rule
named once is a rule shared on purpose; the row redraws with the endpoints that
actually resulted rather than the ones you clicked, so the reach is visible at
the moment you make it. Where a rule really is one endpoint's alone, give it a
permission of its own.

**Refusing takes two messages and a choice.** One is shown on their screen, so
they know what happened. One is a note that never leaves this panel, for
whoever comes back to this row in six months. And you decide whether that
device may ask again or not.

Refusing also takes back anything a previous approval gave. Otherwise *refused*
would be a word on a row rather than a thing that happened.

**The row leaves the queue as you refuse it**, because a queue is what is still
owed and a decision already made sitting in it reads as one still to make. It is
written to the server's log at that moment — who refused, whether they may ask
again, and both messages — so the record outlives the row leaving the list.

The row itself is kept rather than deleted: *may not ask again* is enforced off
it, and a deleted row is one that comes straight back the next time that browser
opens the page. Where they **may** ask again, asking puts them back in the queue
with what they typed the second time. Where they may not, they cannot ask and
the row stays out of sight — **so a final refusal cannot be taken back from the
panel**, and that is the one decision here with no undo.

**A refusal is per device, not per person.** Somebody turned away on their
laptop can open the page on their phone and ask again from a clean row. That is
what device identity is — anything stronger needs an identity that person
carries, which is what a dedicated URL will be.

### Kiosk mode

A **kiosk** is a screen people walk up to, that nobody has open and nobody is
sitting at — a wall, a stand, a reception counter, a tabletop. The mounting was
never what any of this followed from: what it follows from is that nobody owns
the session and nobody has a keyboard. It was called *on a wall* until
2026-08-16, which told anybody deploying on a stand that the feature was not
for them.

Most rows in a real deployment are not kiosks — a guest's laptop, somebody's
phone — so it is one tick. Tick **Kiosk mode** on a device and one control
appears: **which kiosk it is**, chosen from the LAYOUT profiles.
Untick it and the screen goes back to being an ordinary page, with the choice
kept: putting the device back up restores what you had.

What a kiosk *does* is the profile's business, not the row's. That is the whole
point of the split — the settings that used to be edited one device at a time
are now edited once, where they are named, and every screen using that profile
changes with them.

**A kiosk is voice only and speak only by default.** Both follow from what the
thing is rather than being two more boxes to find:

- **No text box.** Voice only arrives already ticked. Untick it for the case
  that wants a transcript — a television in a meeting room, a screen somebody
  reads — but the default is the geometry alone.
- **No keyboard.** Push-to-talk holds the SPACE bar, and a tablet bolted to a
  wall has no space bar. So a wall is always in the listening mode, and the
  SPACE button is removed from that screen rather than left there. This is also
  what makes the wake word real: the gate is inactive in push-to-talk, so on a
  wall the name is the way in.

TALK and AUDIO stay. A browser will not open a microphone unless somebody asks
it to, so TALK is pressed once when the screen is commissioned and the wake word
carries it from there.

**Date and time across the top** is a tick of its own, off by default. A screen
people walk past wants the time on it; a browser tab has one in the corner
already, which is why this is the layout's decision rather than something every
display gets. It sits at the two ends of the top edge, dim, and **goes while the
screensaver drifts** — a line that never moves is the exact thing the drift
exists to prevent.

What it *says* — 24-hour or 12-hour, and which of the date formats — is set once
for the deployment under **SETTINGS ▸ ADMIN ▸ Time format**, not here. A
building whose screens disagreed about how to write the time would be a building
with two answers to one question.

**And it goes full screen on the first touch**, unless the profile says otherwise. An address bar, a tab strip and
somebody's bookmarks across the top of a hallway screen is a browser that
happens to be running a display. The page cannot remove that chrome — no page
can — but it can ask to be shown full screen, and a browser grants that off a
gesture, which is why it happens on a touch rather than on load.

Only on a kiosk. A tab you opened is yours, and a page that went full screen the
moment you clicked it would be a page you never opened twice.

**A REFRESH ALWAYS DROPS IT, and no setting here can change that.** Leaving
full screen on navigation is in the specification, and the request to re-enter
needs a gesture — so a page cannot put itself back on load, however it is
configured. After a reload the screen is a normal browser window until the next
touch, which puts it back.

That is a real problem on a wall, because a wall reloads on its own: a settings
change published from the panel, a network blip, the browser restarting
overnight. The page-level tick cannot solve it. **What solves it is starting the
browser already full screen**, which is a window state rather than a page
permission and therefore survives every reload:

- **Kiosk mode** — `firefox --kiosk https://host:9701/` (Chromium:
  `--kiosk --start-fullscreen`). The right answer for a screen that is only
  ever this. Nothing to press, nothing to restore.
- **F11**, once, by hand. Browser-chrome full screen is not the same mechanism
  as the one this page asks for, and it is kept across reloads.

With either of those the tick becomes redundant and harmless — leave it on, and
it simply never finds anything to do.

**It does not fight you.** Press Escape and it stays out for a minute, because
somebody leaving full screen is nearly always the person installing the screen
wanting the address bar back — and asking again on their next tap would make it
unusable exactly while they are working on it. After that minute a wall goes
back to being a wall.

**And it keeps the screen awake**, unless the profile says otherwise. A tablet
that has let its backlight go out cannot be walked up to and spoken to: the
microphone is behind a page nobody can see, and the person standing in front of
it has no way of knowing the screen is anything but off. The page asks the
browser to hold the display on for as long as it is showing.

The browser drops that request whenever the tab is hidden, so it is taken again
every time the tab comes back — and some browsers will not grant it at all
until somebody has touched the page, which the same first touch that asks for
full screen takes care of. Untick it on a television, or on a device whose
operating system is already set never to sleep, where holding it gains nothing
and costs the battery.

Neither changes what this server will answer. This is entirely what the screen
looks like.

**Every row is a display**, and there is no longer a state where it is not
one. There was, while a shared settings document dressed every screen whether
or not it was in layout mode; that document is gone, so a row in that state
had nothing dressing it and came out looking broken rather than plain. The only
question a row answers now is which profile — its own, or the one it inherits.

**Voice only** is the geometry alone: no transcript and no composer. That is
what a screen in a hallway wants. It is not a workstation, and a page of
scrolling text on a kiosk is neither useful nor discreet.

This is the one setting that **beats the viewer's own control.** The three
buttons in the bar were built to override the shared settings deliberately,
because somebody standing in front of a screen knows better than a document
does. This is the exception: it is a policy for a *place* rather than the
preference of whoever walked past last. Where it applies, the TEXT button is
**removed from that screen rather than disabled** — a control that is present
and ignores you is worse than one that was never offered. What it does not do
is overwrite anyone's stored choice, so a tablet taken off the wall and used as
an ordinary tab gets that person's own setting back.

TALK, AUDIO and SPACE stay. A browser will not open a microphone without
somebody asking it to, so a display with no TALK button is a display that could
never hear its own wake word. Voice only means no text, not no controls.

**Listen from the moment it loads** is the answer to the problem that creates
on a wall. TALK is a button, and a wall screen has nobody standing at it — so
every reload left the hallway deaf until somebody walked up and pressed it,
which is exactly the walk the screen was meant to save. Tick this and the page
opens the microphone itself as soon as it loads.

**Off by default, and it has to be.** A page that opens a microphone unasked is
a page nobody should trust, and on a laptop the button is right there.

It is a **request, not a guarantee**: the browser decides whether a page may
open a microphone without somebody touching it first, and the answer is no
until the permission has been granted persistently for this address. So a
screen hung for the first time still needs one visit — grant the microphone and
tick *remember this decision*. After that it comes back listening on its own,
through reboots and republished settings alike. When the browser does refuse,
the status line says so and the **next touch of the screen starts it**, which is
the same single touch that asks for full screen.

**It says what to say to it.** A kiosk is walked past by people who
have never used it, and nothing about a silent figure suggests that it listens.
So a kiosk carries one dim line low in the frame — *say “kitchen”*, in
whatever the wake words actually are. **The profile can turn that line off, or
give it words of your own**; leave the text empty and it writes itself from the
wake words the screen is currently answering to, which stays right when you
rename one. It is there only while nobody is talking
to it, only where a wake word exists, and never on a browser tab: somebody who
opened the page did so on purpose.

While the screensaver drifts, that line is **drawn into the picture** and moves
with it. Taking it away would lose it for exactly the person it is for — who
walks up to a screen that has been idle for hours — and leaving it where it was
would be the one thing on a drifting screen that never moved.

**Both profiles are chosen from lists set centrally**, on the APPEARANCE and
SCREENSAVER tabs. All three settings are deliberately
separate axes: a wall screen can be voice only without ever drifting, a shared
television can drift while still showing its transcript, and a laptop can be
given larger type without being told to do either.

### Appearance profiles

A screen in a hallway is read from three metres. A laptop is read from fifty
centimetres. One type size cannot be right for both, and neither can one
layout: a wall wants the figure filling the frame, a desk wants room for the
transcript beside it.

**The tab is the editor; a profile is what it looked like when you pressed
SAVE.** Not a hand-picked shortlist of overridable values — a profile holds
*every* key the APPEARANCE tab writes, palette and layout and type size and
the glass sliders and the speaker labels alike. Tune it against the live
preview, then capture it under a name.

**Opening a profile loads it back into the tab**, so editing one is the same
gesture as making one. There is no PREVIEW and no STOP: you are always looking
at the profile you have open.

**A device that names no profile shows what the page ships with**, unless one
of its endpoints hands it one — see *Setting a fleet in one place*. Nothing is
nominated: no profile stands in for a choice nobody made. Deleting a profile
puts every device that named it back to the page's own settings, which is still
a working appearance and one no longer attributable to a profile that has
gone.

One limit worth knowing before a screen goes up: **type size tops out at
LARGEST**, because that is the range the APPEARANCE tab offers. If that is not enough
at three metres, the range itself is the thing to change.

### Screensaver profiles

A tablet showing a mostly-stationary figure for years will burn it into the
panel. The usual answer replaces the screen with something else. This one keeps
the same face — every appearance setting still applied — and moves it.

**Set them once, pick them per device.** A deployment has a handful of *kinds*
of place — a hallway, a bedroom, a shop floor — not one setting per screen.
Change **night** and every screen using it changes together. The alternative is
twelve rows quietly drifting out of step with each other and nothing on screen
telling you which had.

Up to eight profiles, each a name and three numbers:

| | what it does |
| --- | --- |
| **Idle seconds** | how long with nobody speaking to it and nobody touching it. **0 never starts**, which is how you park a profile without deleting it and unpicking every device that names it |
| **Shrinks to %** | how far down it scales first. Shrinking is what creates the margin to move within: drawn edge to edge there is nowhere to go, and moving it would only clip the sides |
| **Dims by %** | how much light comes off it while it drifts |
| **Dark from / until** | the hours a dim runs regardless of anybody being there. Set them the same for no dark window; a start later than an end wraps midnight, so **22:00** to **07:00** is what you mean |
| **Dark by %** | how much light comes off it during those hours |

### The status line

The strip above the composer — what the microphone is doing, what the voice is
doing. **It is a troubleshooting tool and it is off**, on every screen and every
person, until somebody turns it on. Before 2026-08-20 it was always drawn and
only suppressed by a heuristic guessing whether anybody was mid-conversation,
which is the wrong shape for a diagnostic: what you want while debugging is a
switch, and what a wall wants the rest of the time is silence.

**Two switches, and either one is enough.** A **device** carries one — that
screen, wherever it hangs — and a **person** carries one, which follows them to
whatever they sign in at. On/off, off/on and on/on all show it; only off/off
hides it. Making one of them win would mean turning yours on, seeing nothing,
and having to work out which of two rows in two registers was holding it down.

**Per row**, the button is in the row's own bottom bar on both registers, and it
says the state it is in rather than the state it would move to. **In bulk**, tick
the rows and use *Status line* — the bar above the device register on ACCESS, and
the one above the people on IDENTITY ▸ USER. A screen takes the change at its
next check-in; a person's applies the next time they sign in.

**A LISTENING SCREEN IS AN IDLE SCREEN.** This is the part that surprises
people, and it was wrong until 2026-08-20. The microphone being open is not a
conversation: a wall display transcribes every noise in the room, because that
is the only way a wake word is ever caught, and none of it is anybody talking to
that screen. So the idle clock does not stop for it.

What does stop it is a conversation that is actually happening — the assistant
speaking aloud, a clip playing, a question outstanding, or the wake window still
open after somebody woke it. Between two sentences nothing is speaking for a few
seconds, and the wake window is what keeps a screen somebody is standing in
front of from dimming at them mid-thought.

It used to ask the figure's own state instead, which is a flag set from six
places — and any one of them returning early left it set, after which that
screen never reached its screensaver again, with nothing on screen to say why.

Four things worth knowing about the behaviour:

- **It scales down, then drifts** — slowly and continuously rather than bouncing
  between corners. It covers more of the panel over a night that way, and it is
  calmer to share a room with. The travel is exactly the margin the shrink
  bought, so nothing is ever cut off, and the path does not repeat: two nights
  running do not light the same pixels in the same order.
- **Dark hours are a different question from the idle delay**, and that is why
  they are both here. Idle asks whether anybody has been here recently; only a
  clock keeps a hallway dark after somebody walks past it at three in the
  morning. The two dims never add up — whichever is darker at that moment wins,
  so a screen already drifting at night does not go past black. The hours are
  read off **the device's own clock**, not the server's, so a building with
  screens in two time zones has each of them dark at its own two in the morning.
- **The dim does more than the movement does.** Reducing brightness is the
  strongest thing available against burn-in, and it is independently what a
  screen in a hallway should do at two in the morning. It is not the same as
  switching the screen off: you can still see across a room that it is working.
- **It ends on the wake word or on a touch**, easing back to the centre rather
  than snapping. On a voice-only display touch is the only signal that is not
  speech, so it has to count. The transcript, the composer and the status line
  hide while it drifts — text sliding around a screen is worse than either state
  on its own — and they come back the instant you touch it. It also never starts
  while an answer is being thought about or spoken.
- **A device is never told the list.** It is handed the three numbers of the
  profile it uses and nothing else. The list of names is a description of a
  building, and no screen has any use for the names of places it is not in.

**PREVIEW tries a profile without saving it.** Nobody can pick a scale and a
dim by reading two numbers, and nobody should have to stand in front of a screen
waiting out three minutes of idle to find out what they chose. It drives the
live preview on the right; SAVE is what gives it to the devices that name it.

**Deleting a profile clears it from every device that named it**, the same way
deleting a display clears it from every endpoint that named that. A setting
pointing at something nobody can see is a setting nobody can change.

**When a device picks a change up.** Every display checks in on the interval
set under APP SETTINGS ▸ MAINTENANCE, and reloads itself when anything **it**
draws from has moved — its own row, or the settings every screen shares.
Another device arriving, being approved or being deleted is not that, and does
not disturb the screens it has nothing to do with — so a profile edited here reaches the wall without anybody
walking to it. Never while somebody is talking to the screen or typing into it;
it waits until they have finished. RELOAD on a row under ACCESS asks one
directly.


### Changing several at once

The bar above the two lists on **ACCESS**. Tick the rows you want and the
controls under it apply to all of them at once.

**Layout is no longer one of them.** It was — pick a profile, press APPLY TO
SELECTED — and it went with the per-screen override in 2026-08-20: what a
building of identical hallway screens wants is one change on the endpoint their
port carries, which reaches all of them without a selection at all. What the
selection is for now is the **status line**.

**ALL means all of this screen**, which is the two lists the bar sits under —
People and Devices. It does not reach the rows still arriving under
ENROLLMENTS: those are on a page this bar is not drawn on, and a screen still
waiting for its code has nothing yet for a profile to apply to. Rows outside
those two lists do not draw a tick at all.

A selection is dropped as soon as the row leaves the screen — a person you
approve, or a device that takes its code — so nothing is applied to something
you can no longer see.

### The settings above the list

**Does a general user require approval?**

*Yes* — somebody who has not been approved gets the request form instead of the
transcript and composer, and reaches nothing until you decide.

*No* — they open the page and use the default endpoint straight away. No form,
no queue, nothing for you to decide, and a restricted endpoint still needs a
code you issued. This is the setting for an installation where a general
assistant is meant to be there for anyone and only the expensive or the
dangerous one is controlled.

*No* can only be set while an endpoint open to any display is the **default**,
or it would mean access to nothing. The rule holds from both ends, so you also
cannot restrict or switch off that default while it is set.

**How long a granted request lasts.** Guest access is a lifecycle, not a
session: it runs out and the person asks again. Their answers are kept, so
asking again is one press for them and one decision for you, and the row counts
how many times it has been renewed.

**Displays you issued a code for never expire**, whatever that number says. A
screen on a wall going dark on a timer is not a security property, it is an
outage.

**Displays in total, and how many may wait at once.** When more than the
waiting limit are queued the oldest waiting row is dropped to make room, so set
it high enough that a real request cannot be pushed out by noise.

**What the request asks for** is yours to build: up to five fields, each with a
label and whether it must be answered, and one of them optionally a box big
enough for a reason. This server has no opinion about it — somebody running a
campus wants a name and a department, somebody running a house wants none of
it. Ask for no name and rows arrive labelled by their id, and you approve them
on whatever you did ask for.

**REISSUE is for a screen that lost its identity** — a browser that wiped its
data, a television swapped for a bigger one in the same place. The row keeps its
name and every endpoint that names it, so nothing has to be ticked again, and
you get a new code to type into the new screen. **The device using that row
stops working the moment you press it**, before the new code is typed: a place
is one device, so deciding to move it ends the old one there and then.

**Until you approve it, it renders and answers to nothing.** The appearance
settings are public, so a device that has just arrived looks exactly right the
moment it is powered on; what it does not have is the right to use any endpoint
you have restricted. Its status line says so, and gives the id you will see in
the list.

**The name is not the credential.** Anybody can type `?display=kitchen` into a
URL. What actually identifies a display is an unguessable token this server
issues on its first visit and keeps in a cookie the page itself cannot read.
Somebody who types a wall screen's URL into their own phone gets a *new*
token, which nobody approved — and turns up in this list as a row you were not
expecting. That is the early warning; it is also, in the ordinary case, simply
the next device you meant to add.

**Restricting an endpoint to named displays** is done on an **authorize**
profile, under PROFILES ▸ PERMISSIONS, and the endpoint reaches it through the
permission it names. `ANY DISPLAY` is what every endpoint did before displays
existed. `ONLY THESE` names them. Two reasons to want it: an
endpoint that *acts* — a house, a light switch — where every microphone in
earshot should not be able to trigger it, and an endpoint that *costs*, where a
hosted model is worth giving to some devices and not to all of them.

**What a restricted endpoint does to everybody else:** nothing audible. A
display that hears a name it may not use drops the utterance — it does not
answer, does not pass what it heard to whatever it was already talking to, and
says nothing out loud. The person was addressing a different device, and a
screen nobody was talking to announcing that it cannot help is noise laid over
somebody else's answer. The reason appears on that display's status line and in
the server log, which are the two places it belongs.

**The list also tells you** what each display calls itself, when it first
arrived and was last seen, which restricted endpoints name it, and how many
requests it has been refused. The *looks like* line — screen size, platform,
language — is a hint to help you recognise a device whose browser has been
wiped and which has therefore arrived as a new row. It is never a credential:
every field in it is forgeable from a browser console in one line.

**DELETE is the revocation.** The token stops matching anything immediately,
and the display is removed from every endpoint that named it. If the device is
still on the wall it will enrol again, as a new row, unapproved.

A display's token has no expiry. A wall display is commissioned once, and one
that stopped working a year later for a reason nobody standing in front of it
could see would be worse than anything the expiry bought.

## Staying up unattended

Everything above assumes a page somebody opened and will close. A tablet on a
wall is a browser tab running for a year: through server restarts, network
drops, endpoint reboots, certificate renewals and its own operating system's
ideas about backgrounding, with nobody standing in front of it to notice or
reload.

The failure this is written against is specific, and it is not a blank screen.
It is **a screen that looks perfect and does nothing.** The figure is drawn on
the device, so it keeps drifting and breathing with no server involvement at
all — somebody walks past, sees it moving, and assumes it is fine while nothing
has reached this server in a week. A blank screen at least gets reported within
the hour.

The settings are under **APP SETTINGS ▸ MAINTENANCE**, and none of them needs a
restart: each display takes them at its next check-in.

### Every display checks in

A screen at rest issues no requests at all. Without a check-in an outage would
end and the screen would stay broken until somebody walked up and spoke to it —
the server would be back, and the wall would not know.

That one check-in pays for four things: it keeps **Last seen** honest in the
device list, it gives RELOAD somewhere to be answered, it carries the settings
on this page out to every screen, and it is how a screen notices on its own
that the server has returned.

### How a change reaches a screen, and when it does not

Two different things travel on that check-in, and knowing which is which is the
difference between a screen that fixes itself and one that looks stuck.

**A stamp.** The server sends a value built from the endpoints document, the
shared settings and the app settings — anything a screen renders from. A screen
keeps the value it booted with, and reloads itself when it moves. It cannot say
*what* changed and does not need to: the answer to all of them is the same
reload.

**A request.** RELOAD on a device's row asks one named screen to reload, and the
check-in is where it hears about it. A request older than the screen's own boot
has already been carried out, so it fires once rather than for ever.

**Two states ignore the stamp, and only two.** A screen **waiting on a
decision** does — the approval itself moves the stamp, and reloading at that
moment would replace the words explaining what just happened with a page that
came back silently approved. So does a screen that has just been **approved into
an account** and is about to send somebody to choose a password: reloading that
one out from under itself is worse than anything the stamp could be telling it.

Every other screen acts on it, approved or not. Until 2026-08-20 only an
approved one did, and an unapproved screen is a legitimate working state rather
than a transient one — so a tablet somebody had opened the page on would sit for
days ignoring every configuration change, including one that took away what it
was allowed to do. Turn sign-in on for an endpoint underneath such a screen and
it carried on with the permissions it had fetched at load, finding out only when
it next asked that endpoint for something — which answered with a refusal in the
status line rather than a sign-in page.

**A RELOAD request is not gated at all** and reaches any screen with a row,
whatever its state. That is the way to bring one up to date by hand, and the way
to reach a screen still running a page from before a deploy.

**Neither ever interrupts a conversation.** A reload waits while the screen is
speaking, while a question is outstanding, and while somebody is typing into the
composer — a reload landing between a question and its answer is indistinguish-
able from a crash to the person who asked.

**Check in every (seconds)** — 20 by default, 2 to 300. Faster than a couple of
seconds is a denial of service somebody configured by accident; slower than five
minutes is a screen that stays dead through a lunch break.

### When a check-in fails

**Attempts before it says so** and **seconds between attempts** — three and
four by default. Three attempts is right for a server being restarted and wrong
for a cable somebody pulled out, which is why both are fields rather than
constants.

**Every display shows it. Only a kiosk says it aloud.**

**NO CONNECTION TO THE SERVER** appears high in the frame of any display whose
check-in has run out of attempts, with a quieter note in the status row at the
foot of the screen. **It clears itself** when the server answers again: nobody
is standing in a hallway to dismiss anything, and an alert that has to be
acknowledged at the screen is an alert that stays up for a month. A line is
silent, so it interrupts nobody — and somebody sitting at a desk tab learns why
it stopped answering before they ask it anything.

A **kiosk** also speaks it, once, after the last attempt. It has no transcript
and no composer, so speech is the only way it can tell anybody — and saying it
twice would make an outage worse than the silence it replaced.

**Nothing else speaks**, because speech fills a room. A desk tab stays quiet
and fails at the moment somebody actually tries to use it, rather than making
them wait out three attempts first. Somebody who has just spoken is owed an
answer now; a hallway nobody is standing in is not.

**On reconnect the page reloads** rather than picking up where it left off.
Resuming would preserve a conversation nobody is having any more — the outage
was minutes and the person left — while a reload picks up a deploy and anything
changed while the screen was down, including a route or an appearance an admin
corrected during the outage.

**It never reloads while the server is unreachable.** A reload into an outage
replaces a working screen with the browser's own error page, and that page has
no check-in, no timer and no way back. A reload that falls due during an outage
is held and carried out as part of coming back.

### Asking a screen to reload

**RELOAD**, on a device's row under ACCESS, asks that screen to reload
itself
at its next check-in. What it actually repairs is a display that is alive but
stuck: it is still checking in, so it is still listening, and a reload is the
whole fix. It defers while somebody is talking to the screen.

A display that does not come back from that is one this server has no channel
to at all — nothing here reaches it, and no amount of server-side work will.

### The nightly refresh

**At (HH:MM)** and **spread over (minutes)** — off by default. Every display
reloads itself once a night, because a tab that never reloads accumulates.

It is read off **each device's own clock**, not this server's, for the same
reason a screensaver's dark hours are: a screen's night is the night outside
it. And it is deferred while somebody is talking to the screen or typing into
it — a reload that lands between a question and its answer looks like a crash
to whoever asked.

Spread it if the building has more than a handful of screens: twelve tablets
reconnecting in the same second is a load this server did not previously have.
Each screen takes its own fixed slot inside the window, worked out from its
device id, so the spread stays put instead of re-shuffling every night.

### Restarting this server on a schedule

**Restart this server at (HH:MM)** — off by default, and read off *this
machine's* clock rather than a device's, because this one is about one server
rather than twelve screens.

There is no supervisor: `serve.sh` launches the process with `setsid nohup` and
there is deliberately no systemd unit, because that is what lets the whole
thing install and run without elevated rights. So a setting that merely
*stopped* the server at three in the morning would be a setting that ended the
service, with nothing left to start it again.

**It hands over instead.** At the appointed minute the server launches
`serve.sh restart` in a session of its own and lets that script kill it — `stop`
waits for the sockets to be released, `start` binds a fresh process. The helper
is detached, so the death of its parent is the thing it was launched to cause
rather than something that takes it with it.

**It waits for the server to fall quiet** — no question, transcription or
spoken reply for a minute. A restart in the middle of one is a crash as far as
whoever asked can tell. A check-in is not use: every display sends one every
few seconds, and treating those as activity would mean a building of screens
that never let the server restart at all. If it never falls quiet, it gives up
after an hour and leaves it for tomorrow.

**Setting a time that has already passed today leaves it for tomorrow.** That
is not a special case, it is the whole safety property: a time is only ever
acted on if it was already set when that minute arrived. It is what stops the
fresh process that came back at 03:00:04 from restarting itself again in a
loop, and it is what stops an admin who types `14:23` at `14:23` from taking
the server out from under themselves.

**The one risk worth knowing.** If the new process cannot bind — something else
took the port while it was down — nothing catches that, and the server stays
down until somebody looks. That is the residual cost of having no supervisor,
and it is why this is a field you set deliberately rather than a default. The
handover is logged to **`restart.log`**, which survives it; `server.log` is
truncated by every start, so a failure written there would be lost with the
process that reported it.

Every display sees the restart as a short outage and reloads itself when the
server answers again — so with this set you rarely also need the nightly
refresh above.

### What this cannot reach

**A device that reboots.** A tablet that restarts at four in the morning after
an operating system update comes back to a lock screen with no browser running.
There is nothing left for this server to talk to, and no setting on this page
reaches it. Relaunching a browser at a URL on boot is the device's job:

- **Android** — a kiosk launcher, or *screen pinning* plus a home-screen
  shortcut to the display URL.
- **iPad** — *Guided Access*, with the page added to the home screen so it
  opens without Safari's chrome.
- **A desktop or a mini PC** — the browser's own kiosk mode
  (`--kiosk <url>`), started by whatever the machine uses to start things at
  login.

Saying that plainly is better than a Maintenance page that quietly fails to
cover it.

## Logging catalog

*Under SETTINGS ▸ ALERT.*

Fifteen kinds of event are captured from the screens and from the server. They
are ticked in **four runs**, each under its own divider, rather than as one
grid of fifteen — fifteen ticks in a row is a list you read start to finish to
find the one you came for.

**Speech** is six faults about hearing and speaking: a refused microphone, no
recorder in the browser at all, a transcription that ran long, a recogniser
that errored, a fall back to the browser voice, a near-miss wake. **The
assistant** is three about the thing answering — asked for something it cannot
do, errored, ran long.

**Signing in** is the door: **signed in** and **sign-in refused**, the latter
saying whether it was a wrong password, an address with no account behind it,
or too many attempts. **The register** is four — **person created**, **person
deleted**, **display created**, **display deleted** — each naming who did it.

**The runs are what you would do about a kind**, which is the same line the
level setting falls on. The first two are faults a screen reports about itself.
The last two are not faults at all and are recorded at `info`, so a sink set to
warnings and errors does not carry them — they are a record of something
somebody did deliberately rather than something wrong, and the ledger holds it
either way. Everything that happened at a screen is filed against that screen,
so it reads in the same per-display list as the rest. **Every one is recorded
until you untick it**, and what is stored is the list you switched OFF, so a
kind added in a later version records itself rather than being silently missing
from a list written today. A kind this panel has no run for is ticked under a
run of its own at the end rather than going unshown: a tick nobody can see is a
setting nobody can turn off.

**Unticking one stops it being written at all.** That is the point — the ledger
is a file, and one screen with a broken microphone can fill it — and it is also
the cost: a kind you turn back on shows nothing that happened while it was off.
There is no hidden copy kept for later.

The two worth considering first in a working house are **woke on a near miss**
and **transcription ran long**: they are the noisiest, and the least likely to
be acted on.

**With syslog on, everything recorded is also sent.** Every event goes to the
collector as it happens, not only the ones that cross an alert threshold — so
the catalog governs both the local ledger and the sink, and unticking a kind
stops it in both at once.

**How much of it the collector gets is set by level**, beside the host and
facility: everything, warnings and errors, or errors only. It governs the
server's own log as well as the events — on `everything`, which is how it
ships, the collector gets the lot; on `errors only` it gets tracebacks and
error alerts and none of the running commentary. The reader at that
end is an aggregator and every one of them is pointed at a severity rather than
at this product's own words.

Alerts still go too, and they are a different thing: an alert is a threshold
crossed — five slow transcriptions from one screen in an hour — where an event
is the fact itself. A collector receiving both sees the fault and then the
judgement about it.

**`server.log` is a different stream, and it travels too.** That is the
process's own output — every HTTP request, saves, restarts, tracebacks —
written beside the program, and mirrored to syslog line by line whenever the
sink is on. It is not filtered by the event catalog above, which governs the
ledger: the catalog decides which *events* are recorded and forwarded, while
the log is simply everything this process writes.

## Groups

A name for a set of them, so a grant is made once instead of ticked twelve
times and re-ticked every time somebody gets a new phone. Groups are made on
**SECURITY**, under the settings that decide who has to be approved at all, and
named wherever access is granted — today that is an **authorize** profile, and
anything added later that grants something can name them the same way.

**Everything that starts working is filed with its own population** without
anybody doing it: a code redeemed puts a screen with the devices, an approved
request puts a person with the people. The group is made the first time one is
needed rather than shipped, and an existing group of the right kind is adopted
before a second is created — so an install that never uses groups never grows
two it did not ask for.

**Two kinds, and they do not mix.**

- **USERS** holds the people created under ENROLLMENTS ▸ USER. A person
  reaches an endpoint from whatever machine they sign in on, so a grant made
  here follows the human rather than the hardware.
- **DEVICES** holds displays — every screen and every laptop, however it got
  here.

There was briefly a third, separating the machines that *asked* from the ones
an admin *invited*. That is how a row enrolled, not which population it is in:
both are a browser on one machine, so both are displays. It is written on the
row now, where it describes without sorting — which means a group holding a
wall screen and somebody's laptop is a perfectly good group, where before it
could not exist.

**Groups stored under the old kind read back as DEVICES**, keeping their
members and the names you gave them. Nothing was rewritten on disk.

The two that remain cannot mix, and the reason is concrete rather than tidy:
they are different files whose ids are minted independently. That is also why
**a group's kind cannot change once it exists** — a kind that changed would not
filter the group's members, it would fail to find any of them.

**How a display got here is shown on the row**, not chosen: *created here and
enrolled with a code*, or *arrived by opening the display page and asking*. The
control that used to set it is gone with the distinction it was setting.

**Left at WORK IT OUT it follows how the row arrived** — recorded when the row
was made and never changed after. A code you minted is a **device**; a browser
that opened the display page is a **person**.

It used to ask instead whether the row had ever pressed REQUEST ACCESS, which
is a different question with a different answer: somebody looking at your
request form has not pressed it yet, and that filed them under DEVICE
ENROLMENT — the one page that has nothing to do with them, since nobody ever
minted them a code. Rows made before this was recorded fall back to the old
guess, so nothing moves under you.

A **person** is still, strictly, an identity that carries from a phone to a
laptop, and nothing here issues one yet — so "person" today means the browser
somebody walked up with rather than the human holding it.

**Changing it can drop the row from a group.** A group takes one population,
so moving a row to the other one removes it from any group of the kind it
left. The panel says which groups, rather than letting one quietly lose a
member.

**Grants add up.** An endpoint reachable by a group and by one device named on
its own is reachable by everyone in the group plus that device. Being in a
group never takes away a grant made individually.

**A group is not approval** — for a display. A device in a group that has not
been approved is still refused, and so is one whose access has run out. The
group says *which* endpoints it may reach; approval says whether it may reach
anything at all.

**A request is for an ACCOUNT, not for a device.** Somebody who fills the form
in is a person asking to be let in, and approving them creates the account and
mints the link rather than turning their browser into a screen on your wall.
The form asks for an **email address** above whatever fields you defined — it
is the login the request is for, so it cannot be renamed, reordered or
switched off — and the endpoints you tick are granted to the person.

They are standing at that screen waiting, so **their page takes them straight
to the choose-a-password box** the moment you approve. The link also appears in
the panel, once, for the case where they walked away.

**Either half of an endpoint's permission can put a sign-in box in front of
somebody.** The *authenticate* half asks whether there must be a known caller
at all; the *authorize* half asks whether this particular one is allowed. A NO
from either leaves the browser unable to use the endpoint, and a sign-in box is
what the display offers when that happens — so an endpoint whose sign-in says
NOT REQUIRED still shows one to a browser its allow-list does not cover. See
*Assistants* → *Permission* for the full table.

**A person has no equivalent test.** An account exists only because you made
it, so creating one *is* the approval and there is no way to turn up asking to
be one. Withdrawing it is deleting the person, or reissuing their link — which
clears the password and signs out every browser they had open.

**Deleting a group** removes it from every endpoint that named it. Nothing in
it is deleted — a group is a way of referring to people and devices, not a
thing they belong to.

## The certificate

*SETTINGS ▸ SECURITY ▸ Certificate.*

**One pair serves every listener** — this panel, each assistant, the enrolment
port. The microphone needs a secure context on all of them, and a second
certificate for the same machine would be a second thing to renew and a second
thing to forget.

**What it shows is read off the file, not out of a setting**: who issued it,
what names and addresses it answers to, when it runs out, and whether the
listeners are actually answering with it. Nothing in this product could see any
of that before — the pair was loaded at startup or it was absent, and its
expiry was a date in somebody's diary. It expires on every listener at once, so
the day that happens is the day nothing works and no page says why. Under
thirty days left, this section says so in the colour it uses for faults.

**Installing one does not need a restart.** Paste the certificate and its key,
press INSTALL, and every listener is handed it as soon as the pair is in place:
connections already open finish on the old one, everything arriving afterwards
gets the new. The single exception is a server that started with **no**
certificate at all — there is no HTTPS to hand anything to, the ports come from
the network profiles, and binding a socket under an admin's mouse is a thing
this panel has never done. That case takes a restart, and the note says so
rather than claiming a change nobody can see.

**Nothing is refused quietly.** A key that is not this certificate's, a block
that is not a certificate, one that has already expired, or one carrying no
subject alternative name — a browser refuses that last one whatever its common
name says — are each turned back by name, with what is on disk untouched. The
pair is checked with the same call a listener makes, beside the live files and
before either is replaced.

**MAKE A CERTIFICATE takes every name at once.** `make-cert.sh` takes one host
and writes the subject alternative name from it, so a deployment reached by an
address, a name, and the hostname in an invitation had to choose which of the
three would work. Type all of them here, separated by commas or spaces;
`127.0.0.1` and `localhost` are always included, because the machine itself is
always one of the ways this is opened. Good for a year, because a browser
refuses anything longer outright — sometimes as a blank page rather than a
warning anybody can click past.

**What it makes is still self-signed**, and that is a real limit rather than a
formality. Browsers warn until its issuer is trusted on the machines that use
it: fine for a screen somebody clicks past once, and **not** fine for an embed
on somebody else's site, which fails silently and blankly instead. For that,
install a certificate for a name a browser already trusts.

**The key never leaves the machine.** It is written beside the server as
`key.pem` at mode 600, the same as one made by the script.

## Locking down a deployment

`settings.json` is served to anything that can reach the display port. That is
deliberate — the display is built from it, and the browser needs it to render
and to match wake words. It holds no credential: API keys, tokens and upstream
addresses live with the model profiles in `displays.json`, which no browser
ever sees — the panel is told only whether a profile has a key.

**The network is still the stronger boundary.** In order of
effect:

1. **Put the wall displays on their own VLAN** and let nothing else onto it.
   A device that cannot open a connection needs no other control.
2. **Bind to one address** rather than every interface, in ADMIN →
   Reach & sign-in. A machine that later joins another network then does not
   follow you onto it.
3. **Firewall the display ports** to the addresses that should have them.

### What that does not cover

**Anyone using an approved device can read what that device reads.** The page
runs on hardware they are holding, so no setting here changes it. What they
get is the appearance settings and the wake words — which, on a device they
are allowed to talk to, they already know. They do not get a credential, an
upstream address, or any way to reach Home Assistant except by asking this
server, which they could already do by speaking.

**A display is told the wake word of an endpoint it may not use.** That is
deliberate and it is what makes the drop work: recognising the house's name is
the only way a phone can *ignore* a command addressed to the house rather than
passing it into its own conversation. The word buys whoever reads it nothing —
saying it into an unapproved device is refused at the server, every time.

**Two people sharing one device cannot be told apart.** Nothing here is
per-person.

**A token inside the page would not help.** It would be served to whoever
asked for the page and could be read back out of it. Access control belongs in
what the server will answer, not in what the page carries.

## Where things are kept

| File | Holds | Visible to |
|---|---|---|
| `settings.json` | the shared interface settings | everyone — the display is built from it |
| `routes.json` | every AI endpoint, and the connection, layout and permission it names | admin only, mode 600 |
| `users.json` | accounts and password hashes | nobody over HTTP |
| `app.json` | ports, binding and session lifetime | admin only |
| `backend.json` | the single assistant this server had before endpoints | read once, at the migration, then never again |
| `embeds.json` | embed keys, hashed, and what each one grants | admin only, mode 600 |
| `displays.json` | every display, its token hashed, whether it is approved, and every profile — layouts, connections, permissions and the rest, including the model profiles' API keys and the allow-lists a grant is written into | admin only, mode 600 |

**Two things live outside this directory.** Piper voices are in `voices/`, and
the transcription models are cached by faster-whisper under
`~/.cache/huggingface`. That second one is where the disk goes if you work
through the model list: `small.en` is ~250MB and `large-v3` ~1.6GB, and each
one you select is kept once it has been fetched. Nothing removes them for you.

The split matters. `settings.json` is world-readable by design, because every
viewer's browser has to fetch it to build the interface. Anything secret must
therefore live somewhere else, which is why the endpoints' keys and the
accounts each have their own file.

**None of these is reachable over HTTP, including the ones that are not
secret.** The server hands out exactly four files — the two pages and the two
pieces of artwork — and refuses everything else. That is an allow-list rather
than a list of things to hide, and it is deliberate: this directory is a
deployment, the base server will happily serve whatever is sitting in it, and
the next file to land beside these will not be foreseen either.

It is worth saying plainly why the rule is written that way round. It was the
other way, and the private key of the TLS certificate, the account hashes and
the endpoints' API keys were all downloadable, unauthenticated, from the
display port. A list of things to hide could never have been right: the file
holding one key per endpoint did not exist when such a list would have been
written.

## Restarting

The server is deliberately not a system service, so it needs no elevated
rights to run or restart. From the directory it is installed in:

```
./serve.sh status
./serve.sh stop
./serve.sh start
```

`stop` waits for the process to actually exit before returning, so
`stop && start` is safe and will not race itself for the listening ports.

## When a screen goes wrong

A screen with a fault cannot tell anybody. It is on a wall, it shows nobody
anything, and the note explaining what went wrong fades in front of an empty
room. **STATUS**, beside HOME at the right of the bar, is where it says so
instead, in three sections.

Everything on STATUS is read rather than set. What governs it — where an alert
is sent, how much log is answered with, how long what screens report is kept —
is **SETTINGS ▸ ALERT**, and each of the three sections below names the setting
that belongs to it.

### Health

What each screen has been reporting, worst first, so twenty of them can be read
down rather than opened one at a time. A microphone that would not open, a
browser with no recorder at all, transcription erroring or running long, the
neural voice quietly falling back to the browser's, and the wake word it
actually matched on.

Most of this was already being worked out and thrown away. The display says
*woke on "hows" (near "house")* as a note nobody on a wall is ever there to
read; kept, it is the only way to find out that two wake words are
cross-triggering.

Slow is reported and ordinary is not — a screen doing its job in half a second
has nothing to say, and a store of ordinary timings is a store nobody reads.
**CLEAR** on a row forgets what one screen reported without taking it off the
wall, for a fault that has been fixed.

### What was said to them

The conversation record, and the decision trail beside it. This is where *"it
didn't work"* becomes *the recogniser heard "hows" and matched it fuzzily to
the house route*, which is a thing you can act on.

Each row shows what was heard **before the wake word was stripped**, what was
sent, what came back, which route matched and whether it matched exactly or on
a near miss, how long it took, and any error verbatim.

**What is kept, precisely.** What was addressed to the device — from the wake
word to the end of that conversation — and the routing decision that followed,
for the retention window. Nothing outside an active conversation is recorded,
and nothing at all until somebody says a wake word.

This is a boundary that moved, so it is written down rather than left implied:
an earlier version of this promised no conversation content at all. The reason
it changed is that a voice-only display shows nobody anything, so when it
mishears there is no record and nothing to fix — and what is captured is
exactly what already leaves the machine, since it goes to a house or a model
regardless. It adds retention, not disclosure.

**Retention is the only control there is, and it is short on purpose.** Seven
days by default. A generous default would be a decision made on somebody's
behalf about their household.

### Alerts

Diagnostics is somewhere you go and look. An alert comes and finds you.

**Four states, not two:** open or resolved, acknowledged or not. The one that
matters is **resolved but unread** — a screen that dropped off at two in the
morning and came back four minutes later leaves something in the list until a
person sees it. Self-healing nobody ever hears about is indistinguishable from
nothing having happened, and a display that heals itself every night is a fault
rather than a success.

Resolving is automatic; acknowledging is not. Anything both resolved and
acknowledged has nothing left to say and leaves the list.

An alert has an identity — its kind and its device — rather than a row per
occurrence. A screen offline for a day is one alert that has been true for a
day, not two hundred and forty of them.

**What raises one.** Liveness, from the poll: three missed check-ins rather
than one, because a single drop is a hiccup and an alert that fires on one gets
switched off in a week. Hard faults, which are not rates: a microphone that
will not open does not get better by happening less often. And rates, which are:
near misses, slow transcription, a voice falling back, a house being asked for
what it cannot do. Screens that never worked raise nothing — an invited row
that has not taken its code has not gone quiet, it was never switched on.

One alert depends on none of that: **a device asking to be let in** arrives the
moment it asks, because it is the only one with a person attached to it.

### Where alerts go

The list is the baseline and is not optional, because acknowledgement has to
live somewhere. Everything else is in addition to it, cheapest reach first.

- **Syslog** — the standard library speaks it and every operator already has
  somewhere it goes. One socket, no credentials. **It carries the whole log,
  not only the alerts**: the startup banner, what a migration did, every
  request answered, every failed sign-in, and any traceback — the same stream
  that lands in `server.log`, mirrored line by line as it is written. Severity
  is where the line came from: the ordinary log is `info`, anything on the
  error stream is `err`. An alert carries its own instead — errors as `err`,
  warnings as `warning`, recoveries as `info`.
- **A webhook** — one JSON POST, which reaches ntfy, Slack, Discord, Gotify and
  whatever else you run.
- **Home Assistant** — the strongest here, because it can speak: a screen that
  dies gets announced by the building it is part of. It has **its own
  connection** rather than borrowing an endpoint's, since alerting hung off a
  route would vanish the day somebody deleted that route.
- **Email** — last, and not by accident. No dependency, but it wants a server
  and credentials and it fails somewhere this process cannot see more often
  than the others.

Every sink is **fire and forget**. Nothing retries or blocks, because a sink
that did would turn reporting a fault into a second fault — and whatever failed
to send is still in the list.

**Quiet hours** run on this machine's clock, the same one dark hours use, and
span midnight the way a night does: 22 until 7 is a night, not nineteen hours
of daylight. Nothing is dropped, only held — announcing a dead hallway screen
through the house speakers at three in the morning is how alerting gets
switched off in its first week.

**A digest** gathers what is held into one message, timed from the oldest thing
waiting rather than from the last digest: what matters is how long something has
gone unsaid, not how long since a message that may have carried nothing.

Two exceptions, both deliberate: **syslog ignores quiet hours**, because a log
with a hole in it every night is useless for the fault that only happens at
night; and **a device asking to be let in comes through regardless** of quiet
hours and digest mode both, because somebody is standing at a screen waiting.

**Name in the source field** decides what a collector files these lines under.
Blank uses this machine's own hostname, which is what a collector would infer
from the packet anyway — the field is for when that is not the name you want
to read: a host called `srv-04b` answering for the thing everybody calls the
kitchen, or several installs arriving behind one address.

It applies to a **remote** collector only. Sending to the local daemon leaves
the header to the daemon, which is already doing it; a second one would put
the name inside the message text instead of in the column.

Spaces in the name are turned into hyphens. The format ends that field at the
first space, so a name with one in it would push the rest of the line into the
message and leave half a word in the source column.

One thing worth knowing about the format rather than about this server:
**RFC 3164 carries no time zone**. The timestamp is local time with nothing
marking it as such, so a collector in another zone reads it as its own. That
is the format, not a choice made here, and the alternative is a line some
parsers reject outright.

### The server log

Readable from the panel rather than over SSH — the end of it, newest last,
filtered on a word. It is a tail through the admin listener and never a served
file. Not a live feed: press REFRESH.
