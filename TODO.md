# Todo

Open questions and work not yet started. Each entry says what is wrong, what
has to be decided before it can be built, and what was actually found in the
code — so the next person to pick it up is not starting the investigation
again.

---

## 1 · Choosing what gets logged

**Everything is recorded and there is no way to say otherwise.** The nine kinds
in `EVENT_KINDS` — `mic_denied`, `no_recorder`, `stt_slow`, `stt_error`,
`tts_fallback`, `wake_fuzzy`, `no_intent`, `backend_error`, `backend_slow` —
are all captured, all kept for `event_days`, and all forwarded to the syslog
sink when `syslog_on`. `EVENT_LEVELS` (`info`, `warn`, `error`) exists and is
recorded per row, but nothing filters on it.

The noisy ones in a working house are `wake_fuzzy` and `stt_slow`, and they
are the two least likely to be acted on.

**To decide first:** three separate questions that a single control would
answer badly.

- **Per kind, or per level?** Nine ticks describes exactly what you want and
  goes stale every time a kind is added; three levels survives new kinds and
  cannot say "everything except near-miss wakes".
- **Does the choice apply to the ledger, to the syslog sink, or to each
  separately?** They are read by different people for different reasons — the
  ledger is the panel's own health list, the sink is somebody else's
  aggregator — so one setting for both is likely wrong.
- **Not recorded, or recorded and not shown?** Filtering at capture is what
  makes a busy deployment cheaper; filtering at display is what lets somebody
  turn a kind back on and still see last week. They are different features and
  only the second is reversible.

---

## 2 · Building up embeds

**Scope this before building any of it** — the list below is what is there and
what is plainly missing, not a decision about which of it is wanted.

What exists already, and works:

- **Seven parts** — `visual`, `transcript`, `input`, `mode`, `talk`, `audio`,
  `text` — composed rather than enumerated, so seven parts cover 128
  arrangements instead of a layout list that needs extending for the 129th.
- **Six presets** over them (`full`, `console`, `voice`, `chat`, `kiosk`,
  `signage`), as starting points an admin edits rather than separate kinds of
  token.
- **A capability envelope kept separate from the chrome** — `ask`, `mic`,
  `speak`, `rate_per_min` — fixed when the key is made and never widenable
  afterwards. `kiosk` and `signage` are the proof the two axes cannot be one
  field: identical chrome, opposite permissions.
- **An origins allow-list, session tokens with a TTL** (5–1440 minutes),
  per-embed rate limiting and a per-IP failure back-off.
- **A message API in both directions.** Out: `ready`, `status`, `learned`. In:
  `settings`, `routes`, `hello`, and `cmd` over six commands — `reorient`,
  `idle`, `thinking`, `speak`, `kiosk`, `drift`.
- **`docs/embedding.md`**, which describes all of the above.

Directions worth weighing, each of which is a different product:

- **The host API is thin where it matters.** A host can push a phrase to be
  spoken and drive the figure, but cannot ask a question and receive the
  answer, cannot read the transcript, and cannot be told a turn finished. A
  signage page can therefore narrate but an application cannot integrate.
- **No events reach the host.** `ready`, `status` and `learned` are the whole
  of it — nothing for a turn starting, a wake word firing, an error, or the
  microphone being refused, all of which the page already knows and records
  against `EVENT_KINDS`.
- **Appearance is the deployment's, not the embed's.** An embed renders what
  the shared settings and profiles say. Whether a host should be able to hand
  over a palette or a look — or name an appearance profile — is undecided, and
  it is the difference between an embed being *this* assistant on somebody
  else's page and being a component.
- **One key, one arrangement.** There is no way to issue a key that a host can
  reconfigure within its envelope, which is what an application with two
  surfaces on one page would need.
- **Nothing is versioned.** The message API has no version field, so the day a
  `cmd` changes shape there is no way for a host to know which it is talking
  to.

---

## 3 · A real certificate on the server

**Self-signed, and it is the reason for most of what looks broken.** What is on
the box today:

```
subject / issuer  CN = <the server's IP>      (its own issuer — self-signed)
valid             13 Aug 2026 → 13 Aug 2027
SAN               IP:<server>, IP:127.0.0.1, DNS:localhost
```

Every browser warns before every listener, on the panel and on each assistant,
and it has to be clicked past on each new machine and after each profile wipe.
Worse than the noise: a warning people are trained to click past is a warning
that stops meaning anything on the day it matters.

What it also blocks, concretely:

- **The FQDN under ADMIN ▸ Enrolment cannot be used honestly.** Set
  *Address in the link* to a name and every invitation opens on a certificate
  that does not carry it, so the first thing anybody sees when accepting is a
  security warning about the link they were sent. That is indistinguishable
  from phishing and it is the one page where it matters most.
- **Tooling cannot reach it.** The in-app browser refuses the cert outright, so
  the acceptance page and the panel cannot be driven or screenshotted for
  verification — which is why the enrolment gate shipped with its two body
  attributes unset and was found by hand instead.
- **A name is barely usable at all.** `make-cert.sh` writes the SAN from the
  one host it is given, so every name and address wanted has to be decided in
  advance and the script re-run to change any of them.

**To decide first:** where the certificate comes from, and it is a different
job for each answer.

- **An internal CA**, with its root installed on the machines that use this —
  covers every name and address at once and is the only answer that scales past
  a handful of browsers.
- **A public certificate** for a real domain, which needs that domain to resolve
  to the server and a renewal path that does not involve remembering.
- **Keep self-signing but do it properly** — every name and IP in the SAN,
  including whatever goes in *Address in the link*, and the root trusted on the
  machines that matter. Cheapest, and it does not fix the acceptance page for
  anybody outside those machines.

Whichever it is, two things go with it: **a renewal that is not a diary entry**
(this one expires 13 Aug 2027 and nothing will say so), and `make-cert.sh`
taking more than one host so the SAN can carry the panel's address, each
assistant's, and the enrolment name together.

---

## 4 · Ending a session when the browser closes

**Nothing ends when a browser closes today.** The cookie is written with
`Max-Age = hours × 3600`, so it survives being closed and reopened, and the
server's own record — `_user_sessions[token] = {pid, expires}` — knows nothing
about browsers at all. Closing the window leaves a live session that anybody
returning to that machine walks straight into.

**Signing out is built and this is not**, which is the same question asked from
the other end: one is somebody saying they are finished, the other is nobody
saying anything. The knot they shared is untied — `close_one_session()` ends
this browser's session and nothing else, so whatever answers this can end one
session too.

Three mechanisms, and only one of them actually ends anything:

1. **Make it a session cookie** — drop `Max-Age` and the browser forgets it on
   close. One line, and it is the weakest of the three: the server session is
   still open and still valid until it expires, so the token is *forgotten*
   rather than *ended*. Anybody holding a copy still gets in.
2. **A beacon on the way out** — `pagehide` / `visibilitychange` with
   `sendBeacon('/user/logout')`. Genuinely ends it, and unreliable in exactly
   the cases that matter: a killed tab, a crash, a dead network, a machine
   switched off at the wall. It also fires on ordinary navigation, so it has to
   tell leaving from moving.
3. **A heartbeat and an idle sweep** — the page already polls; a session not
   seen for N seconds is closed server-side. The only one that covers a crashed
   browser or a yanked power cable, which is the wall-screen case, and the only
   one where "ended" means ended.

**To decide first:** this contradicts a decision already made on purpose. The
session is persistent on that browser because *being asked again every half hour
would end with people avoiding the assistants that ask* — and that is still true
of somebody's own laptop. A shared machine wants the opposite. So it is probably
a setting, and the question is whose:

- **the person's** — they know whether it is their laptop, and `session_hours`
  is already theirs to set;
- **the display profile's** — the deployment knows which screens are shared,
  and the person may never have seen the machine before;
- **both**, with one winning, which needs the rule written down before either
  is built.

Worth knowing while deciding: `_user_sessions` is an in-memory map, so **a
server restart already ends every session**, and nothing anywhere says so.

---

## 5 · An approved request lands the person on a JSON error

**A regression, and a recent one.** Somebody asks for access on a display, an
admin approves, and their screen shows `{"error": "not found"}`. The admin sees
the link, which is working as intended; the person sees a JSON body.

The cause, exactly:

- Approving a request with an email on it mints an identity and puts the setup
  token on the display row, and `_display_state` hands the page
  `setup_url = "/p/<token>"` — **a path, not a URL**.
- The page polls, sees `state === 'setup'`, and does `location.href =
  this.setupUrl`, which resolves on **the port that display is loaded from** —
  an assistant's.
- `/p/` now answers on the enrolment listener and 404s on every other one. That
  was the point of giving enrolment a port of its own, and this redirect is the
  one caller that was still assuming the old rule.

**The wanted behaviour is not to fix the redirect.** Send the person back to
the sign-in page with a message: their request was received, and if it is
approved they will get an email with a link. That is the better answer anyway —
the display they asked from is a device, the account is theirs, and the link
should reach them on something they own rather than open on a screen in a
hallway that anybody may walk up to next.

Which means:

- the page stops navigating on `state === 'setup'` and says so instead;
- the display row probably stops carrying `setup` at all, since nothing on the
  screen will spend it — worth checking what else reads it before removing it;
- **the promise has to be true.** `mail_setup_link()` already runs on approve,
  but it needs an SMTP host and there is none configured on the test box today
  (`mail_host` is empty), so the message would promise an email nobody sends.
  Either the wording changes when `mail_ready()` is false — *an administrator
  will give you a link* — or the panel refuses to say the mail half at all.
