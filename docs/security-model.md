# Security model

What a browser can obtain from this server, what it cannot, and the exact
limits of both. For how to operate the admin interface see
[Administration](administration.md); for how the pieces fit together see
[Architecture](architecture.md).

## What reaches a browser, and what never does

Three tiers, and the boundary between them is the whole of the model:

| tier | contents | who can read it |
| --- | --- | --- |
| **never leaves the server** | API keys, the Home Assistant token, adapter base URLs, password hashes | nobody, through any browser |
| **served to the display** | the settings document: appearance. The routes document: names, greetings, voices, wake words and how strictly each matches | today, anyone who can reach the port |
| **held by the browser, unreadable by it** | the device token, in an `HttpOnly` cookie | the server, on presentation |

The first row is the one that matters and it is absolute: no credential and no
upstream address is in any response the display listeners produce. Reading
everything a browser can obtain gets you no closer to reaching Home Assistant
or a paid API than reading nothing.

**You cannot keep a secret in a page you serve to somebody.** A token
embedded in `index.html` can be read out of it by whoever received the file,
so it is obfuscation rather than access control — the same reason the identity
design refuses to encrypt anything in the browser and keeps the secrecy in the
server-side mapping.

So the boundary is not *which fields are hidden*. It is **which devices may
ask at all**, and there are two mechanisms for that:

- **The network.** Bind to one address, firewall the port, and put the wall
  displays on their own isolated VLAN. An unapproved device cannot open a
  connection, so there is nothing to authorise. This is available now and is
  the strongest of the two.
- **The device token** — built. Server-issued on the first visit, `HttpOnly` so
  page script genuinely cannot read it, and an admin approves the device.
  `curl` does not have the cookie. A guest's phone is issued a token of its own
  and refused, because nobody approved that one.

### The limitations, stated exactly

**A person using an approved device can read what that device reads.** This is
not fixable — the page runs on hardware they hold — and it is worth being
clear about how little it costs:

- On a **wall display**, that person is standing in your hallway, and they can
  already operate the house by talking to it. Reading the wake words they
  would have to say anyway is not the exposure in that room.
- On a **personal device**, that person is its owner, who says those wake
  words daily. The document tells them nothing they did not already have.
- In **neither case** does it yield a credential, an endpoint, or anything
  that would let them reach Home Assistant except by asking this server —
  which is the thing they were already allowed to do.

**Two people sharing one approved device cannot be told apart.** Approval is
per device. Telling the people using it apart means each of them signing in
with their own account, which is what an endpoint set to REQUIRED insists on —
and a shared wall screen is exactly the case that cannot satisfy it.

**A display learns the wake word of a route it may not use, and that is
deliberate.** It has to: recognising the house's name is the only way it can
*drop* an utterance addressed to the house instead of passing it into whatever
conversation it was already having. Withholding the word would not make the
phone in the room safer — it would make it answer on the house's behalf. What
the word buys whoever reads it is nothing: saying it into an unapproved device
is refused at `/ask`, by this server, on every request.

**What is exposed today:**

| | to | |
| --- | --- | --- |
| the settings document | anything that can reach the port | appearance values |
| a route's name, greeting and voice | anything that can reach the port | what makes a newly hung display look right before anybody approves it |
| a route's wake words and strictness | any browser that has said hello, approved or not | the gate rule above |
| a route's adapter, address and key | nobody, through any browser | not published at any tier |

The network is still the stronger of the two boundaries, and the VLAN is still
the right answer for wall displays. What the token changes is that reaching the
port is no longer the same as being able to *use* what is on it.

## An embed reaching the host application's data

A site can be granted operations on the application it is embedded in. That is
a new surface, and it is worth being exact about what it does and does not
move.

**No credential of theirs is held here, and no request is made from here.**
Every call is made by the host's own page, same-origin, carrying the session
of whoever is signed in to their application. So the ceiling on what an embed
can read is *what that person could already read* — enforced by their
application, on every request, exactly as it would be if they had clicked the
same thing themselves. Nothing about this widens a person's reach; it shortens
the path to what they already had.

**Three authorities, and the narrowest wins:**

| | who decides | where it lives |
| --- | --- | --- |
| the ceiling | the application's owner | `/.well-known/resonance.json`, on their own origin |
| what is enabled | this server's admin | ticks on the site's row |
| what that person may do | their application | their session, on every request |

The middle one can only narrow. An admin here cannot grant an operation the
application did not declare, which is what makes this safe to embed in an
application somebody else runs — and **no grant file means read verbs only**,
because silence must never grant a write.

**The spec and the grant file must come from a registered origin.** Without
that rule the spec field is a text box this server will fetch from any address
on its network, and the grant file is a document anybody could serve while
claiming to speak for that application.

**The model's output is untrusted input.** A model that invents an operation,
renames a parameter or puts a slash in a path segment is a model failing in
the ordinary way, and each of those would otherwise arrive at somebody's API
as a request their page made in their name. Every proposed call is resolved
against the operation's own description and checked against the session's
grant here; `embed.js` checks again at the far end against the operation's
path template, so a tampered frame still reaches only declared paths.

**The host page could lie about what its application said.** It could — and it
could equally lie about the question, which it has always been able to do. The
host page is untrusted by definition; what it cannot do is reach an operation
the site was not granted, which is checked on the way out and again on the way
back in.

**What the log keeps of all this.** The request, and never the response. A
call is recorded as its method, path and query — the same line the host's own
access log carries, so the two can be compared — and the answer is recorded as
its status code and byte count alone. The body never reaches `server.log`, and
`server.log` travels: it is the stream a syslog sink carries off the machine.
An application's data must not leave by that route because somebody was
debugging a 400.

**A write is confirmed by the frame, not by the host.** A confirmation drawn
by the party that wants the action is not a confirmation. It names the real
values, per action, with no session-wide switch to turn it off.

**What this does not do.** It is not a general answer to recency: an embed
reaches the application it is embedded in and nothing else, there is no web
search, and a display on a wall is inside no application and has no page to
make a request from. See [Reaching the host application's
data](host-data.md).
