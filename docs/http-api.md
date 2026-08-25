# HTTP API

Every endpoint this server exposes, and which listener it exists on.

On every listener:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/stt` | audio in, `{"text": …}` out. `?model=`, `?hint=` |
| `GET` | `/stt/status` | which transcription models are resident, and which this server will accept |
| `POST` | `/tts` | text in, WAV out. `?voice=`, `?rate=` |
| `GET` | `/tts/voices` | installed neural voices |
| `GET` | `/settings` | the shared interface configuration |
| `GET` | `/routes` | the routes: presentation to anyone, the routing half only to a caller holding a display token, and `allowed` per route for that caller |
| `POST` | `/ask` | a question — `{"route": …}` picks one, absent means the default. `{"conversation_id": …}` continues one the endpoint is keeping, and the reply carries that id back. `403 {"refused": "display"}` where this display may not use that route |
| `POST` | `/display/hello` | a display announcing itself: declared name in, its identity out, and a token in an `HttpOnly` cookie if it had none. **A name, or nothing** — arriving without one returns `{}` and mints no device, because hanging a screen is a deliberate act and a browser that merely opened the address is somebody looking at a page. Same-origin only |
| `POST` | `/display/request` | a device asking for access, answering the form the admin built — or `{"renew": true}`, which asks again on the answers already held. Same-origin only |
| `POST` | `/display/poll` | a display saying it is still here and asking whether anything has moved: the stamp of ITS OWN configuration, whether an admin has asked it to reload, this server's clock, and the numbers it keeps itself up with. Same-origin only |
| `POST` | `/display/enrol` | an enrolment code redeemed in place, from the box the display page offers. Spends the code and sets the cookie, without sending anybody back to the address bar. Same-origin only, same back-off as the URL form |
| `GET` | `/e/<code>` | the same code, typed as a URL instead — the right shape for a television with a remote and no browser open yet. Spends the code, sets the cookie, and redirects: to the first assistant that screen may use where a **device enrolment listener** is set, otherwise back to the display with `?enrol=` saying how it went. Display listeners, and the device enrolment listener where one is configured |

Display listeners only — the embed does not exist on the admin port:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/embed/session` | an embed key in, a one-use handover code out. Where the key requires it, `user.id` must come with the key or the call is refused. Never returns a session token: see [Embedding](embedding.md) |
| `GET` | `/embed?c=` | the display, framed, drawing only what the key grants. The code is read for the `frame-ancestors` line and **not** spent |
| `POST` | `/embed/claim` | the code, spent once, for the session token and the grant — including `tools`, the operations this session may ask the host's own application for. The token is a bearer credential and lives only in that page's memory |
| `GET` | `/embed/session` | what this session was granted — bearer token |
| `GET` | `/embed.js` | the loader a host page drops in: fetches a code from *their* endpoint, frames this, draws the bubble, renews the session |

`POST /ask` from an embed session answers with `tool_call` instead of `reply`
where the answer is in the host's own application: the frame performs it
through the host page and posts the same question again with `tool_results`.
Four laps, then it stops. See [Reaching the host application's
data](host-data.md).

**These five are the only endpoints another application is meant to call**, and
the table above is an index rather than a contract. The request and response
bodies, every status code and what to do about it, the two TTLs, the three
different `429`s and the `postMessage` channel are written out in
[Integrating it](integrating.md), which is the document to hand a host
developer.

Admin listener only — everything below returns 404 on the public ports:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/auth/login` | username and password in, session cookie out |
| `POST` | `/auth/logout` | end the session |
| `GET` | `/auth/me` | who am I, and with what role |
| `POST` | `/auth/password` | change a password; your own needs the current one |
| `POST` | `/settings` | write the configuration — `admin` role. A bare object replaces it; `{settings, merge}` writes only the keys it carries |
| `GET` | `/app` | ports and session length, plus what is actually running |
| `POST` | `/app` | change them — `admin` role, restart to apply |
| `GET` | `/users` | list accounts — `admin` role |
| `POST` | `/users` | create an account — `admin` role |
| `POST` | `/users/role` | change a role — `admin` role |
| `POST` | `/users/delete` | remove an account — `admin` role |
| `GET` | `/routes/all` | every route in full, less the keys — `admin` role |
| `POST` | `/routes/new` | create one — `admin` role |
| `POST` | `/routes/save` | change one — `admin` role |
| `POST` | `/routes/default` | choose which answers the unaddressed — `admin` role |
| `POST` | `/routes/enable` | enable or disable one — `admin` role |
| `POST` | `/routes/delete` | remove one, and its key — `admin` role |
| `POST` | `/routes/test` | one real round trip against that route — `admin` role |
| `GET` | `/displays` | every display, plus the address an enrolment code is typed into — `admin` role |
| `POST` | `/displays/new` | create a row before its device exists, and issue its code — `admin` role |
| `POST` | `/displays/reissue` | kill the row's live token now and issue a new code; name and permissions kept — `admin` role |
| `POST` | `/displays/decide` | approve — with the endpoints it may use, in the same call — or refuse, with a message for them, a note for you, and whether it may ask again — `admin` role |
| `POST` | `/displays/settings` | whether guests may ask, how long a grant lasts, the two limits, and the request form — `admin` role |
| `GET` | `/groups` | every group, plus the two populations one can be drawn from — `admin` role |
| `POST` | `/groups/save` | create one, rename it, or set its membership — `admin` role |
| `POST` | `/groups/delete` | remove one, and take it off every endpoint that named it — `admin` role |
| `POST` | `/displays/approve` | approve one, or withdraw it; may name it in the same call — `admin` role |
| `POST` | `/displays/rename` | change what it is listed as; blank hands the row back to the name the device declares — `admin` role |
| `POST` | `/displays/delete` | revoke: its token stops matching, and it is removed from every route's allow-list — `admin` role |
| `GET` | `/embeds` | list embed keys, each with the integration code rebuilt for it — `admin` role |
| `POST` | `/embeds` | create one; the key is returned once — `admin` role |
| `POST` | `/embeds/update` | rewrite one in place: same id, same secret, same grants. Live sessions dropped if the envelope moved — `admin` role |
| `POST` | `/embeds/reissue` | a new secret on the same key: same id, same settings, same grants, live sessions dropped. Returned once — `admin` role |
| `POST` | `/app/restart` | hand over to `serve.sh restart`. **Refused with `409` and the reason where the saved configuration would not bind**, rather than restarting into a server that cannot come back |
| `POST` | `/embeds/spec` | read a site's OpenAPI document and the grant file beside it, and cache the operations. `url` or a pasted `doc`; both must resolve to an origin the site is registered under |
| `POST` | `/embeds/ops` | which of those operations the panel may call. Bounded by the application's own grant file; anything outside it is dropped rather than refused. Withdrawing one drops the site's live sessions |
| `POST` | `/embeds/enable` | enable or disable one — `admin` role |
| `POST` | `/embeds/delete` | revoke one — `admin` role |

`GET /embeds` carries `snippets` on every row. The key is not in them — it is
read from `RESONANCE_KEY` in the host's own environment — which is why they can
be rebuilt long after the one response that held the secret has gone. The
secret itself is a hash from the moment it is written and never comes back;
`/embeds/reissue` is the only way to obtain a working key for an existing site,
and it keeps the id so every grant made to that site survives.

`/embeds/update` takes the same body as `/embeds` plus the `id`, and runs it
through the same validator — an edit cannot reach a record a create could not
have produced. It replaces `name`, `preset`, `parts`, `cap`, `origins`,
`ttl_minutes` and `needs_user`, and leaves the secret, the audit fields and
`enabled` alone (`enabled` has `/embeds/enable`, so a form carrying it would
put a site back on the air as a side effect of a rename). It answers `changed`,
the list of envelope fields that moved, and `dropped`, how many live sessions
were cut because they moved: a session token carries the parts, the capability
and the origins it was minted with, so a narrowed key whose sessions were left
running would be narrower on paper for as long as a session lasts. A rename
drops nothing. `snippets` comes back too, because `needs_user` decides whether
the host's own endpoint has to send a person.

**Everything else 404s, including files that are not secret.** The server
hands out four files — `index.html`, `admin.html`, `icon.svg`, `lockup.svg` —
and refuses every other path. An allow-list rather than a list of things to
hide, because the directory `serve.py` runs from is a deployment: the base
class serves whatever is sitting in it, and what was sitting in it was the TLS
private key, the account hashes and one API key per route. Deny-by-default
also answers traversal and percent-encoding without either needing a rule.

The last admin account cannot be deleted or demoted; an interface nobody can
administer is a brick. The last route cannot be deleted or switched off for
the same reason: a server with nowhere to send a question is a composer wired
to nothing, recoverable only by editing JSON on the box.

`/routes` is the one path with a public half and a private half, and every
privileged operation sits under `/routes/…` precisely so the admin-only list
can stay a list of paths rather than a list of paths and methods.

`/display/hello` and `/displays` are one letter and a whole boundary apart, for
the same reason. A display has to be able to reach the first from the listener
it is served on; everything an *admin* does to a display is the second, and is
absent from that listener entirely.

## Driving the visualiser directly

The geometry only ever reads two things, so any source can drive it:

```js
Drive.hit(weight);   // an impulse — a token, a syllable, an event
Drive.level;         // 0..1, current energy
```

Wire an analyser to those and the visualiser follows, whatever is making the
sound. This is the seam that will become the public API when this is packaged.

