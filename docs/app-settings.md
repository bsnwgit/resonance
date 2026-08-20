# Admin settings & accounts

Everything in this document is about how the server itself is wired, as
opposed to how the interface looks.

## Reachable at, and signing in

Two settings, deliberately not one "mode": **what it is reachable at**, and
**what it takes to sign in**. They are independent, and a single label covering
both starts lying the moment somebody changes half of it — "personal" would
still read personal after the binding moved to every interface on the machine.

They are two topics for the same reason, and they now sit on two tabs:
**Admin Portal**, under ADMIN, holds the panel's own interface and port;
**Sign in**, under SECURITY, holds what it takes to get past the door — with
the rest of who-gets-in, which is what that tab is about. **Sessions** went
with it, since how long a session lasts is the same subject.

**That binding is the panel's alone.** It was the whole server's and every
other listener was pinned to it; a network profile names its own interface and
so does enrolment, so it is the last one that needed a setting. Whether
anything is *exposed* — which is what decides that a password may not be typed
over plain HTTP — is asked of every listener, not of this one: a panel on
loopback with an assistant on the network is still a server on the network.

The posture line — what it is reachable at and what the door is, in the words
it actually means — stays under Admin Portal, because what it warns about is
exposure, and it still reports the pair whichever tab you set half of it on.

Both moved topics still write `app.json`, so they still need a restart — and
each carries its own SAVE inside it, the way every other topic in the panel
does, rather than being committed by a button on a tab they are no longer on.

They are still read as a pair:

| Reachable at | Fits |
|---|---|
| this machine only | your own machine; nothing else can reach it |
| one address | your own home network, your call, stated plainly |
| everything | anywhere other people are |

**There is no deployment-wide sign-in setting, in either direction.**

The **admin panel** always asks for a password. It holds the assistant's API
key, every credential the server stores, and the power to grant anybody access
to anything — a switch that opened it would be a switch somebody leaves on.

The **displays** ask per endpoint, under ACCESS ▸ AI, on **MUST SIGN
IN**. "Must there be a person" is a property of the thing being reached rather
than of the server: three assistants on one box can want three different
answers — a house one anybody in the room may talk to, a hosted model worth
money per question, one reading from a system that should know who asked — and
a single switch covering all three could only ever be set to the strictest.

**Two settings on an endpoint can each produce a sign-in box** — MUST SIGN IN,
and an allow-list that does not cover this caller. The display shows one
whenever it cannot use what is on the port, and does not distinguish the
reason. *Assistants* → *Sign in* has the table.

MUST SIGN IN refuses a **device** outright, approved or not. A wall screen has
no person on it, so an endpoint set that way is one your kiosks stop answering
on. That is what makes it the control that limits what a model costs, where an
allow-list of screens only limits which rooms it is heard in.

### This machine only

Loopback. The network is already the boundary, so accounts add nothing — and
**no certificate is needed**: browsers treat `http://localhost` as a secure
origin, so the microphone works unprompted and nothing crosses a network for
TLS to protect. Start it, open localhost, talk to it. None of the certificate
ceremony applies, and the admin page is served over plain HTTP here for the
same reason.

This is the install that makes fishing a generated password out of a log
unnecessary on your own laptop.

### One address

Worth doing regardless of anything else on this page. A machine bound to one
specific address rather than every interface does not follow you onto the next
network it joins. The panel offers the addresses this machine actually has
rather than a box to type one into — an address this machine does not have is
a server that will not start, and it would take the admin page with it.

If a stored address later disappears — a DHCP lease that moved, an interface
that is down — it is still shown, flagged, rather than some other address
being silently selected in its place.

### Beyond loopback with no sign-in at the displays

Allowed, and not dressed up as anything else. The structural argument for
skipping accounts is gone and what is left is you accepting a risk on a
network you control — anyone who can reach the machine can use whatever the
assistants are open to, and whatever it costs to run them. The panel itself
still asks. It is not refused, because you may want exactly that —
but it **warns at every startup and in the admin panel**, because a laptop
configured this way that later joins an office network will not have changed
on the day that matters.

**The warning is on the endpoint**, under ACCESS ▸ AI ▸ *Sign in*, because
that is the control that causes it — one line saying what being open costs,
shown only where that endpoint asks nobody to sign in and this machine can be
reached. This page keeps the count and a pointer, since being reachable is what
makes it matter rather than what decides it.

**It can be answered, two ways.** *Not now* lasts as long as the tab. *I know*
is recorded against your admin account, so it follows you to another machine
and leaves a colleague still being told — a shared "never show this again" on a
security notice is a notice worth nothing. Either way it is an acknowledgement
of a **state**: close the endpoint and every acknowledgement of it is forgotten,
so reopening it later is a new fact rather than a repeat of an old one.

It used to banner the display as well. That is gone: a description of this
server's exposure is not something to hand to every browser that loads a
screen. The reasoning that made it safe — anybody reading it could have opened
the admin port and found out anyway — expired the day the panel started always
asking for a password. Warnings live where they can be acted on: behind the
sign-in, and in the log of whoever ran the command.

A firewall rule, which is outside this application entirely, does more than
anything inside it.

### There used to be a panel PIN

One number for the whole panel — no accounts, no account management — for the
deployment with a single administrator. It is gone, with every other PIN in
this product.

**What it cost was the log.** Everything an account does is recorded against a
name. Everything done behind one shared number was recorded as
**(single PIN)**, because that is all it knew about who was there. A
deployment with one administrator is an account with one member, which is the
same login screen without the hole in the record.

An install saved on it comes up on **accounts** rather than refusing to start
or falling back to nothing — a removed authentication mode must never fail
open. The first-run password is minted the same way it is for any other
install with no account yet, and printed at startup.

### Accounts and roles

The default, because the safe default is the one that assumes it can be
reached. With sign-in set to nothing there are no accounts to manage: the
sections under IDENTITY ▸ ADMIN are not offered, and the account routes refuse
rather than quietly writing to a file nothing consults.

**This setting governs the display side too.** On **accounts**, somebody who
reaches a display that is not an approved device has to sign in with the email
address and password they set from their enrolment link. On **nothing**, they
do not — opening the link is the whole of it. One switch, because "is this
server reachable by people I have not met" is one question.

## Ports

**One port is configured here: the admin portal's**, 9702 by default — the page
you are reading this in, which requires a sign-in.

Everything the app answers on is a **network profile** instead, under
PROFILES ▸ NETWORK. A deployment can want several, and which endpoint each one
carries is a question about the app rather than about the portal. See
*Assistants* → *Network profiles*.

**A port carries one endpoint.** Ports were shareable once — several
assistants on one, told apart by wake word — and that went when signing in
became a property of the endpoint. A door with two assistants behind it can
only have one lock, and would have to answer for the looser of them; one
assistant per door is what makes the answer unambiguous. Choosing a port
another endpoint already answers on is refused, and the built-in display
ports are simply a profile like any other — there is no nominated default and
no listener that is special.

An install that already shares one keeps working — the rule is enforced where
a save is made, not by rewriting a configuration on upgrade, since moving an
assistant to another port changes the URL people use. It says so at every
startup, naming the endpoints, until they are moved apart.

The portal's port stays here deliberately: it is the way back in when what is
over there is wrong. For the same reason the server refuses to put it on a
port a network profile is using, and refuses to give a network profile this
one.

The admin routes are not merely hidden on the app's ports — they **do not
exist** there. Asking for one returns "not found", not "unauthorised", because
answering "unauthorised" would confirm the route is there for anyone probing.

### The plain HTTP port redirects

A network profile may name a plain HTTP port alongside its own. Wherever HTTPS
exists and the server is reachable beyond this machine, that plain port does
not serve the display — it **redirects to the profile's port** instead. The
microphone already refuses to work on an insecure origin, so a display served
there was half dead and mostly generated confusion about why.

It redirects rather than being deleted, so every bookmark, kiosk startup URL
and printed QR code pointing at it keeps working — with its path and query
intact, which is what matters for a `?display=` URL taped to the back of a
screen.

The redirect is **temporary (307), not permanent**. A permanent one is cached
by the browser indefinitely, and the target here is configuration you can
change: move the HTTPS port, or switch the machine to loopback, and every
browser that had ever visited would go on redirecting to a port nothing
answers on — unfixable from the server, and curable only by each person
clearing their site data by hand. A temporary redirect keeps the bookmark
working, which was the entire point, and costs one extra request per visit.

Two cases where the plain port keeps serving normally:

- **Bound to this machine only**, where it is the whole product and
  `http://localhost` is already a secure origin.
- **Beyond loopback with no certificate**, where there is no HTTPS to redirect
  *to*. Sending every visitor to a dead port would take the product off the
  air to enforce a rule it cannot satisfy, so it keeps serving and says so at
  startup.

A port must be between 1024 and 65535, and no two may collide — not the admin
portal's with a network profile's, and not two profiles' with each other.
Below 1024 requires root, and this server deliberately runs as an ordinary
user.

Before accepting a change, the server tries to bind the port. A port already
taken by something else is refused at the point of saving — otherwise it would
pass validation and only fail at the next restart, by which point the admin
interface is gone and the fix is editing JSON on the box by hand.

### Changes here need a restart

**Nothing on this tab takes effect until the process restarts.** You cannot
move the floor you are standing on. The panel tracks what is configured
against what is actually bound and tells you which values are waiting.

```
./serve.sh stop
./serve.sh start
```

Note the address you will need afterwards. Changing the admin port and then
restarting means the page you are on is no longer served — that is expected,
and the new address is the one you just saved.

## Sessions

*Under SECURITY, with signing in.*

**session idle minutes** is how long an idle admin session survives before it
has to sign in again. It slides: activity pushes the deadline out, so a
working admin is not signed out mid-task, while a forgotten tab expires.

**Minutes, and thirty of them by default.** An admin session is a window onto
a configuration everybody else is looking at the results of, and it should
last a piece of work rather than a working day. Five minutes to eight hours is
the accepted range; the long end exists for someone who needs it, not as a
suggestion.

When a session does end, the panel puts the sign-in back up rather than
reporting "not signed in" under whichever control you happened to touch. It
does not wait to be clicked either: the page asks the server every 45 seconds
whether the session is still alive, so a forgotten tab becomes a sign-in
screen rather than a live-looking panel that has quietly stopped working.
Your username is kept; only the password is asked for again.

That check deliberately does **not** renew the session it is checking. A poll
that refreshed what it was polling would mean an open tab never expired at
all, because the check itself would be the activity keeping it alive.

A viewer's session is a different question with a different answer. Somebody
signed in at a display is measured in **hours** rather than minutes: a person
standing in front of a screen doing their job is not holding the keys to
everyone else's configuration.

That number belongs to **the person**, on their row under IDENTITY ▸ USER,
rather than to one setting covering everybody. Blank takes the deployment's
default.

Changing a role or a password drops that account's existing sessions, so the
new rights or the new password take effect at the next sign-in rather than
whenever the old session happens to expire.

## Maintenance

What keeps a screen nobody touches working: how often every display checks in,
how many attempts a failing check-in makes and how long it waits between them,
whether every display reloads itself once a night — and whether this server
restarts itself once a day.

**None of them needs a restart to take effect** — unlike everything else on
this tab. Each display takes its settings at the next check-in, which is what
makes the check-in interval the one that changes how quickly the others arrive;
the server reads its own restart time afresh every twenty seconds.

The reasoning, what a screen actually does when it loses this server, and the
two things no setting here can reach — a tablet that reboots, and a scheduled
restart of this server — are in **Administration → Staying up unattended**.

## Accounts

### Roles

**admin** configures everything and manages accounts.

**viewer** signs in, reads the configuration, and changes nothing. The
controls are visibly inert rather than removed, so a viewer can see how the
display is set up — and read these documents — without being able to alter it.

Give people viewer unless they need to change things. It is a real role, not a
courtesy.

### Creating and removing

**CREATE** takes a name, a password and a role. **CHANGE PASSWORD** under
*Your account* changes your own.

The server refuses to remove or demote the **last admin**, including yourself.
An interface nobody can administer is a brick, and the recovery would be
editing JSON on the box.

### How passwords are held

Hashed with PBKDF2-SHA256 at 600,000 rounds, each with its own salt. The
plaintext is never written anywhere, and there is no route that returns a
hash. There is also no password reset by email — there is no mail
configuration and no address on file — so recovery for a forgotten sole-admin
password means editing `users.json` on the box.

Failed sign-ins back off geometrically per address, so guessing becomes
impractical quickly without ever locking a legitimate user out permanently.

## Files on disk

| File | Holds | Mode |
|---|---|---|
| `settings.json` | shared interface settings | world-readable by design |
| `routes.json` | every AI endpoint, and which model, speech and network profile it names | 600 |
| `displays.json` | every display and every profile — including the model profiles' API keys | 600 |
| `backend.json` | the single assistant this server had before endpoints. Read once at the migration and never written again | ordinary |
| `users.json` | accounts and password hashes | 600 |
| `embeds.json` | embed keys, hashed | 600 |
| `app.json` | the admin portal's port, binding, sign-in mode and session lifetime | ordinary |
| `server.pid` | the running process id | ordinary |

`settings.json` has to be readable — every viewer's browser fetches it to
build the interface. That is precisely why the keys, the accounts and the
embed keys live somewhere else: the model profiles' API keys are in
`displays.json`, the accounts in `users.json`, the embed keys in
`embeds.json`, none of them served by anything. **None of the files at mode
600 should ever be committed to a repository.**

## The service, or the deliberate lack of one

There is no systemd unit, and that is a decision rather than an omission: it
means the whole thing installs, runs, restarts and upgrades without ever
needing elevated rights.

```
./serve.sh status      # is it up, and on which ports
./serve.sh stop        # waits for the process to actually exit
./serve.sh start
```

`stop` waits rather than returning as soon as the signal is sent, so
`stop && start` cannot race itself for the listening sockets and leave nothing
running.

`status` resolves the process exactly — by recorded pid, then by port,
verifying in both cases that what it found is actually this directory's
server. It never matches on a name pattern, because pattern-killing on a box
running other things is how you take down something unrelated.

**The scheduled restart works with no supervisor because it hands over rather
than stopping.** At the time set under MAINTENANCE the server launches
`serve.sh restart` in a session of its own and lets it kill the running process
and start a fresh one. What it cannot do is catch a `start` that fails to bind
— see *Administration → Restarting this server on a schedule*, which is where
the reasoning and the one residual risk are written down.
