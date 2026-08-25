# Reaching the host application's data

**Built** — designed and built 2026-08-23. This document is both the design
and the reference: what follows is what the code does, and where it says a
thing is refused, it is refused.

The embed puts an assistant on somebody else's page. What it cannot do today
is answer *about that application* — a person sitting in front of a log
viewer, a ticket queue or a stock list can ask the panel anything except the
thing they are looking at. This closes that: the panel reaches the host
application's own records, through the host application's own API, with the
credentials of the person already signed in to it.

The two halves either side of this one are [Embedding](embedding.md), for the
admin who makes the key, and [Integrating it](integrating.md), for the
developer on the receiving end.

---

## What it is for

Somebody is working in an application that holds a database of log lines from
a dozen sources. They ask the panel *"anything from the firewall overnight?"*
The answer is not on the page in front of them, and the panel cannot invent
it. Something has to search that application's database and come back.

The whole of the design is about **who does that search, with whose
permission, and who decided they were allowed**.

---

## What happens per question

1. Somebody asks the panel something.
2. The model sees, alongside the question, the list of operations this site
   has been granted — names, descriptions, parameters, taken from the
   application's own API spec.
3. It chooses one and emits a call.
4. The call goes **down the existing host channel** to the page the panel is
   embedded in.
5. The host page performs it — a same-origin request, carrying that person's
   own login, exactly as any other request that page makes.
6. The result comes back up the channel and into the answer.
7. If the operation changes something, step 5 does not happen until the person
   has said yes.

Nothing in that sequence involves this server holding a credential to their
application, or reaching their network.

---

## Why the browser and not this server

The obvious design has this server call theirs. It is the wrong one, for three
reasons that all arrive on the first integration.

**A credential into every application.** This server would need a service
account on theirs — one account, used for everybody, necessarily holding more
than any individual visitor should see. Scoping it back down to the person who
actually asked is a delegation problem, and solving it properly is more work
than the rest of this feature put together.

**Network reach.** Half of these applications are on a private network, a
laptop, or a machine that has never accepted an inbound connection in its
life. The browser is already inside; this server is not, and *make the server
reachable* is not a reasonable thing to ask of somebody who wanted a chat
panel.

**A schema per application.** Pulling from the far side means learning where
each application keeps things. That is app-specific code here, forever, one
lump per customer.

The browser answers all three at once. The panel is running inside a page that
is **already authenticated as that person**, same-origin with the application's
own API. So the request is made where the session already is. This server
holds no secret, reaches no network, and contains no code specific to any
application.

**The limit that follows, stated plainly:** the panel can only reach data
while somebody has the application open. There is no background analysis and
no scheduled pass. That is not a gap to be filled later — see
[Not taken](#not-taken).

---

## The spec is the integration

An application publishes an **OpenAPI description of its own API**, which most
already generate, and gives the address of it. That is the whole of the
integration work on their side.

**A site record gains a spec URL.** Beside the origins, the capability and the
chrome, on the same row under **EndPoints ▸ SITES** where everything else about
that site is edited — the third block on the row, *their application*. **READ
SPEC** fetches it, reads the operations out of it, and lists them with a tick
each; anything that writes is marked. **SAVE OPERATIONS** is what grants them.

**A document may be pasted instead of fetched.** An application on a private
network is the ordinary case for this and is exactly the case this server
cannot reach, so `POST /embeds/spec` takes a `doc` as readily as a `url`. What
is pasted goes through the same parser and the same ceiling. The grant file is
still fetched from the origin, because its whole value is that it came from
there.

**The spec must sit on an origin the site is registered under.** That is a
boundary rather than a convention: a URL an admin can type is a URL this
server will fetch, and without the check the field reaches every address on
this machine's network.

**Operations are named by `operationId`.** It is the one identifier in an
OpenAPI document that is meant to be stable and unique; paths and methods get
rewritten by every refactor, and a grant that named a path would silently
follow the rename to a different operation.

**An application with no API is not reachable, and that is theirs.** There is
no fallback that scrapes the rendered page. A panel that answered from the DOM
would answer only about what is already visible, which is the exact case this
exists to solve, and it would do it while looking like it had done more.

---

## Three authorities, and the narrowest wins

Nothing here has one owner. What the panel may actually do is the intersection
of three separate decisions, each made by somebody with a real claim.

| | who decides | where it lives |
|---|---|---|
| **The ceiling** | the application's owner | a grant file they serve, from their own origin |
| **What is enabled** | this server's admin | ticks on the row under EndPoints ▸ SITES |
| **What that person could do anyway** | the application itself | their session, on every request |

**The data owner sets the outer bound and only they can raise it.** The admin
here can withdraw anything but cannot add to it — which is what makes the
panel safe to embed in an application that somebody else runs, rather than
only in your own.

**An application that serves no grant file gets reads only.** Writes never
become available by silence: the application has to state them. So an
application that has never heard of any of this can still be embedded and be
useful, and can never be written to by accident.

**Everything starts off.** A spec listing forty operations grants none of
them until an admin ticks them, and operations that appear in a later version
of the spec appear in the list off. Nothing turns itself on.

---

## The grant file

Served from **the same origin the site is registered under**, at
`/.well-known/resonance.json`. The origin check is the whole of its
authenticity: without it, anybody could serve a file claiming to speak for
that application.

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

**`writes` is declared, not inferred.** The verb in the spec is a hint and not
a promise — plenty of applications change things behind a `GET`, and plenty of
`POST` endpoints are searches with a body too long for a query string. An
operation the application has not marked as writing is treated as a read and
refused if it is anything else; an operation marked as writing goes through the
confirmation below whatever its verb is.

An operation named in the file but absent from the spec is reported on the
site's row rather than ignored, because the usual cause is a rename that has
already silently withdrawn a capability somebody depends on.

---

## Writes stop and ask

Reads go straight through. **Anything that changes something stops and asks
the person.**

The panel states what it is about to do, with the real values in it — *"close
ticket 4471"*, never *"make this change"* — and nothing is sent until they
agree. It is a voice interface, so agreement is spoken as readily as clicked,
and the readback exists precisely because a spoken interface has no address
bar to check.

**Per action, never per session.** There is no *allow writes for this
conversation* toggle. That is the same hole with an extra click in front of
it, and it would be worth exactly one mistaken *yes*.

---

## The channel

The host channel already exists — `rsn: 1`, the frame and the host page,
posted to the host's origin and never to `*`. This adds one exchange to it.

```js
// frame → host
{rsn: 1, kind: 'call', id: 7, op: 'searchLogs',
 params: {source: 'firewall', since: '2026-08-22T22:00:00Z', limit: 50}}

// host → frame
{rsn: 1, kind: 'result', id: 7, status: 200, body: {…}}
```

**`embed.js` performs the call itself**, building the request from the spec it
was given and fetching it same-origin with `credentials: 'include'`. So an
application whose session is a cookie writes **no code at all** for this — it
publishes a spec and a grant file and is done.

**An application holding a bearer token in memory writes a handler**, because
the loader has nowhere to put an `Authorization` header. This is the same
fault line as the code endpoint in [Integrating it](integrating.md), it splits
the same population the same way, and whatever shape settles that one should
settle this one too rather than inventing a second convention beside it.

The frame validates every result against the operation's declared response
shape before it reaches the model. The host page is untrusted by definition;
it is simply the only thing standing in the right place.

---

## What the model is told, and what it gets back

**The application narrows, not the model.** An operation returns a bounded
page and a count, never a table. A log search that matched forty thousand rows
returns fifty and says forty thousand — the model then asks a better question,
which is the thing it is good at, instead of being handed a corpus it cannot
read.

**The grant carries vocabulary or the calls fail.** Which sources exist, what
the levels are called, how far back the data goes. This is what a spec's
descriptions and enums are for, and an application whose spec is bare
parameter names will produce a panel that guesses field values and gets 400s
for it. Worth saying to a host developer before they wire it up rather than
after.

---

## What this needs that does not exist yet

**Resonance does not call tools today.** Home Assistant does its own tool
calling on its own side; nothing in this server has ever emitted a call and
fed a result back into a second pass. That machinery is new work, and it is
the bulk of the build.

It also lands on the choice of assistant, which is worth being blunt about:
`demo` cannot do this at all, hosted models do it reliably, and small local
models are exactly where tool calling is least dependable. An assistant a site
uses for this is a different judgement from one chosen for conversation — the
same split [Architecture](architecture.md) already names between conversational
quality and reliable tool calling.

---

## Not taken

**This server calling theirs.** Covered above: a credential per application, a
network reach it does not have, and app-specific code here forever.

**Reading the host page's DOM.** Zero setup and answers only about what is
already on screen, while appearing to do more.

**A background pass over an application's data.** The panel acts on something
a person asked for. Nothing runs on its own, and nothing is scheduled — the
value here is a person asking a question they could not otherwise ask, not an
agent with an opinion about their database.

**Inferring writes from the HTTP verb.** Wrong often enough to matter, in both
directions.

---

## Following a call in the log

Every call is recorded on both legs, and the pair is what tells you whose
problem a failure is. **The request, and never the response.** A response body
is that application's data and has no business in this server's log; the status
is the one fact that decides where to look next.

```
embed efe2c22ff5da2 (pktLog) -> GET /api/logs/search?limit=1 (lap 1)
embed efe2c22ff5da2 (pktLog) <- searchSyslog 200 648B
```

The `->` line is the request as the host application's own access log will
have recorded it, so the two can be laid side by side. The `<-` line is what
came back:

| what it says | what it means |
|---|---|
| a status and a size | their API answered. A `4xx` or `5xx` is theirs to explain |
| `no status — the application did not answer` | twenty seconds passed with no reply from the page |
| `no status — this page does not perform that operation` | `embed.js` refused it: the operation was not in the session's grant, or the path did not match its template |
| nothing at all, and an `SSLEOFError` beside it | **something in front of this server closed the connection.** See below |

**A reverse proxy in front of this server needs its read timeout raised.**
Every lap is its own HTTP request, and each one waits on a whole model pass —
tens of seconds on a small local model. nginx's default `proxy_read_timeout`
is 60 seconds, which is not a setting anybody remembers making. When it fires,
this server finishes the lap and then fails writing the response, the browser
sees a dead connection, and the panel says it could not reach the assistant.
The failure therefore reads as the *assistant* being broken, which is the one
place it is not.

**A question that needs several laps is where this bites**, and a model that
chooses the wrong operation is what causes several laps: a rejected call is
answered to the model and it tries again, so a poor choice costs a whole extra
round trip. The two failures compound, and the log above is what separates
them.

## Still open

Three, and none of them blocks using it.

- **How a large spec is presented.** Four hundred operations is a list no
  admin will read and a prompt no model should see. Whether that is search in
  the panel, tags in the grant file, or a hard cap on how many one site may
  enable.
- **When the spec is re-read.** It is read when an admin presses READ SPEC and
  at no other time. What happens to an operation that has since disappeared is
  settled — the tick is dropped and the row says which ones went — but nothing
  yet notices without being asked.
- **Where a refused call surfaces.** A 403 from the host application reaches
  the model as the result of its call and is answered in words. That is right
  for the person and leaves an admin nothing to look at.
- **A refusal and a wrong request are told apart.** 401 and 403 are that
  person's account saying no, and the model is told to say so and stop.
  Anything else — a rejected parameter, a window too wide, a bucket too fine —
  is the call being wrong, and these applications answer it by naming the value
  that would have worked, so the model is told to correct the arguments and
  call again. One sentence used to cover both and taught it to give up on
  either. It is also told never to ask whether to make a call: a read needs no
  permission and a write is confirmed by the browser, so an offer to proceed
  only costs the person a turn.

- **Only the OpenAI dialect and Anthropic call tools.** Home Assistant does
  its own on its own side and is not affected; `demo` cannot, and a small
  local model is exactly where tool calling is least dependable. Choosing an
  assistant for a site that uses this is a different judgement from choosing
  one to converse with.

---

## Appendix — what the host application must provide

Hand this to the developer on the other end. It is the whole of their side,
and it is written to be copied as it stands.

    RESONANCE — LETTING AN EMBEDDED ASSISTANT ANSWER ABOUT YOUR DATA
    ===============================================================

    A Resonance assistant panel is being embedded in your application. This
    document is everything your side needs so it can answer questions about
    YOUR records, not just sit beside them.

    You do not write an integration. You do not issue anyone a credential.
    No Resonance server ever contacts yours.

    Every call is made BY YOUR OWN PAGE — same-origin, with the session
    cookie of the person already signed in to your application. So the
    assistant can only ever reach data that person could already reach, and
    their own permissions still apply on every request.

    There are three things to provide. Two are files. The third is
    "nothing", unless you authenticate with a bearer token.


    1 — AN OPENAPI DOCUMENT
    -----------------------

    OpenAPI 3.0 or 3.1, **JSON**, at a stable path on the same origin as
    your application (e.g. /openapi.json). Most frameworks already generate
    this.

      *** YAML CANNOT BE READ. *** There is no YAML parser on the Resonance
      side and none is being added. If your framework emits YAML, point us
      at the JSON it serves from the same document — usually the same path
      ending .json.

    Requirements:

      * Every operation you want reachable MUST have a unique
        `operationId`. That is the ONLY name permissions are granted
        against. Paths and methods are not stable enough — a grant naming a
        path would follow your next refactor onto a different operation and
        keep working.

      * Every such operation MUST have a `summary` and a `description`,
        written for a reader who has never seen your application. A model
        chooses between operations on those sentences and nothing else.
        "Search logs" is not enough.

      * Every parameter MUST be described, and MUST carry an `enum`
        wherever the valid values are a fixed set. This is how the
        assistant learns your vocabulary. Without it, it will confidently
        send "firewall" where your data says "fw-edge" and collect a 400
        every time. This is the single most common cause of a bad
        integration.

      * Every operation MUST declare a response schema. Results are
        validated against it before they reach the model.

      * Anything that can return many rows MUST take a `limit` with a
        sensible default and a hard maximum, and SHOULD take a cursor or
        offset.

    Example of the level of detail expected:

        /api/logs/search:
          get:
            operationId: searchLogs
            summary: Search log entries
            description: >
              Search ingested log entries across all sources, newest first.
              Returns at most `limit` entries plus the total number matched.
            parameters:
              - name: source
                in: query
                description: Restrict to one ingest source.
                schema:
                  type: string
                  enum: [fw-edge, dhcp, radius, syslog-core]
              - name: since
                in: query
                description: ISO 8601 timestamp; entries at or after this time.
                schema: {type: string, format: date-time}
              - name: limit
                in: query
                description: Max entries to return. Default 50, maximum 200.
                schema: {type: integer, default: 50, maximum: 200}
            responses:
              '200':
                description: Matching entries.
                content:
                  application/json:
                    schema:
                      type: object
                      properties:
                        total:   {type: integer}
                        entries:
                          type: array
                          items: {$ref: '#/components/schemas/LogEntry'}

    Local $ref into the same document is resolved. External $ref (to
    another URL) is not followed.


    2 — A GRANT FILE
    ----------------

    Served at /.well-known/resonance.json on the SAME ORIGIN, as
    Content-Type: application/json, readable WITHOUT a login (it contains
    no data, only names).

    This is where YOU declare what may be touched. Nothing in your spec is
    reachable unless it is named here — publishing the spec grants nothing.

        {
          "resonance": 1,
          "spec": "/openapi.json",
          "allow": [
            {"op": "searchLogs"},
            {"op": "getLogEntry"},
            {"op": "listSources"},
            {"op": "acknowledgeAlert", "writes": true}
          ]
        }

      * `resonance: 1` is required. Without it the file is not read.
      * `spec` — path or absolute URL of the document from step 1.
      * `allow` — the operationIds the panel may call. Everything else in
        your spec is invisible to it, whatever the admin at the far end
        does.
      * `writes: true` — set on ANY operation that changes state, WHATEVER
        its HTTP verb. This is never inferred from GET/POST, because both
        get used both ways in real applications. An operation marked this
        way is never executed until the person confirms it — out loud or on
        screen — with the real values read back to them.

      IF YOU SERVE NO GRANT FILE AT ALL: read verbs only (GET/HEAD), and
      writes can never be enabled. Your application can be embedded and be
      useful without ever having heard of this, and cannot be written to by
      accident.

    The grant file and the spec must both sit on an origin the site is
    registered under at the Resonance end. This is enforced.


    3 — YOUR ENDPOINTS BEHAVING NORMALLY
    ------------------------------------

    No new authentication, no CORS work, no key to hold. If your front end
    uses a cookie session, the loader (embed.js, already on your page)
    performs the call itself with credentials: 'include' — you write
    NOTHING.

      * Your own authorization still applies per request. If this user may
        not see a record, return your normal 403; the assistant will say so
        plainly and will not retry.
      * Return JSON, not HTML. Errors as proper status codes with a JSON
        body like {"error": "unknown source"} — that message is shown to
        the person, so make it one they can act on.
      * BOUND YOUR RESULTS. A page plus a total, never the whole table. A
        search matching 40,000 rows should return 50 and say 40,000.
      * *** Results over 4,000 characters are truncated *** and the model
        is told they were. It will then ask a narrower question — but only
        if your operation lets it (see `limit`, above). It was 20 KB, which
        was chosen against "a log search returns 40,000 rows" without
        asking what a model could hold: 20 KB is around 5,000 tokens, and a
        small local model's ENTIRE window — tools, prompt, history and
        result together — is 4,096.
      * *** You have 20 seconds to answer. *** Past that the panel treats
        the call as unanswered and tells the person so.
      * Keep field names stable. They end up in the sentences people read.


    IF YOU AUTHENTICATE WITH A BEARER TOKEN IN MEMORY
    -------------------------------------------------

    The loader can carry a cookie and has nowhere to put an Authorization
    header. Give it the fetch instead — one function, on the page:

        Resonance.onCall = function (call) {
          // call = {op, method, url, path, query, body, writes}
          return fetch(call.url, {
              method: call.method,
              headers: {
                Authorization: 'Bearer ' + myToken,
                'Content-Type': 'application/json'
              },
              body: call.body ? JSON.stringify(call.body) : undefined
            })
            .then(function (r) {
              return r.json().then(function (b) {
                return {status: r.status, body: b};
              });
            });
        };

    `call.url` already has the query string on it. Your handler is only
    ever invoked for operations the session declared — that check happens
    before it is reached.


    THE RAW CHANNEL (only if you are not using the loader)
    ------------------------------------------------------

        // panel frame -> your page
        {rsn: 1, kind: 'call', id: 'h1', op: 'searchLogs', method: 'get',
         path: '/api/logs/search', query: {source: 'fw-edge', limit: '50'},
         body: null, writes: false}

        // your page -> panel frame, within 20 seconds
        {rsn: 1, kind: 'result', id: 'h1', status: 200, body: {...}}

    Post back to the panel's origin, never '*'. The method, path and query
    are already resolved from YOUR spec — there is nothing to assemble.


    WHAT TO EXPECT WHEN IT DOESN'T WORK
    -----------------------------------

      * "400, naming a parameter"  -> a missing `enum`. The model guessed a
                                      value your API does not use.
      * "it never calls anything"  -> the operation is in your spec and
                                      your grant file, and nobody has
                                      ticked it at the Resonance end.
                                      Everything starts off, by design.
      * "results are truncated"    -> over 4,000 characters. Add/lower
                                      `limit`.
      * "the assistant says the
         application didn't answer" -> over 20 seconds.
      * "writes never happen"      -> either no grant file, or
                                      `writes: true` is missing, or the
                                      person said no. A write always stops
                                      and asks.


    CHECKLIST
    ---------

      [ ] OpenAPI **JSON** at a stable, same-origin path
      [ ] unique operationId on every operation to be exposed
      [ ] summary + description written for a stranger
      [ ] enum on every fixed-value parameter
      [ ] limit with a default and a maximum on every list operation
      [ ] response schemas declared
      [ ] /.well-known/resonance.json, public, application/json
      [ ] resonance: 1, and allow[] naming ONLY what you intend to expose
      [ ] writes: true on everything that changes state, whatever the verb
      [ ] bounded results: a page plus a total
      [ ] answer within 20s, JSON bodies, real status codes
      [ ] cookie session — or add Resonance.onCall for a bearer token
