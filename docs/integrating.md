# Integrating it into your application

**For the developer on the receiving end.** Somebody has run an assistant on a
server and given you a key. This is everything you need to put it in your
application without asking them a question — the exact request and response
shapes, the status codes, the timings, what fails and how, and the one case
the drop-in loader does not cover.

The other half of this is [Embedding](embedding.md), which is written for the
admin who makes the key. Read that one if you want to know *why* it is shaped
this way. Read this one to build against it.

If what you actually want is the panel answering questions about **your**
application's records rather than sitting beside them, that is built too —
see [Reaching the host application's data](host-data.md), and the section at
the end of this document for the two files and one message it costs you.

---

## What you should have been handed

Three things. If any is missing, go back and ask — none of them can be worked
out from the others.

| | |
|---|---|
| **The address** | `https://host[:port]`, e.g. `https://ai.example.com:9701`. Both your server and your visitors' browsers reach it |
| **The key** | `e0a1b2c3d4e5.<secret>`. Shown once, at creation. It goes in your server's environment and never anywhere else |
| **Whether it needs a person** | if yes, every code request must name whoever is signed in to your application, or it is refused |

Worth confirming two more while you are asking, because both fail late and
badly:

- **Your origins are on the key's allow-list.** Every origin your application
  is served from — staging included — must be listed on the key, or the
  browser refuses to render the frame. `https://app.example.com` and
  `https://app.example.com:8443` are different origins; so are `http` and
  `https` of the same host.
- **The key is ticked onto the assistants it may use.** Where an assistant is
  set to ONLY THESE, an unticked key is refused at `/ask` with *this embed may
  not use that endpoint*. Everything else can be right and it will still not
  answer.

---

## Which of two paths you are on

The difference is how your own front end authenticates to your own back end.
It decides which integration you write, and it is worth settling before you
write either.

**Your session is a cookie.** Your pages are server-rendered, or your SPA
authenticates with a cookie the browser sends by itself. Use the loader: one
endpoint and one script tag, and renewal, the launcher, the microphone
attribute and the origin checks are all handled for you. → [The loader](#path-1--the-loader)

**Your session is a token held in memory.** Your SPA keeps an access token in
a variable and sends it as `Authorization: Bearer …`. **The loader cannot help
you.** It fetches your code endpoint with `credentials: 'include'` and no way
to attach a header, so it will get your login page or a 401. Do the two calls
yourself — it is about forty lines. → [Without the loader](#path-2--without-the-loader)

There is no third path today. A `getCode` callback on the loader would collapse
these back into one and has been asked for; until it exists, a token-authenticated
SPA writes its own mount.

---

**Which assistant answers is not yours to set, and not in your code.** It is a
property of the key, chosen by whoever issued it, and it can be changed without
anything on your side moving. Do not hardcode an assumption about which model
or which endpoint is behind the address you were given.

## What happens per visitor, either way

1. Someone opens a page in your application.
2. Your **server** posts your key to `POST /embed/session` and gets back a
   **code** — good once, for sixty seconds.
3. Your **page** frames `https://<address>/embed?c=<code>`.
4. The frame trades the code for a session token, which lives in that page's
   memory and is never written to a URL, a cookie, or storage.
5. They talk to it.
6. A minute before the session ends, step 2 again, and the new code is posted
   into the frame — which swaps its token without reloading.

**The key never reaches a browser.** That is the whole design. A code in a URL
is worth sixty seconds and one use; a session token in a URL would be readable
by your own scripts, your analytics, your error reporter, the browser history,
a referrer, and a screenshot in a support ticket.

---

## The contract

### `POST /embed/session`

Server to server. Your key is the whole of the authentication — there is no
cookie and no origin check, because there is nothing ambient to abuse.

**Request.** `Content-Type: application/json`. Exactly two fields are read and
anything else is ignored:

```json
{
  "key": "e0a1b2c3d4e5.SECRET",
  "user": {"id": "u_1234", "name": "Jane Doe", "roles": ["staff"]}
}
```

| Field | |
|---|---|
| `key` | **required.** `<id>.<secret>`, verbatim from your environment |
| `user` | **only where the key requires it.** Omit it entirely otherwise |
| `user.id` | required if `user` is present at all; a `user` with no id is treated as no user, so a key that requires one will refuse. Truncated to 64 characters |
| `user.name` | optional, for the audit trail. Truncated to 64 |
| `user.roles` | optional, list of strings. Up to 16, each truncated to 32. See [what we do with them](#what-happens-to-what-you-send) — today, nothing |

**`200`:**

```json
{
  "code": "8Kx…",
  "src": "/embed?c=8Kx…",
  "code_expires_in": 60,
  "expires_in": 3600,
  "parts": ["visual", "transcript", "input", "talk"],
  "cap": {"ask": true, "mic": true, "speak": true,
          "rate_per_min": 20, "rate_per_visitor": 10}
}
```

| Field | |
|---|---|
| `code` | the one-use handover code. Put it in the frame's URL |
| `src` | the same code as a path, for convenience — join it to the address |
| `code_expires_in` | **60.** How long you have to spend the code |
| `expires_in` | the **session's** length in seconds, once claimed. This is the one you schedule renewal against |
| `parts` | which controls the frame will draw, of `visual`, `transcript`, `input`, `mode`, `talk`, `audio`, `text` |
| `cap` | what it may do, and its two rate limits |

`parts` and `cap` are informational — the frame enforces them itself. They are
returned so your server can decide things like panel height without a second
round trip.

**Errors.** Every one is `{"error": "<a sentence in English>"}`. There is no
machine-readable code field; branch on the status.

| Status | Means | What to do |
|---|---|---|
| `400` | malformed body, **or** the key requires a person and you sent no `user.id` | Fix the call. This will not come right on its own |
| `401` | the key is not recognised. One message for a bad id and a bad secret alike | Check `RESONANCE_KEY` reached the process |
| `403` | the key is disabled | The admin turned it off. Stop calling |
| `404` | you are talking to the admin port | Use the display address you were given |
| `429` | too many **failed** key attempts from your address | See [rate limits](#rate-limits-and-429s) — this one is not about volume |

### `POST /embed/claim`

**The frame's own call, not yours** — unless you are doing without the loader,
in which case the frame is still the one making it and you are only choosing
when.

```json
{"code": "8Kx…"}
```

**`200`:**

```json
{"token": "…",
 "embed": {"name": "Support widget",
           "parts": ["visual", "transcript", "input"],
           "cap": {"ask": true, "mic": false, "speak": true,
                   "rate_per_min": 20, "rate_per_visitor": 10},
           "origins": ["https://app.example.com"],
           "expires_in": 3600}}
```

**`403`** — *this embed code is expired, already used, or was never issued.*
All three, one message. A code is spent by exactly one caller: two browsers
racing the same code cannot both come away with a session.

### `GET /embed?c=<code>`

The framed interface. The code is **read and not spent** here — it is read to
set `frame-ancestors` on the page that will spend it a request later.

`403` if the code is expired, spent or unknown. Deliberately not a `404`: the
route is real, and a `404` sends you looking for a deployment problem instead
of at a code that aged out.

---

## Path 1 — the loader

### Your server: one endpoint, behind your login

```js
// /api/resonance-code — behind your existing login. Anyone who can reach
// this endpoint gets a session, so it must not be public.
const RESONANCE = 'https://ai.example.com:9701';
const KEY = process.env.RESONANCE_KEY;

app.get('/api/resonance-code', requireLogin, async (req, res) => {
  const r = await fetch(RESONANCE + '/embed/session', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      key: KEY,
      user: {id: req.user.id, name: req.user.name, roles: req.user.roles},
    })
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) return res.status(502).json({error: j.error || 'no code'});
  res.json({code: j.code});
});
```

Drop the `user` block where the key does not require it. Node, Python and PHP
are all offered in the panel, rebuilt for your key, under ACCESS ▸ SITES.

**The endpoint must be behind your login.** Anyone who can reach it gets a
session on your key and spends your rate limit.

**Return `{"code": …}`.** That is the only field the loader reads.

### Your page: one tag

```html
<script src="https://ai.example.com:9701/embed.js"
        data-code-url="/api/resonance-code"
        data-style="bubble"></script>
```

| Attribute | |
|---|---|
| `data-code-url` | **required** — your endpoint from above |
| `data-style` | `bubble` (default) or `inline`. There are only these two; anything else is treated as `bubble` |
| `data-target` | for `inline`: a CSS selector for an element that **already exists** when the script runs |
| `data-label` | the launcher's label and the frame's title, default `Ask` |
| `data-side` | `right` (default) or `left` |
| `data-width` `data-height` | the panel in pixels, default 400 × 620. Both are ignored on a viewport under 520px wide, where the panel goes full-screen instead |
| `data-open` | present, or `"true"`, to start with the panel open |

`window.Resonance` is exposed with `open()`, `close()`, `toggle()`,
`destroy()` and `frame`, so your own button can drive it.

### What the loader does for you

The four things that are easy to get subtly wrong, and three of which fail
silently:

- **`allow="microphone"` on the iframe.** Without it the microphone is refused
  inside the frame no matter what the key grants and no matter that your page
  has permission. It is the single most common way an integration fails.
- **Renewal without a reload**, so the conversation survives.
- **Origin checks on incoming messages**, so another frame in your page cannot
  impersonate the assistant.
- **Shadow DOM isolation** for the bubble, so your `button {}` rule does not
  restyle the launcher and its rules do not leak onto your buttons.

### What it does *not* do — read this before you ship

**It does not retry. Anything. Ever.**

- If the first call to your code endpoint fails, it writes one
  `console.error` naming the address and stops. There is no bubble on the page
  until a reload.
- If a **renewal** fails, it writes one `console.warn` and **does not try
  again**. The session then runs out and questions start being refused.

This is safe — a failing endpoint will not be hammered, and a rate limit will
not be made worse — but there is no recovery. If your application is long-lived
in one page, and a single network blip during a renewal window is not acceptable
to you, watch for it and call `Resonance.destroy()` and remount:

```js
// The loader logs and gives up; this notices and restarts it.
window.addEventListener('online', () => {
  if (window.Resonance) { window.Resonance.destroy(); location.reload(); }
});
```

**Nothing reads or sends `Retry-After`.** It is not set by the server on any
response and not honoured by the loader. If you write your own mount, you are
free to back off however you like; nothing will tell you how long to wait.

---

## Path 2 — without the loader

For a SPA whose token is in memory, and for anyone who wants their own
launcher. You are writing four things the loader would have written: the
mount, the renewal, the origin check, and `allow="microphone"`.

```js
const RESONANCE = 'https://ai.example.com:9701';

// YOUR fetch, with YOUR auth. This is the whole reason to be on this path.
async function getCode() {
  const r = await fetch('/api/resonance-code', {
    headers: {Authorization: 'Bearer ' + auth.accessToken()},
    cache: 'no-store',
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.code) throw new Error(j.error || ('HTTP ' + r.status));
  return j.code;
}

let frame = null, timer = 0;

async function mount(into) {
  const code = await getCode();
  frame = document.createElement('iframe');
  frame.src = RESONANCE + '/embed?c=' + encodeURIComponent(code);
  // THE ONE EVERYBODY MISSES. Without it the microphone is refused inside
  // the frame whatever the key grants, and it reads as a broken assistant.
  frame.setAttribute('allow', 'microphone');
  frame.style.cssText = 'width:100%;height:100%;border:0;display:block';
  into.appendChild(frame);
}

// Only our frame, only our origin. Your page embeds other things.
window.addEventListener('message', e => {
  if (!frame || e.source !== frame.contentWindow) return;
  if (e.origin !== RESONANCE) return;
  const m = e.data;
  if (!m || m.rsn !== 1) return;
  if (m.kind === 'ready' || m.kind === 'renewed') schedule(m.expires_in);
});

// A minute early, so a failure has a minute to be retried in — and unlike
// the loader, this one retries.
function schedule(seconds) {
  clearTimeout(timer);
  timer = setTimeout(renew, Math.max(30, (seconds || 0) - 60) * 1000);
}

async function renew(attempt = 0) {
  try {
    const code = await getCode();
    frame.contentWindow.postMessage({rsn: 1, kind: 'renew', code}, RESONANCE);
  } catch (e) {
    // Four tries inside the minute of headroom, then give up quietly.
    if (attempt < 3) setTimeout(() => renew(attempt + 1), 5000 * (attempt + 1));
    else console.warn('[resonance] session will lapse: ' + e.message);
  }
}

function unmount() { clearTimeout(timer); if (frame) frame.remove(); frame = null; }
```

Call `unmount()` when your route changes. A frame left in a detached
container keeps its session and its renewal timer.

### The message channel

Both directions carry `rsn: 1`. It is a marker, not a version negotiation —
nothing advertises which message kinds a given server understands.

**Out, from the frame to you** — always to your origin, never to `*`:

```js
{rsn: 1, kind: 'ready',    name, parts, cap, expires_in, tools}
{rsn: 1, kind: 'narrowed', name, parts, cap, expires_in}
{rsn: 1, kind: 'renewed',  name, parts, cap, expires_in, tools}
{rsn: 1, kind: 'call',     id, op, method, path, query, body, writes}
```

`tools` is the list of operations this session may ask **your** application
for, and `call` is it asking. Both are empty and silent unless somebody has
granted operations on the site — see [Answering about your own
data](#answering-about-your-own-data) at the end of this document.

**In, from you to the frame** — post to the address, never to `*`:

```js
{rsn: 1, kind: 'renew', code}
{rsn: 1, kind: 'narrow', parts: ['visual', 'transcript'], cap: {mic: false}}
{rsn: 1, kind: 'result', id, status, body}
```

**There is no other API.** You cannot put a question in, read the transcript,
or be told a turn finished. `result` is not an exception: it answers a `call`
the panel made and cannot start anything. Your server can `POST /ask` itself, but that
starts a separate conversation — it does not join the one the frame is having.
If you are scoping work that depends on reading or driving the conversation,
that does not exist yet; say so early.

---

## Narrowing what is drawn

A host may show **less** than the key grants, on either axis — hide the field
for anonymous visitors and reveal it for staff, run with the microphone off,
disclose the transcript after the first exchange:

```js
frame.contentWindow.postMessage({
  rsn: 1, kind: 'narrow',
  parts: ['visual', 'transcript'],
  cap: {mic: false}
}, RESONANCE);
```

**You can never show more.** Anything asked for beyond the key is dropped by
the embed itself rather than refused by agreement — your page is untrusted by
definition. Wanting less than the key grants needs no new key; wanting more is
a conversation with the admin.

A narrowing survives a renewal. You asked for less; a renewal is not you
changing your mind.

---

## Sessions, and how they end

| | |
|---|---|
| **Code** | 60 seconds, one use |
| **Session** | whatever the key says: 5 minutes to 24 hours, an hour by default. Read `expires_in` rather than assuming |

**A session does not slide.** It stops at a time the admin chose, not after a
period of inactivity, and using it does not extend it.

Renewal is a fresh code posted into the frame, which swaps its token in place.
The conversation survives. Reloading the frame would also have worked and would
have thrown away the last ten minutes for no reason the person could see.

**A session carries the envelope it was minted with.** What the key allowed and
what it drew at the moment your server asked for it, not what it allows now —
so a running conversation is never widened or narrowed mid-sentence.

**These end sessions immediately, not at expiry:** the key being disabled, the
key being deleted, the key being reissued after a leak, the admin **changing
what the key may do, what it draws, which origins may frame it, how long a
session lasts, or whether you must name the person**, and the server
restarting. Sessions are held in memory. In every case your server simply mints
another code and your page mounts again inside whatever the key now says — so
treat "the frame says it could not start its session" as ordinary, not as an
incident.

That is why an edit is dropped on you rather than waiting: a key narrowed at
11:00 with sessions left running would be narrower on paper and not in fact
until the last of them expired. Renaming a key drops nothing.

**One edit you have to follow.** If the admin turns on *the host must name the
person*, `/embed/session` starts requiring a `user` from that moment and
answers `400` without one. Nothing else about the key needs anything from your
side — the id does not change, and neither does `RESONANCE_KEY`.

---

## Rate limits and 429s

Three different things return `429` and they mean different things. Do not
write one handler for all of them.

| Where | Trigger | Shape |
|---|---|---|
| `/embed/session` | **5+ failed key attempts** from your address | Geometric backoff, per address, 15s doubling to a 300s cap. Not about volume — a correct key never sees it |
| `/ask` | one **visitor** over their share | *you are asking faster than this is set up to answer* |
| `/ask` | the **key** over its total | *this embed is over its rate limit* |

The two `/ask` limits are the ones that matter in production. Defaults are 10 a
minute per visitor and 20 a minute for the whole key; each can be set between 1
and 600, and the per-visitor number must be the smaller.

**The visitor is checked first, deliberately.** One page stuck in a render loop
gets told *it* is asking too fast, rather than everybody else being told the
application is busy about a limit one browser is the whole of.

Where the key names people, the visitor window follows **the person** rather
than the tab — so reloading the page does not reset it. Where it does not, the
window is per session, and a reload does buy a fresh one. That is a known
limit, and the key's own ceiling is what actually caps it.

**No `Retry-After` on any of them.** Back off on your own schedule.

---

## What happens to what you send

Be able to answer this when someone asks what leaves your application.

| | |
|---|---|
| `user.id` | The rate-limit bucket where the key names people, so re-minting a session does not buy a fresh budget. Written to the turn log |
| `user.name` | Written to the turn log beside the id, so *who said that* has an answer |
| `user.roles` | **Recorded on the session and otherwise inert.** Nothing is gated on them, and they are not written to the log |

**Roles gate nothing today.** There is no vocabulary to match and no effect to
observe — send them or do not. If you need role-differentiated behaviour now,
use two keys, or narrow the frame from your page.

**Where the key does not name people, nothing is logged at all.** Not an
anonymous row — no row. An anonymous transcript entry is collecting for its own
sake.

Access control is not roles. It is which assistants the **key** is ticked onto,
which the admin sets and you cannot see.

---

## TLS — the failure that has no error message

**A browser will not load an iframe from a certificate it does not trust, and
inside an iframe there is nothing to click through.** It fails, silently, for
everybody, with nothing in the console that names the cause. There is no
client-side escape hatch and no flag you can set.

Two halves, and the second is the one that catches people.

**Trusted** means either a publicly-trusted certificate, or an internal CA
whose root is installed on **every machine that will open your application**.
An internal CA covers staff laptops and covers nobody else — a contractor, a
personal phone, anything off the VPN, and anything on the public internet all
get the blank frame. If your application is or will be internet-facing, an
internal CA is not enough and it is worth settling before you build.

**Reached by a name that is on the certificate.** An IP address is not on one
unless somebody put it there, and a wildcard covers one label and never its own
parent — `ai.example.internal` can work while `example.internal` and
`10.0.0.5` both fail.

**And your own pages must be on HTTPS**, or the microphone will not open even
with everything above correct. A microphone in an iframe needs three things:
the frame's `allow` attribute, your page on HTTPS, and the permission granted
on your origin. The loader supplies the first; the other two are yours.

If you get a blank frame with a clean console, this is where to look first.

---

## Before you call it done

- [ ] The key is in the server's environment, not in any file you commit
- [ ] The code endpoint is behind your login, and you have checked it 401s when signed out
- [ ] Every origin you serve from — production **and** staging — is on the key
- [ ] You have opened it in a browser that has never seen this server and got no certificate warning
- [ ] Your pages are on HTTPS, if the microphone is granted
- [ ] The assistant you expect it to reach has the key ticked under its permissions
- [ ] You have watched a renewal happen — set the key's session to 5 minutes and leave a page open for six
- [ ] You have unmounted on a route change and confirmed the timer stops
- [ ] You know what your page does when the code endpoint is down: today, with the loader, the answer is "no bubble and one console line"

---

## If something is wrong

| What you see | Almost always |
|---|---|
| Blank frame, nothing in the console | The certificate. See above |
| Frame renders, says it could not start its session | The code expired before it was spent, or was already used. Do not mint codes ahead of time |
| Nothing on the page, one `console.error` from `[resonance]` | Your code endpoint 401'd, 404'd, or returned no `code` |
| *this embed may not use that endpoint* | The key is not ticked onto that assistant. Only the admin can fix it |
| *this key requires the person asking to be named* | Send `user.id`, from whoever is signed in to **your** application |
| The microphone never opens | `allow="microphone"`, your page on HTTPS, and the permission granted — all three |
| It works, then stops after an hour | A renewal failed and the loader did not retry. See [what it does not do](#what-it-does-not-do--read-this-before-you-ship) |
| Refused with *this embed is over its rate limit* | The whole key's budget, spent by everybody. Ask for a bigger number, or find the loop |


---

## Answering about your own data

Everything above puts the panel *beside* your application. This puts it
*inside* it: somebody asks the panel a question whose answer is in your
database, and it goes and gets it — through your page, with their login.

**No server of ours ever contacts yours, and we hold no credential of yours.**
The panel is on another origin and cannot reach your API. Your page can, so
your page is what makes the request. It follows that the panel can only ever
see what the person looking at it could already have seen.

### What you provide

**1 — an OpenAPI document**, on the same origin, at a stable path. Every
operation you want reachable needs a unique `operationId` — that is the only
name we grant against, because paths get rewritten and a permission that
followed a rename to a different operation is the worst way for one to fail.
Give each a `summary` and a `description` written for somebody who does not
know your application: a model chooses between operations on those sentences
and nothing else. Put an `enum` on every parameter with a fixed set of values,
or it will guess `firewall` where your data says `fw-edge` and collect a 400.
Anything that can return many rows needs a `limit` with a default and a
maximum.

**YAML cannot be read** — there is no parser for it in the standard library
and none is worth adding. Point us at the JSON your framework serves from the
same document.

**2 — a grant file** at `/.well-known/resonance.json`, same origin, no login
required to read it. This is where **you** say what may be touched at all:

```json
{
  "resonance": 1,
  "spec": "/openapi.json",
  "allow": [
    {"op": "searchLogs"},
    {"op": "getLogEntry"},
    {"op": "acknowledgeAlert", "writes": true}
  ]
}
```

Nothing in your spec is reachable unless it is named here, and the admin at
the other end can narrow this and can never widen it. `writes: true` goes on
anything that changes state **whatever its verb** — we do not infer it from
`GET` versus `POST`, because both get used both ways. An operation marked that
way is never executed until the person confirms it, out loud or on screen,
with the real values read back to them.

**Serve no grant file and you get read operations only** — `GET` and `HEAD`,
never a write. An application that has never heard of any of this can still be
embedded and be useful, and cannot be written to by accident.

### What arrives, and what goes back

If you use the loader, **nothing** — `embed.js` performs the call itself,
same-origin, with `credentials: 'include'`, and refuses anything the session
did not declare. Your endpoints behave normally: your own authorization still
applies per request, return JSON with proper status codes, and bound your
results — a page plus a total, never the whole table.

Doing it without the loader, or authenticating with a bearer token in memory,
the exchange on the existing channel is:

```js
// frame → your page
{rsn: 1, kind: 'call', id: 'h1', op: 'searchLogs', method: 'get',
 path: '/api/logs/search', query: {source: 'fw-edge', limit: '50'},
 body: null, writes: false}

// your page → frame, within twenty seconds
{rsn: 1, kind: 'result', id: 'h1', status: 200, body: {…}}
```

The method, the path and the query are already resolved from **your** spec, so
there is nothing to assemble and nothing to guess. Answer within twenty
seconds or the panel treats it as unanswered and says so.

With a bearer token, keep the loader and give it the fetch:

```js
Resonance.onCall = function (call) {
  return fetch(call.url, {
      method: call.method,
      headers: {Authorization: 'Bearer ' + myToken,
                'Content-Type': 'application/json'},
      body: call.body ? JSON.stringify(call.body) : undefined})
    .then(function (r) {
      return r.json().then(function (b) { return {status: r.status, body: b}; });
    });
};
```

It is called only for operations the session declared — that check happens
before your handler is reached.

### What you should expect to see fail

- **A 400 naming a parameter.** Almost always a missing `enum`: the model
  guessed a value your API does not use.

  **Make your 400s name the valid values.** The thing reading that message is
  the model, and the model is what retries. Given a bare refusal it re-guesses
  and sends again — a whole extra round trip through your page, often landing
  on the same wrong operation. Given *"bucket_minutes must be one of 1, 5, 15,
  60"* it corrects itself on the next call. Your error strings are part of the
  interface now.

- **The right question answered by the wrong operation.** A model chooses
  between your operations on their `description` and nothing else. If two of
  them could plausibly answer "which host is noisiest" — one that ranks hosts
  and one that plots volume over time — say so in the sentence, in those words.
  Observed in the field: the timeline operation chosen twice for a question the
  summary operation answers directly.
- **The panel saying it could not read a result in full.** A result over 20KB
  is truncated and the model is told it was. Bound your list operations.
- **Nothing happening at all.** The operation is in your spec and your grant
  file, and nobody has ticked it at the other end. Everything starts off.
