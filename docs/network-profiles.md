# Network profiles

**SETTINGS ▸ CONNECTIONS ▸ NETWORK.** One profile is one port with one
assistant behind it. Everything on the tab answers one of three questions, and
the editor is divided into those three in that order.

- **What this port binds** — the socket this server actually opens.
- **What our own screens and people call it** — the name in links handed to
  your tablets and your users.
- **What an integrator calls it** — the name in the snippet handed to whoever
  runs a host application that embeds an assistant.

They are separate because they are genuinely different facts on some
deployments and the same fact on most. **Filling in only the first is normal.
Filling in only the second is also normal.** The third exists for the case
where outsiders arrive by a name your own equipment does not use, and is
empty on most installs.

---

## Why there is one profile per port

A port carries exactly one assistant. That was not always true — ports were
shareable, and several endpoints on one were told apart by wake word — and it
stopped being true when authentication became a property of the port: a door
with two assistants behind it can only have one lock, and would have to answer
for the looser of the two.

So the shape is fixed and worth holding on to:

```
network profile  →  one port  →  one endpoint  →  one assistant
```

Two assistants means two profiles, two ports and two names. That is the whole
reason the addresses below are per profile rather than one setting for the
server.

---

## Section 1 — what this port binds

### IP address

Which interface the listener answers on. **ANY** is every address this machine
has, and is the default.

It is picked from a list rather than typed, for the same reason the server's
own binding is: an address this machine does not have is a listener that will
not start, and there is no way to know that from a box you can type anything
into. The interface name is shown beside each address, because `10.0.0.4` on
its own is a number nobody can place.

An address that was chosen and has since gone — a lease that moved, an
interface that is down — is kept and flagged rather than silently swapped for
another. Being bound to nothing is worth seeing.

**This is a binding, not a name.** It is not what anybody types into a browser,
and it is not what goes into a link. That is section 2.

### Port

The number the socket is opened on. This is the port your reverse proxy
connects *to*, and the one the firewall would have to publish if there were no
proxy.

Two profiles cannot hold the same port on the same address. ANY collides with
everything on that port, because that is what ANY means — and the clash is
refused at save time with both names in the message, rather than discovered at
the next restart.

**The port is checked before it is accepted.** A port that passes validation
and fails to bind at the next restart is a profile that looks saved and is not,
found out at the worst possible moment. Only a profile whose address or port
actually *moved* is checked, because the panel sends every profile on every
save, and checking all of them would mean an edit to one row being refused by
the state of another.

### Plain HTTP, redirected here

An optional second socket, speaking plain HTTP, that answers on its own port
and sends every request to the HTTPS one above. Blank is none, which is the
common answer.

---

## Section 2 — what our own screens and people call it

This is the pair that decides what goes in every URL this server builds for
this profile. It is read by three things:

| Where | What it builds |
|---|---|
| A tablet being commissioned | the `/e/…` address its enrolment code is typed at |
| A tablet whose code has been spent | the assistant it is redirected to |
| A person who has just set a password | the list of assistants they may use |

### Address in links

Optional, and **a name rather than a second binding** — the listener answers on
the IP address above whatever this says.

It exists because the binding was going straight into those URLs. Bind by IP,
which is the ordinary way to bind, and everybody was handed
`https://10.0.0.4:9701` instead of a name.

**Leave it blank and nothing breaks, but the link becomes a guess.** With no
name set, the URL is built from the address the profile binds — or, when it
binds ANY and so names no single address, from the `Host:` header of whatever
request happened to build the link. Enrol one tablet from one name and another
from a second, and the same assistant is bookmarked at two different addresses.
If the header is missing altogether the fallback is `127.0.0.1`, which works
only on the machine itself.

Whatever you put here **must resolve to this server and must be covered by the
certificate**. A wildcard like `*.server.example.com` matches one label:
`ai.server.example.com` is covered, `server.example.com` is not, and
`a.b.server.example.com` is not.

### Port in links

The port *that name* is reached on, which is **not** the port in section 1.

**Blank is the answer behind a reverse proxy, and blank means none** — the
scheme's own port, 443 for HTTPS. See the worked example below.

Read only where a name is set. With no name there is no link being built out of
it.

---

## Section 3 — what an integrator calls it

### Embed app address — scheme, name, port

The address that goes into the code you hand to whoever runs a host
application: the `<script src>` their page loads the assistant from, and the
address their own server posts to for a session. It is also the value they type
into their application's own settings — pkt\* applications call it the
*Resonance AI Interface Server*.

**Empty is the normal state.** An empty box means "use the address in links
above", and only if that is empty too does it fall back to the server-wide
address under **SETTINGS ▸ ENROLL ▸ Enroll Embed APP**:

```
embed app address  →  address in links  →  the server-wide address
```

So on a deployment where outsiders and your own tablets reach a port by the
same name — which is every deployment on an internal network — you fill in
**one** box, in section 2, and this section stays empty.

Fill it in only when the two genuinely differ: a public name in front of an
internal one, a different port published to outsiders, or plain HTTP on a
segment that has no certificate. Then it wins over section 2 for embeds only,
and your own screens carry on using the name above.

**A site is never pointed at an assistant by its address.** Which assistant
answers an embedded site is decided by the *endpoint* named on that site's row
under **EndPoints ▸ SITES**, and the endpoint decides the port. That is why
there is no address field on a site: moving a site between assistants would
otherwise be an edit to somebody else's source and a deploy on their side, for
a choice that was never theirs to make.

---

## Worked example — behind a reverse proxy

A proxy terminates TLS on 443 and forwards to this server. Two assistants:

```
                              ┌─ reception.example.com ──▶ :9711  Reception
 browser ──443──▶  proxy  ────┤
                              └─ workshop.example.com ───▶ :9712  Workshop
```

The **Reception** profile:

| Field | Value | Why |
|---|---|---|
| IP address | ANY | the proxy reaches it over loopback or the LAN; nothing needs pinning |
| Port | `9711` | what the proxy forwards to |
| Plain HTTP, redirected here | *blank* | the proxy does the redirecting |
| Address in links | `reception.example.com` | the name the proxy publishes |
| Port in links | **blank** | ◀ see below |
| Embed app address | *blank* | integrators use the same name as everyone else |

### Why "Port in links" is blank here

Because **443 is implied by `https://` and must not be written down.**

The listener holds 9711. The world arrives at the proxy on 443, and the proxy
is the only thing that ever speaks to 9711. So:

- Put `9711` in this box and every link becomes
  `https://reception.example.com:9711/` — which sends people *straight past the
  proxy* to a port your firewall very likely does not publish. From inside the
  network it may even work, which is worse: it works for you and is dead for
  everybody else.
- Leave it blank and every link becomes `https://reception.example.com/` — the
  proxy's own address, on the scheme's own port, which is what you actually
  published.

The two ports in this tab are answering different questions. Section 1's port
is *what this server binds*. Section 2's port is *what the outside world dials*.
Behind a proxy those differ by definition, and the box is blank precisely
because the outside world dials nothing — it takes the default.

**Fill the box in only when there is no proxy** and the browser really does
reach this process directly on a non-standard port. Then the name and the bind
port are the same door, and the link has to say so.

---

## Reaching it directly, with no proxy

Same server, no proxy, browsers talking to the listener:

| Field | Value |
|---|---|
| IP address | ANY, or the one interface it should answer on |
| Port | `9711` |
| Address in links | `reception.example.com` |
| Port in links | `9711` |
| Embed app address | *blank* |

Here the port **is** written down, because there is nothing in front of the
server to supply a different one. Links become
`https://reception.example.com:9711/`, which is the truth.

---

## What happens if a section is left empty

| Left empty | Effect |
|---|---|
| IP address | Binds every interface. Normal. |
| Port | The profile is not bound at all, and the startup log says so. |
| Plain HTTP, redirected here | No plain-HTTP companion socket. Normal. |
| Address in links | Links fall back to the binding, then to the `Host:` header, then to `127.0.0.1`. They still work on a flat network; they are unstable and name the bind port. |
| Port in links | The scheme's own port — 443 for HTTPS. **This is the correct answer behind a proxy.** |
| Embed app address | Uses the address in links; failing that, the server-wide address under ENROLL. Normal. |

Nothing here is refused for being empty except the port in section 1, which is
what makes the profile a listener at all.
