# Embedding it in another application

Your assistant, on somebody else's web page — sitting in the page, or as a
bubble in the corner that opens into a panel. Their visitors talk to it
without leaving the page they are on.

Two jobs. **You** create a key here and hand over the code the panel writes
for you. **They** add one endpoint to their application and one tag to their
page template. Nothing else, ever.

---

## Read this before you start

An embed means **every visitor's browser talks to this server directly**. Not
their web server on their visitors' behalf — each browser, over the internet
if their site is public. Three things follow, and none of them is optional.

**A certificate their browsers trust, reached by a name that is on it.** A
browser will not quietly load an iframe from a certificate it does not trust,
and inside an iframe there is no warning to click through: it fails, silently,
for everybody, with nothing in the console that names the cause. The
self-signed certificate `make-cert.sh` writes is fine for a screen on your own
wall and fatal here.

Two halves, and the second catches people. *Trusted* means either a public
certificate, or an internal CA whose root is installed on every machine that
will use the embed — which is a decision about who those people are: an
internal CA covers your staff and covers nobody else, so a contractor, a phone
off the VPN, or anything on the public internet still gets the blank frame.
*By a name that is on it* means exactly that — an IP address is not on a
certificate unless somebody put it there, and a wildcard covers one label and
never its own parent, so `ai.example.internal` can work while
`example.internal` and `10.0.0.5` both fail. Set **Address integrators reach
this on** to a name you have checked in a browser, not to whatever you happen
to type into your own address bar.

**Their pages on HTTPS.** A microphone will not open otherwise. The loader
sets `allow="microphone"` for them, but that is only one of the three things a
microphone in an iframe needs — the other two are the host page on HTTPS and
the permission granted on their origin.

**The assistants closed to anonymous callers.** Set an assistant's permission
to require a sign-in, under PROFILES ▸ AUTHORIZE. **An embed session counts as
a signed-in caller** — that is the whole point of it — so your embeds keep
working while everybody who merely found the port stops. Leave them open and
the key buys you nothing at all: `/ask` is reachable by anyone who can reach
the server, embed or no embed.

**And the key ticked onto the assistants it may use.** Where a profile says
ONLY THESE, it lists groups, screens, people — and embeds. A key that is not
on the list is refused, exactly as an unnamed screen is, so six applications
on one server are six separately grantable doors rather than one shared one.
This is the step that is easy to miss: everything else can be right and the
embed still answers *this embed may not use that endpoint* until it is
ticked.

---

## What an embed key is

An admin creates a key under **ENROLLMENTS ▸ EMBED** — beside the two other things that enrol, a person and a screen. It fixes four things.

### Capability — what the application may do

Ask at all, open a microphone, speak. Enforced on the server: an embed denied
the microphone gets a 403 from `/stt`, denied speech a 403 from `/tts`, denied
asking a 403 from `/ask`.

### Chrome — what it draws

Seven parts, in any combination:

| Part | What it is |
|---|---|
| `visual` | the figure |
| `transcript` | the conversation |
| `input` | the field you type in |
| `mode` | the SPACE / AUTO control |
| `talk` | the TALK button |
| `audio` | the mute toggle |
| `text` | the transcript toggle |

**Hiding the TALK button is not the same as withdrawing the microphone.** The
control goes; the permission stands. The proof that one field could not do
both is a pair of the presets: `kiosk` and `signage` draw exactly the same
thing — the figure alone — and have opposite permissions. One listens
hands-free. The other must never open a microphone.

### Who is asking

Off by default. Ticked, the host's server must name whoever is signed in to
their application when it asks for a code, and every question is recorded
against that person.

**Their server, never their browser.** Their application authenticated the
person and holds the key; a browser saying who it is would be a text field
anybody could type into. A code request that names nobody is **refused**, so a
host that forgets finds out on the afternoon they wire it up rather than
months later through an audit trail full of nobody.

Leave it off for a public site. There are no logins there to report.

### How much it may ask

Two numbers, because one cannot say the thing that matters.

| | |
|---|---|
| **Questions a minute** | everything this application asks, added up across all its visitors. The ceiling, and the bill. |
| **…and one visitor's share** | one browser. Has to be the smaller of the two. |

A key sized for a busy application is a key one visitor could spend on their
own; a key sized for one visitor is a key the second visitor finds empty. Set
the visitor's share comfortably above what a person actually does — a few a
minute — so it catches a page stuck in a loop rather than somebody in a hurry.

Where the key names the person, the visitor's window follows **them** rather
than their tab, so reloading the page buys nothing.

### Presets

Starting points, not separate kinds of key. Edit any of them.

| Preset | Draws | May |
|---|---|---|
| `full` | everything | ask, mic, speak |
| `console` | everything but the transcript toggle | ask, mic, speak |
| `voice` | the figure and the voice controls | ask, mic, speak |
| `chat` | the transcript and the field | ask |
| `kiosk` | the figure alone | ask, mic, speak |
| `signage` | the figure alone | speak |

### Arrangements that are refused

An arrangement with an orphaned part is refused when you create it, naming the
part — rather than left for a host developer to work out from a 400 three
weeks later.

- `text` without `transcript` — a button that toggles nothing.
- `mode` without `talk` — configuring how a microphone decides you have
  finished speaking, on an arrangement with no microphone control.
- `talk` or `mode` without the microphone capability — a control that cannot
  work.
- `audio` without the speak capability — muting a voice there is not.
- `input` or `talk` without the ask capability — a way to ask on a key that
  may not.
- `input` with neither a transcript nor a voice — typing into a void.
- one visitor allowed more a minute than the whole key is.

One key is one surface. A lobby kiosk and a support widget are two keys,
separately revocable and separately rate-limited, and the admin list says
exactly what each one draws.

---

## What you hand over

Set **Address integrators reach this on** at the top of that tab first —
the name a stranger's browser reaches this server by, which is not necessarily
the name your own screens use. Then create the key.

The panel shows the key **once**, with working code written against that
address and shaped by that key. Copy both parts and send them over. Nothing on
this server can show the key again.

### 1 — their server: one endpoint, behind their login

```js
// /api/resonance-code — behind your existing login. Anyone who can
// reach this endpoint gets a session, so it must not be public.
const RESONANCE = 'https://ai.example.com:9701';
const KEY = process.env.RESONANCE_KEY;

app.get('/api/resonance-code', requireLogin, async (req, res) => {
  const r = await fetch(RESONANCE + '/embed/session', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      key: KEY,
      user: {id: req.user.id, name: req.user.name,
             roles: req.user.roles},
    })
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) return res.status(502).json({error: j.error || 'no code'});
  res.json({code: j.code});
});
```

Node, Python and PHP are all offered in the panel. The `user` block is only
there when the key requires it.

**The key is not in the snippet.** It goes in that server's environment as
`RESONANCE_KEY`, so the code can be pasted into a chat message or committed to
a repository and the credential cannot.

### 2 — their page: one tag, in the template

```html
<script src="https://ai.example.com:9701/embed.js"
        data-code-url="/api/resonance-code"
        data-style="bubble"></script>
```

| Attribute | |
|---|---|
| `data-code-url` | **required** — their endpoint from step 1 |
| `data-style` | `bubble` (default) or `inline` |
| `data-target` | for `inline`: a selector for the element to fill |
| `data-label` | the launcher's label, default `Ask` |
| `data-side` | `right` (default) or `left` |
| `data-width` `data-height` | the panel, in pixels |
| `data-open` | start with the panel open |

The loader exposes `window.Resonance` with `open()`, `close()`, `toggle()` and
`destroy()`, so their own button can drive it.

---

## What happens per visitor

1. Someone opens a page in their application.
2. The tag pulls `embed.js` from this server.
3. `embed.js` calls **their** `/api/resonance-code`, carrying their login
   cookie.
4. Their server checks who is signed in and asks this server for a code.
5. `embed.js` frames `/embed?c=…` and draws the bubble.
6. The frame trades the code for a session token, held in memory.
7. They talk to it.

Steps 3–7 again on the next page. A fresh code, a fresh session, one per
visitor.

---

## Why a code and not the token

The session token is a bearer credential — whoever holds it **is** that embed
— and the obvious design puts it straight into the iframe's URL. A URL inside
somebody else's page is the worst available place for one. Their own scripts
set it and can read it back; so can their analytics, their error reporter, the
browser's history, a referrer, and a screenshot in a support ticket. The
origin allow-list does not help: it stops another site *framing* this, and
does nothing whatever against `curl` holding the token.

So the URL carries a **code**: good once, and for about a minute. The frame
trades it for the token at load, the code burns, and the token exists only in
that page's memory. It is never written to a URL, a cookie, or storage.

The key, meanwhile, never reaches a browser at all — it is held hashed here
and cannot be shown again after creation.

---

## Sessions, and how they end

A session lasts as long as the key says — five minutes to a day, an hour by
default — and does not slide. It is somebody else's page holding it, and it
should stop at a time the admin chose rather than for as long as anyone keeps
using it.

`embed.js` renews it a minute before it expires: it fetches a fresh code and
posts it into the frame, which swaps its token **without reloading**. The
conversation survives. Reloading the frame would also have worked and would
have thrown away the last ten minutes for no reason the person could see.

The grant is copied into the session when it is minted, so editing a key
cannot retroactively widen a conversation already running. A change takes
effect on the next session — and a renewal is a next session.

**Disabling or deleting a key ends its live sessions immediately**, and burns
any codes minted but not yet spent. Sessions are held in memory, so a restart
ends them all; the host's server simply mints another.

Failed keys back off geometrically per address, in their own ledger, so a host
server fumbling its key cannot lock an admin out of the panel.

---

## Narrowing it at runtime

A host may show **less** than the key grants, on either axis — hide the field
for anonymous visitors and reveal it for staff, run a session with the
microphone off, disclose the transcript after the first exchange:

```js
frame.contentWindow.postMessage({
  rsn: 1, kind: 'narrow',
  parts: ['visual', 'transcript'],
  cap:   {mic: false}
}, 'https://ai.example.com:9701');
```

**They can never show more.** Anything asked for beyond the key is dropped by
the embed itself rather than refused by agreement — the host page is untrusted
by definition, so "cannot add" is code that ships from here. Wanting less than
the key grants therefore needs no new key; wanting more is a conversation with
this server's admin.

The embed answers on the same channel, to the host's origin and never to `*`:

```js
{rsn: 1, kind: 'ready',    name, parts, cap, expires_in}
{rsn: 1, kind: 'narrowed', name, parts, cap, expires_in}
{rsn: 1, kind: 'renewed',  name, parts, cap, expires_in}
```

Two surfaces on one page — a figure in the corner and a chat panel — is two
codes off one key, framed separately and narrowed differently. One key, one
revocation, one budget.

---

## Doing it without the loader

`embed.js` is a convenience, not the interface. A host who wants their own
launcher can do the two calls themselves: `POST /embed/session` server-side
for a code, then frame `https://…/embed?c=…` with `allow="microphone"`. They
then own the renewal, the bubble, and the message-origin checks — which is
three of the four things the loader exists to get right.

---

## What the capability envelope does and does not do

**Be clear about the boundary.** A key buys a named, revocable, separately
rate-limited surface with a fixed layout and an audit trail. It does **not**,
on its own, isolate this server from a host page that decides to call it
directly — anyone who can reach the display listener can use `/ask`, embed or
no embed.

The thing that closes that door is the first section of this document:
requiring a sign-in on each assistant, which an embed session satisfies and an
anonymous caller does not. Do both. The key is what makes an embed
accountable; the permission is what makes the server closed.

---

## Storage

`embeds.json`, mode 600, beside the other credentials. It holds the key
hashes, never the keys. Do not commit it.

The secret half of a key is 32 bytes from the system generator, so it is
hashed with a salted SHA-256 rather than the PBKDF2 the passwords get: there
is no dictionary to run against it, and stretching would only add a third of a
second to every session a host mints.

Questions asked through a key that names people are recorded in `turns.json`
against the key and the person. Where a key does not name people, nothing is
recorded — an anonymous row is collecting for its own sake.
