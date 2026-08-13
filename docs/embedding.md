# Embedding it in another application

Another application can pull this interface into its own page. Its **server**
asks this server for a session, and its page frames what comes back.

Read this first if you are the one integrating: **a microphone inside an
iframe needs `allow="microphone"` on the iframe tag, the host page itself on
HTTPS, and the permission granted on the host's origin.** Miss any one of the
three and the embed looks broken for reasons that have nothing to do with this
server. It is the single most common way an integration fails.

## What an embed key is

An admin creates a key on the **EMBEDS** tab. It fixes two things, and they
are separate on purpose:

**Capability** — what the application is permitted to do. Ask at all, open a
microphone, speak, and how many questions a minute.

**Chrome** — what it draws. Seven parts, in any combination:

| Part | What it is |
|---|---|
| `visual` | the figure |
| `transcript` | the conversation |
| `input` | the field you type in |
| `mode` | the SPACE / AUTO control |
| `talk` | the TALK button |
| `audio` | the mute toggle |
| `text` | the transcript toggle |

Both are fixed when the key is created. To change either, create a new key and
retire the old one. One key is one surface: a lobby kiosk and a support widget
are two keys, separately revocable and separately rate-limited, and the admin
list says exactly what each one draws.

### Why they are two axes and not one

**Hiding the TALK button is not the same as withdrawing the microphone.** The
control goes; the permission stands. An integrator will assume otherwise
unless it is said plainly, so it is said here: the two are narrowed
separately.

The proof that one field could not do both is a pair of the presets. `kiosk`
and `signage` draw exactly the same thing — the figure alone — and have
opposite permissions. One listens hands-free. The other must never open a
microphone.

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

## The three steps

### 1 — the host's server exchanges the key for a session

```
POST https://your-server:9701/embed/session
Content-Type: application/json

{"key": "e0123456789ab.the-secret-half"}
```

```json
{
  "token": "…",
  "src": "/embed?t=…",
  "expires_in": 3600,
  "parts": ["visual", "transcript", "input", "mode", "talk", "audio"],
  "cap": {"ask": true, "mic": true, "speak": true, "rate_per_min": 20}
}
```

Server to server, so the layout the application asked for and its right to ask
for it are settled in one call, before a browser is involved. **The key never
reaches a browser.** It is held hashed here and cannot be shown again after
creation.

### 2 — the host's page frames the session

```html
<iframe src="https://your-server:9701/embed?t=…"
        allow="microphone"></iframe>
```

The session token is a bearer token that lives in that URL, and the embed
sends it back as an `Authorization` header on everything it asks for. It is
deliberately not a cookie: a cookie set by an iframe is a third-party cookie,
and browsers block or partition those, so an embed authenticated that way
works in one browser and silently fails in the next.

The server sends `Content-Security-Policy: frame-ancestors` listing exactly
the origins on the key, so a page nobody authorised cannot render it — the
browser refuses at the only moment it can.

### 3 — optionally, the host narrows it at runtime

```js
frame.contentWindow.postMessage({
  rsn: 1, kind: 'narrow',
  parts: ['visual', 'transcript'],
  cap:   {mic: false}
}, 'https://your-server:9701');
```

A host may show **less** than the key grants, on either axis: hide the field
for anonymous visitors and reveal it for staff, run a session with the
microphone off, disclose the transcript after the first exchange. **They can
never show more.** Anything asked for beyond the key is dropped by the embed
itself rather than refused by agreement — the host page is untrusted by
definition, so "cannot add" is code that ships from here.

Wanting less than the key grants therefore needs no new key. A narrowing is
the host's own business; a widening is a conversation with this server's
admin.

The embed answers back on the same channel, to the host's origin and never to
`*`:

```js
{rsn: 1, kind: 'ready',    name, parts, cap}   // the session is up
{rsn: 1, kind: 'narrowed', name, parts, cap}   // what is in force now
```

## What the capability envelope does and does not do

Capability is enforced on the server. An embed denied the microphone gets a
403 from `/stt`; denied speech, a 403 from `/tts`; denied asking, a 403 from
`/ask`. The interface also never offers a control it knows will be refused, so
nobody meets an error they could not have avoided — but the refusal itself is
the server's.

**Be clear about the boundary.** The display listeners are open by design:
anyone who can reach the server can open the display and use `/ask` directly,
embed or no embed. What a key buys is a named, revocable, separately
rate-limited surface with a fixed layout and an audit trail — not isolation
from a host page that decides to call this server on its own account. If the
server needs to be closed to everyone but its embeds, that is the *binding and
authentication* work in the README's roadmap, and it is a different job.

## Sessions

A session lasts as long as the key says — five minutes to a day, an hour by
default — and does not slide. It is a bearer token sitting in a URL inside
somebody else's page, and it should stop working at a time the admin chose
rather than for as long as somebody keeps using it.

The grant is copied into the session when it is minted. Editing a key cannot
retroactively widen a conversation already running; a change takes effect on
the next session.

**Disabling or deleting a key ends its live sessions immediately**, rather
than letting them run to expiry. Sessions are held in memory, so a restart
ends them all — the host's server simply mints another.

Failed keys back off geometrically per address, in their own ledger, so a host
server fumbling its key cannot lock an admin out of the panel.

## Storage

`embeds.json`, mode 600, beside the other credentials. It holds the key
hashes, never the keys. Do not commit it.

The secret half of a key is 32 bytes from the system generator, so it is
hashed with a salted SHA-256 rather than the PBKDF2 the passwords get: there
is no dictionary to run against it, and stretching would only add a third of a
second to every session a host mints.
