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

## Locking down a deployment

`settings.json` is served to anything that can reach the display port. That is
deliberate — the display is built from it, and the browser needs it to render
and to match wake words. It holds no credential: API keys, tokens and upstream
addresses are in `backend.json`, which no browser ever sees.

**The network is the boundary, and today it is the only one.** In order of
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
