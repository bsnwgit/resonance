# App settings & accounts

Everything in this document is about how the server itself is wired, as
opposed to how the interface looks.

## Reachable at, and signing in

Two settings, deliberately not one "mode": **what it is reachable at**, and
**what it takes to sign in**. They are independent, and a single label covering
both starts lying the moment somebody changes half of it — "personal" would
still read personal after the binding moved to every interface on the machine.

They are two topics under APP SETTINGS for the same reason. **EXT Access**
holds where the server can be reached from; **Sign in** holds what it takes to
get past the door. The posture line — what it is reachable at and what the door
is, in the words it actually means — is stated under EXT Access, because what
it warns about is exposure.

They are still read as a pair:

| Reachable at | Sign in | Fits |
|---|---|---|
| this machine only | nothing | your own machine; nothing else can reach it |
| one address | nothing | your own home network, your call, stated plainly |
| one address | a single PIN | a home network you would rather not leave open |
| everything | accounts and roles | anywhere other people are |

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

### Beyond loopback with no sign-in

Allowed, and not dressed up as anything else. The structural argument for
skipping accounts is gone and what is left is you accepting a risk on a
network you control. It is not refused, because you may want exactly that —
but it **warns at every startup and banners in the display itself**, because a
laptop configured this way that later joins an office network will not have
changed on the day that matters.

A firewall rule, which is outside this application entirely, does more than
anything inside it.

### A single PIN — not built yet

One number for the whole display, no accounts, no admin sign-in. The middle
rung, and the right answer for a home server: it keeps a guest's phone or a
smart television out without turning a house into an enterprise. It is the PIN
machinery from identity pointed at a display rather than at a named person, so
it arrives with that work rather than being built twice. The button is present
and disabled so the omission is visible rather than silent.

### Accounts and roles

The default, because the safe default is the one that assumes it can be
reached. With sign-in set to nothing there are no accounts to manage: the
ACCOUNTS tab is not offered, and the account routes refuse rather than quietly
writing to a file nothing consults.

## Ports

Three listeners, each with a job:

| Port | Default | Serves |
|---|---|---|
| display, HTTP | 9700 | the display, no microphone |
| display, HTTPS | 9701 | the display in full |
| admin | 9702 | the panel you are reading this in |

The two display ports serve the same interface to anyone who can reach them.
The admin port serves this page and requires a sign-in.

The admin routes are not merely hidden on the display ports — they **do not
exist** there. Asking for one returns "not found", not "unauthorised", because
answering "unauthorised" would confirm the route is there for anyone probing.

### The plain HTTP port redirects

Wherever HTTPS exists and the server is reachable beyond this machine, the
plain port stops serving and **redirects to the HTTPS port** instead. The
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

Ports must be between 1024 and 65535 and all three different. Below 1024
requires root, and this server deliberately runs as an ordinary user.

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

A viewer's session is a different question with a different answer, and it
does not exist yet — see *Identity* in the README roadmap. When it does, a
display unlocked with a PIN is measured in **hours** rather than minutes:
somebody standing in front of a screen doing their job is not holding the keys
to everyone else's configuration.

That number will belong to **the display URL the PIN was entered at**, not to
the person who entered it and not to one setting covering every display. The
place is what carries the risk: a workshop screen only the workshop can reach
and a reception screen facing the street are the same person on the same PIN
and want opposite answers. An admin securing a room can reason about that
room. Nobody can reason usefully about a number that follows a human between
the two.

Changing a role or a password drops that account's existing sessions, so the
new rights or the new password take effect at the next sign-in rather than
whenever the old session happens to expire.

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
| `backend.json` | assistant configuration and API key | 600 |
| `users.json` | accounts and password hashes | 600 |
| `embeds.json` | embed keys, hashed | 600 |
| `app.json` | ports and session lifetime | ordinary |
| `server.pid` | the running process id | ordinary |

`settings.json` has to be readable — every viewer's browser fetches it to
build the interface. That is precisely why the key, the accounts and the embed
keys live somewhere else. None of the first four should ever be committed to a
repository.

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
