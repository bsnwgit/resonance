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
- **LOOK / MOTION / SPEECH** and **AI** — the four tabs that edit the shared
  interface.

At the foot, pinned so they are always reachable:

- **APP SETTINGS** — how the server itself is wired.
- **ACCOUNTS** — who can sign in.
- **DOCUMENTATION** — these documents.
- Your own name, your role, and **SIGN OUT**.

## Changes, and who sees them

This is the part worth understanding properly.

Moving a control changes the preview on the right **immediately**, and changes
nothing for anybody else. The state is yours until you commit it.

### Every part of the panel commits itself

There is no single save button. **LOOK, MOTION and SPEECH each have their own
SAVE FOR EVERYONE and REVERT**, at the foot of that tab, writing only the
settings on that tab.

That is not decoration. There used to be one button for all three, which meant
pressing it while looking at MOTION also published whatever had been left
half-adjusted on LOOK — a save whose scope was wider than the thing in front
of you, and no way to tell from the screen. Each row now says what it covers:
*19 settings on this tab, shared with every viewer*.

The consequence worth knowing: you can leave MOTION unsaved while saving LOOK,
and the preview will keep showing both. Each row carries its own unsaved
warning, in red, so the tab with work waiting behind it says so.

**REVERT** puts that tab's settings back to what the server holds and leaves
every other tab alone — reverting LOOK should not throw away an hour spent on
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
one. A tab that writes nothing shared shows no save row at all — the AI tab
has none, because each endpoint saves itself.

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

The DISPLAYS tab holds four topics:

| | |
|---|---|
| **Requested Access** | whether a general user needs approval at all, and what a grant to one is worth once given |
| **Created Access** | the queue: everything waiting on a decision, on a code being typed in, or on somebody asking again — and where you add one |
| **Connected devices** | everything that is simply working, most recently heard from first |
| **The request form** | what a request asks for |

Created Access and Connected devices are separate lists on purpose. One is a to-do list and empties as
you work through it; the other is a register you read when somebody asks what
is out there. Three rows that need attention buried among fifty that do not is
how a request sits unanswered for a week.

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
