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

The left column is the whole interface. It is organised as a set of topics,
and **one topic is open at a time**: opening another closes the one before it,
so the column stays short enough to take in at a glance rather than becoming a
wall to scroll through. Clicking the open one closes it, which is a legitimate
state to leave it in.

At the top:

- **filter settings** — type to search across every topic in every tab at
  once. This is the fastest way to find a control when you know roughly what
  it is called but not which tab it lives under.
- **APPEARANCE / GEOMETRY / SPEECH / SCREENSAVER / GROUPS / MODELS / NETWORK /
  DEVICE** — the profile settings group. Each is a list of profiles, and the
  controls for one appear inside it when you open it. MODELS and NETWORK are
  the two halves of an endpoint that are not the endpoint: what it speaks to,
  and what it answers on.
- **AI**, **DEVICES** and **SECURITY** — the group to the right of a rule. AI
  holds the endpoints, each naming a speech profile, a model profile and a
  network profile. DEVICES is the register: every device this server knows
  about, and where each one is set up. SECURITY holds **AI Requires
  Permission** — whether a general user needs approval at all, how long a
  grant lasts, and how many devices and waiting requests there may be. ACCESS
  answers which device may reach which endpoint; this is whether anybody is
  asked in the first place.
- **?**, beside the SETTINGS title — these documents. It is blue, and it is the
  same blue as every ? beside a topic heading, so help is one colour wherever
  you meet it.

At the foot, pinned so they are always reachable:

- **ADMIN SETTINGS** — how the server itself is wired: where it can be reached
  from, signing in, sessions, and the admin portal's own port. What the app
  answers on is a network profile, not here.
- **ADMIN** — who can sign in. The groups access is granted to have a tab of
  their own, GROUPS, in the profile settings row.
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
profile now, and what every display gets is whichever profile is nominated
DEFAULT, published when that profile is saved. A tab-wide commit sitting
beside a list of profiles would have published whichever one happened to be
open to every screen in the building.

The consequence worth knowing: **moving a control changes the preview and
nothing else.** Nothing reaches a display until you press SAVE in the profile
row you are editing, and REVERT does not exist — closing the row without
saving leaves the stored profile as it was.

### Saves that are not that save

Each of these writes a different document, so each has its own button:

| Button | Writes | Applies |
|---|---|---|
| SAVE, inside a profile row | that profile alone; every display naming it, and every display at all if it is the default | immediately |
| SAVE, inside an AI endpoint's box | that endpoint alone | immediately, next question |
| SAVE, on SECURITY | who has to be approved, and what a grant is worth | immediately |
| SAVE, on ADMIN SETTINGS | the admin port, binding, session lifetime | only after a restart |

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

The ACCESS tab holds two topics — the rules about who may be here:

| | |
|---|---|
| **The request form** | what a request asks for. Whether anyone is asked at all is on SECURITY |
| **Created Access** | where you invite a device: name it and take the code to the screen |

Whether anybody is asked at all is on **SECURITY**, under **AI Requires
Permission** — that is the door rather than the key, and it decides what a
grant is worth once given. ACCESS answers which device may reach which
endpoint.

The register itself is on its own tab, **DEVICES**, right of the divider
beside AI and SECURITY — every device this server knows about, in one list.

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

**A device that names no profile gets whichever profile is nominated
DEFAULT.** Deleting a profile puts every device that named it back to that,
rather than to nothing — so the fall-back is always a working appearance.

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

**When a device picks a change up.** Every display checks in on the interval
set under APP SETTINGS ▸ MAINTENANCE. A kiosk reloads itself when anything it
draws from has moved, so a profile edited here reaches the wall without
anybody walking to it — though not while somebody is mid-conversation with the
screen. A display that is *not* a kiosk has a person in front of it who can
reload the page, and taking one out from under them to apply a colour somebody
changed upstairs would be a worse interruption than the stale colour; use
RELOAD on its row under DEVICES to ask it directly, or OPEN DISPLAY here.


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

**Check in every (seconds)** — 20 by default, 2 to 300. Faster than a couple of
seconds is a denial of service somebody configured by accident; slower than five
minutes is a screen that stays dead through a lunch break.

### When a check-in fails

**Attempts before it says so** and **seconds between attempts** — three and
four by default. Three attempts is right for a server being restarted and wrong
for a cable somebody pulled out, which is why both are fields rather than
constants.

**How it says so depends on what the screen is.**

A **kiosk** speaks the failure aloud, once, after the last attempt, and shows a
line high on the screen. It has no transcript and no composer, so speaking is
the only way it can tell anybody — and saying it twice would make an outage
worse than the silence it replaced. **That line clears itself** when the server
answers again: nobody is standing in a hallway to dismiss anything, and an
alert that has to be acknowledged at the screen is an alert that stays up for a
month.

Anything **not** a kiosk stays quiet. Somebody is sitting in front of it, and
it fails at the moment they actually try to use it rather than making them wait
out three attempts first. Somebody who has just spoken is owed an answer now; a
hallway nobody is standing in is not.

**On reconnect, a kiosk reloads the page** rather than picking up where it left
off. Resuming would preserve a conversation nobody is having any more — the
outage was minutes and the person left — while a reload picks up a deploy and
anything changed while the screen was down, including a route or an appearance
an admin corrected during the outage.

**It never reloads while the server is unreachable.** A reload into an outage
replaces a working screen with the browser's own error page, and that page has
no check-in, no timer and no way back. A reload that falls due during an outage
is held and carried out as part of coming back.

### Asking a screen to reload

**RELOAD**, on a device's row under DEVICES, asks that screen to reload itself
at its next check-in. What it actually repairs is a display that is alive but
stuck: it is still checking in, so it is still listening, and a reload is the
whole fix. It defers while somebody is talking to the screen.

A display that does not come back from that is one this server has no channel
to at all — nothing here reaches it, and no amount of server-side work will.

### The nightly refresh

**At (HH:MM)** and **spread over (minutes)** — off by default. A kiosk reloads
itself once a night, because a tab that never reloads accumulates.

It is read off **each device's own clock**, not this server's, for the same
reason a screensaver's dark hours are: a screen's night is the night outside
it. And it is deferred while somebody is mid-conversation — a reload that lands
between a question and its answer looks like a crash to whoever asked.

Spread it if the building has more than a handful of screens: twelve tablets
reconnecting in the same second is a load this server did not previously have.
Each screen takes its own fixed slot inside the window, worked out from its
device id, so the spread stays put instead of re-shuffling every night.

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

**A scheduled restart of this server.** There is no supervisor. `serve.sh`
launches the process with `setsid nohup` and there is deliberately no systemd
unit, because that is what lets the whole thing install and run without
elevated rights — so a setting that stopped the server at three in the morning
would have nothing to start it again. A Maintenance page with a restart button
that ends the service is worse than one without, so there is not one. It waits
for a supervisor somebody opts into.

## Groups

A name for a set of them, so a grant is made once instead of ticked twelve
times and re-ticked every time somebody gets a new phone. Groups are made on
the **GROUPS** tab and named wherever access is granted — today that is an
endpoint's *who may use it*, and anything added later that grants something can
name them the same way.

**Two kinds, and they do not mix.** They answer separate questions — *the
physics department* and *the screens in the east wing* — so a group holds one
population or the other, and its kind cannot be changed once it exists.

**Which population a row is in is set on the row**, under DEVICES: *It is a*
— DEVICE, PERSON, or WORK IT OUT. Left at WORK IT OUT it is inferred from how
the row arrived: asked for access reads as a person, issued a code reads as a
device. That inference answers the wrong question and is only there so every
existing row has an answer — asking for access happens in a browser on one
machine, which describes a device. A **person** is an identity that carries
from a phone to a laptop, and nothing here issues one yet, so today almost
everything is honestly a device.

**Changing it can drop the row from a group.** A group takes one population,
so moving a row to the other one removes it from any group of the kind it
left. The panel says which groups, rather than letting one quietly lose a
member.

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
addresses live with the model profiles in `displays.json`, which no browser
ever sees — the panel is told only whether a profile has a key.

**The network is still the stronger boundary.** In order of
effect:

1. **Put the wall displays on their own VLAN** and let nothing else onto it.
   A device that cannot open a connection needs no other control.
2. **Bind to one address** rather than every interface, in ADMIN SETTINGS →
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
| `routes.json` | every AI endpoint, and which model profile it names | admin only, mode 600 |
| `users.json` | accounts and password hashes | nobody over HTTP |
| `app.json` | ports, binding and session lifetime | admin only |
| `backend.json` | the single assistant this server had before endpoints | read once, at the migration, then never again |
| `embeds.json` | embed keys, hashed, and what each one grants | admin only, mode 600 |
| `displays.json` | every display, its token hashed, whether it is approved, and the profiles — including the model profiles' API keys | admin only, mode 600 |

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
