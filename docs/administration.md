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

Signing in gets you a session that lasts eight hours by default, sliding — it
is extended each time you do something, and expires after that long idle.

### If you are locked out

Failed sign-ins back off geometrically, so guessing gets slower quickly. Wait
it out; the delay is per address and clears on its own.

## How the panel is laid out

The left column is the whole interface. It is organised as a set of topics,
and **one topic is open at a time**: opening another closes the one before it,
so the column stays short enough to take in at a glance rather than becoming a
wall to scroll through. Clicking the open one closes it, which is a legitimate
state to leave it in.

At the top:

- **filter settings** — type to search across every topic in every tab at
  once. This is the fastest way to find a control when you know roughly what
  it is called but not which tab it lives under.
- **APPEARANCE / GEOMETRY / SPEECH / SCREENSAVER / DEVICE** — the profile
  settings group. Each is a list of profiles, and the controls for one appear
  inside it when you open it.
- **AI** and **DEVICES** — the connections group, to the right of a rule. AI
  holds the endpoints, each naming a speech profile. DEVICES is the register:
  every device this server knows about, and where each one is set up.
- **?**, beside the SETTINGS title — these documents. It is blue, and it is the
  same blue as every ? beside a topic heading, so help is one colour wherever
  you meet it.

At the foot, pinned so they are always reachable:

- **APP SETTINGS** — how the server itself is wired: where it can be reached
  from, signing in, ports, sessions, and what the two transcript labels say.
- **ACCOUNTS** — who can sign in, and the groups access is granted to.
- **ACCESS** — what may use this server, and what each may reach.
- **EMBEDS** — keys that let another application frame this interface.
- Your own name, your role, and **SIGN OUT**.

**Your own account is behind your name.** Click it for the box that changes
your password. It is the one thing on this page you do to yourself, so it sits
where your name is rather than as a topic on a tab about everybody else.

## Changes, and who sees them

This is the part worth understanding properly.

Moving a control changes the preview on the right **immediately**, and changes
nothing for anybody else. The state is yours until you commit it.

### Every part of the panel commits itself

There is no single save button. **APPEARANCE, GEOMETRY and SPEECH each have their own
SAVE FOR EVERYONE and REVERT**, at the foot of that tab, writing only the
settings on that tab.

Wherever a block commits itself, its buttons sit at the **bottom right** of
that block — SAVE and REVERT alike, with anything that MAKES a new thing at the
left of the same row.

Colour says which kind of act a button is: **green** commits, **red** destroys,
**amber** brings something new into existence, **yellow** takes something back
without destroying it, **blue** explains. CREATE and
SAVE used to share green, which made pressing one feel like pressing the
other — only one of them adds a row you then have to name. One position for all of them, so
the commit is where the eye already is rather than somewhere to be found again
per topic. The one exception is an endpoint's action bar, which is a row of
seven and keeps its own arrangement: SAVE at the left, and the destructive
actions held apart at the right.

That is not decoration. There used to be one button for all three, which meant
pressing it while looking at GEOMETRY also published whatever had been left
half-adjusted on APPEARANCE — a save whose scope was wider than the thing in front
of you, and no way to tell from the screen. Each row now says what it covers:
*19 settings on this tab, shared with every viewer*.

The consequence worth knowing: you can leave GEOMETRY unsaved while saving APPEARANCE,
and the preview will keep showing both. Each row carries its own unsaved
warning, in red, so the tab with work waiting behind it says so.

**REVERT** puts that tab's settings back to what the server holds and leaves
every other tab alone — reverting APPEARANCE should not throw away an hour spent on
SPEECH.

An unsaved change is flagged in red on that tab's row. Walking away from a
panel full of uncommitted changes is the single easiest mistake to make here.

### Saves that are not that save

Each of these writes a different document, so each has its own button:

| Button | Writes | Applies |
|---|---|---|
| SAVE FOR EVERYONE (per tab) | the shared interface settings on that tab | immediately, everywhere |
| SAVE, inside an AI endpoint's box | that endpoint alone | immediately, next question |
| SAVE APP SETTINGS | ports, binding, session lifetime | only after a restart |

Offering one button that meant all of them is how somebody presses the wrong
one. A tab that writes nothing shared shows no SAVE FOR EVERYONE at all — the
AI tab has none, because each endpoint saves itself from inside its own block.
SCREENSAVER and DEVICE share one: **SAVE PROFILES** writes both lists
together, because they are parts of one document and a device
profile can name an appearance added in the same sitting.

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

The ACCESS tab holds three topics — the rules about who may be here:

| | |
|---|---|
| **Requested Access** | whether a general user needs approval at all, and what a grant to one is worth once given |
| **The request form** | what a request asks for, under the setting that decides whether anyone is asked at all |
| **Created Access** | where you invite a device: name it and take the code to the screen |

The register itself is on its own tab, **DEVICES**, on the profile settings
row —
every device this server knows about, in one list.

Each profile list has a tab of its own in the profile settings group — what a
screen looks like and what it is allowed to do were never the same question:

| | |
|---|---|
| **Appearance profiles** | what a place looks like, for the handful of values that cannot be shared |
| **Screensaver profiles** | what a kiosk does when nobody is there |
| **Device profiles** | what a public screen is: voice only, full screen, the prompt line, and which of the lists above it uses |

They are in that order on the tab because it is the order you build in: the two
pieces first, then the thing that names them.

**A device profile is composed, not self-contained.** It names an appearance and
a screensaver rather than carrying copies of their values, so changing what a
hallway looks like once still reaches every kiosk using it. Day and night in
one hallway share an appearance and differ only in the dim — that case is the
reason the three lists stayed three.

**One of them is the default**, and you choose which. A device that names no
profile gets it, so a screen hung and never configured behaves like the rest of
the building rather than like nothing. It is stored by name rather than being
"the first in the list", so reordering the panel cannot quietly change what
every unconfigured screen is doing.

**Devices is one register, and it used to be two.** The split — a queue of
things wanting a decision, and a list of things simply working — was there so
that three rows needing attention were not buried among fifty that did not.
What actually carried that is the ordering, and the ordering survived the
merge: anything waiting sorts to the top by how much it wants attention, and
everything working follows by what was heard from most recently.

What the split cost was somewhere to look. A device you had just plugged in was
in one list or the other depending on whether it had been approved yet, which
is precisely the moment you are hunting for it. Now it appears under Devices
either way.

**There are two ways one gets into the list**, and which you use depends on
whether you knew it was coming.

**You are installing it — name it here first.** Type a name into the box, press
GET A CODE, and you are given an address to type into that screen:

```
https://<host>:9701/e/K7QP-4M
```

Type it once, on the device itself, and it *is* that display — named, and
already holding whatever endpoints you ticked for it, because the row existed
before the screen was switched on. The code lasts ten minutes, works once, and
is forgiving about how it is typed: case does not matter, dashes and spaces are
ignored, and the characters people misread on a remote — `O` and `0`, `I` and
`1`, `l` — are not in it at all. `k7qp4m` is the same code as `K7QP-4M`.

This is the one to use for anything without a keyboard. You are typing with a
remote or an on-screen keyboard, so the whole address is six characters longer
than the one you would have typed anyway, and there is no second trip back to
the panel afterwards.

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

**Refusing takes two messages and a choice.** One is shown on their screen, so
they know what happened. One is a note that never leaves this panel, for
whoever comes back to this row in six months. And you decide whether that
device may ask again or not.

Refusing also takes back anything a previous approval gave. Otherwise *refused*
would be a word on a row rather than a thing that happened.

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
appears: **which kiosk it is**, chosen from the DEVICE profiles.
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

**And it goes full screen on the first touch**, unless the profile says otherwise. An address bar, a tab strip and
somebody's bookmarks across the top of a hallway screen is a browser that
happens to be running a display. The page cannot remove that chrome — no page
can — but it can ask to be shown full screen, and a browser grants that off a
gesture, which is why it happens on a touch rather than on load.

Only on a kiosk. A tab you opened is yours, and a page that went full screen the
moment you clicked it would be a page you never opened twice.

**It does not fight you.** Press Escape and it stays out for a minute, because
somebody leaving full screen is nearly always the person installing the screen
wanting the address bar back — and asking again on their next tap would make it
unusable exactly while they are working on it. After that minute a wall goes
back to being a wall.

Neither changes what this server will answer. This is entirely what the screen
looks like.

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

The APPEARANCE tab is **one document for everybody**, and that is right for almost
all of it — tune the bloom once and every screen in the building gets it. It is
wrong for exactly four values.

A screen in a hallway is read from three metres. A laptop is read from fifty
centimetres. One type size cannot be right for both, and neither can one
layout: a wall wants the figure filling the frame, a desk wants room for the
transcript beside it. So four values become a profile that a device names:

| | |
| --- | --- |
| **Type size** | NORMAL, LARGER, LARGEST — the range the APPEARANCE tab offers |
| **Palette** | which of the five |
| **Layout** | HERO, or FULL BLEED for a screen that is mostly being looked at |
| **Figure** | STACK, DISC, ORB or KNOT |

Everything else stays shared. That is the point of the shortlist rather than
"override anything": a per-place setting that could cover the whole document
would quietly end the ability to change something once for everyone.

**A device that names no profile shows what the APPEARANCE tab says**, which is what
every display did before this existed. Deleting a profile puts every device
that named it back to that, rather than to nothing — so the fall-back is always
a working appearance.

**PREVIEW** lays a profile over the live preview without saving it, and follows
the controls as you change them. STOP puts the shared document back, and so
does touching anything on APPEARANCE, GEOMETRY or SPEECH.

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

**When a device picks a change up.** One still waiting on a decision is asking
this server every twenty seconds and takes it within seconds. One that is
already working has nothing left to ask about, so it takes it the next time its
page loads — reload it on the screen, or use OPEN DISPLAY here. Making a working
screen poll continuously for a setting that changes twice a year would be the
wrong trade.


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

**Restricting an endpoint to named displays** is on the endpoint, under AI →
*who may use it*. `ANY DISPLAY` is the default and is what every endpoint did
before displays existed. `ONLY THESE` names them. Two reasons to want it: an
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

## Groups

A name for a set of them, so a grant is made once instead of ticked twelve
times and re-ticked every time somebody gets a new phone. Groups are made on
the **ACCOUNTS** tab and named wherever access is granted — today that is an
endpoint's *who may use it*, and anything added later that grants something can
name them the same way.

**Two kinds, and they do not mix.** A group of **people** holds those who asked
for access and were approved. A group of **devices** holds the screens you
created and sent a code to. They answer separate questions — *the physics
department* and *the screens in the east wing* — so a group holds one or the
other, and its kind cannot be changed once it exists.

**Grants add up.** An endpoint reachable by a group and by one device named on
its own is reachable by everyone in the group plus that device. Being in a
group never takes away a grant made individually.

**A group is not approval.** Somebody in a group who has not been approved is
still refused, and so is somebody whose access has run out. The group says
*which* endpoints they may reach; approval says whether they may reach anything
at all.

**Deleting a group** removes it from every endpoint that named it. Nothing in
it is deleted — a group is a way of referring to people and devices, not a
thing they belong to.

## Locking down a deployment

`settings.json` is served to anything that can reach the display port. That is
deliberate — the display is built from it, and the browser needs it to render
and to match wake words. It holds no credential: API keys, tokens and upstream
addresses are in `backend.json`, which no browser ever sees.

**The network is still the stronger boundary.** In order of
effect:

1. **Put the wall displays on their own VLAN** and let nothing else onto it.
   A device that cannot open a connection needs no other control.
2. **Bind to one address** rather than every interface, in APP SETTINGS →
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
| `routes.json` | every AI endpoint, including its API key | admin only, mode 600 |
| `users.json` | accounts and password hashes | nobody over HTTP |
| `app.json` | ports, binding and session lifetime | admin only |
| `backend.json` | the single assistant this server had before endpoints | read once, at the migration, then never again |
| `embeds.json` | embed keys, hashed, and what each one grants | admin only, mode 600 |
| `displays.json` | every display, its token hashed, and whether it is approved | admin only, mode 600 |

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
