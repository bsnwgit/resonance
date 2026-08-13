# App settings & accounts

Everything in this document is about how the server itself is wired, as
opposed to how the interface looks.

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

**session idle hours** is how long an idle admin session survives before it
has to sign in again. It slides: activity pushes the deadline out, so a
working admin is not signed out mid-task, while a forgotten tab expires.

Eight hours suits a workday. A shared machine wants considerably less.

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
| `app.json` | ports and session lifetime | ordinary |
| `server.pid` | the running process id | ordinary |

`settings.json` has to be readable — every viewer's browser fetches it to
build the interface. That is precisely why the key and the accounts live
somewhere else. None of the first four should ever be committed to a
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
