# Todo

Open questions and work not yet started. Each entry says what is wrong, what
has to be decided before it can be built, and what was actually found in the
code — so the next person to pick it up is not starting the investigation
again.

---

## 1 · What belongs to a display and what belongs to an AI connection

**There are settings in both places that answer the same question**, and which
one wins is decided by fallback chains rather than by anybody having drawn the
line. Before any of it is moved, the line has to be drawn: what is a property
of the **connection** (a provider, a model, a key, a port, who may use it) and
what is a property of the **place** (a voice, a greeting, a wake word, a look).

What is actually there today:

- **A wake word can live in three places.** An endpoint carries its own
  `wakeword` and `aliases`; the **speech profile** it names carries the same
  two; and a **person** carries one on their identity row. `wake_words_in_use()`
  reads the profile first and falls back to the endpoint's own pair, which
  makes the endpoint's copy read as legacy — but nothing says so, and both are
  editable.
- **`voice` is on the endpoint** and blank means "whatever the shared settings
  chose", while the speech profile is the thing that otherwise describes how a
  place sounds.
- **`greeting` is on the endpoint**, blank meaning the shared phrases — same
  shape as `voice`, same question.
- **`kiosk_profile` is on the endpoint *and* on the display row.** This one is
  deliberate — the endpoint's is what a screen on its port inherits when the
  row is left on INHERIT — but it is the only two-place setting that is
  intended, so it should be obvious which of the pairs above are like it and
  which are duplicates.
- **An endpoint mixes both kinds already**: `network`, `restricted`,
  `needs_signin`, `displays` are access and address; `greeting`, `voice`,
  `speech`, `kiosk_profile` are appearance.

**To decide first:** whether an endpoint keeps any appearance at all, or names
a speech profile and nothing else. If it keeps none, the endpoint's `wakeword`,
`aliases`, `voice` and `greeting` become migrations into a profile rather than
fields to delete — a deployment that set them on the endpoint must not go
silent on upgrade.

---

## 2 · Choosing what gets logged

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

## 3 · Building up embeds

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

## 4 · "transcribing…" still shows on the Home Assistant wall display

**Reported again**, on a display in full screen. Two rounds of fixes have gone
at this already — the first asked the wake gate and was silently useless
(`Wake.armed()` is false in auto and push-to-talk, so it hushed nothing), the
second moved the question to whether the screen is in a conversation and also
hushed the error-flagged notes, which are the frequent ones. It is still
appearing, so **reproduce it on that screen and find out what `hush()` actually
returns before changing `hush()` a third time.** Both previous attempts were
reasoned about rather than watched.

What it tests today — `index.html`, `hush()`:

```
Drive.phase !== 'idle'   -> do not hush (it is in a conversation)
Wake.awake               -> do not hush (somebody woke it)
otherwise                -> hush unless the screen was touched in the last few seconds
```

Both note surfaces go through it: `micNote()` writes `#micnote`, `note()`
writes `#ttsnote`, and each takes the same gate. `relay()` still sends
everything to the panel either way, so the panel is not evidence that hushing
failed.

**`hush()` never asks what kind of surface this is.** `Kiosk.on` and
`Kiosk.fullscreen` are not in it. That is the gap the report points at: a
browser tab somebody is using should narrate itself, and a screen on a wall
should not, and the current test cannot tell them apart — it only asks whether
anybody is mid-conversation with it.

Three candidates, in the order worth checking:

1. **`Wake.awake` is stuck true** on that screen. It is set on a wake hit and
   cleared in four places; if the HA endpoint's arrangement leaves it set, every
   note paints and the gate is working exactly as written.
2. **Something is updating `lastTouch` that is not a person** — a pushed
   command, a poll, a synthetic event — which buys `TOUCH_GRACE` seconds of
   narration each time.
3. **`Drive.phase` never returns to `idle`** on that endpoint, which would
   disable the gate outright.

If it turns out to be none of those, the answer is probably that a wall screen
should hush on being a wall screen rather than on nobody talking to it.

---

## 5 · A real certificate on the server

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

## 6 · Signing out — by voice, and on screen

**The server can already do it and nothing can reach it.** `/user/logout`
exists, works, and is called by nobody: it closes the account's sessions and
clears the cookie, and there is no button, no phrase and no gesture anywhere
that sends a request to it. A person signs in and the only ways back out are
waiting for the session to expire or an admin reissuing their link, which is
account recovery being used as a sign-out.

Two surfaces are wanted and they are not the same feature:

- **On screen** — a control wherever the signed-in person is visible. It has to
  say who is being signed out, because the case that matters is a shared
  machine and the person pressing it may not be the person signed in.
- **By voice** — a phrase, alongside the sleep word. `heardSleep()` already
  matches a configurable word (`sleepword`, default *goodbye*, with aliases) and
  calls `sleepNow()`; a sign-out phrase would hang off the same matcher and the
  same profile, so it is one more word rather than a new mechanism.

**To decide first, and it is the whole of the design:**

- **`close_user_sessions()` ends EVERY session that person has**, on every
  machine. That is right for a leaked link and wrong for "sign me out of this
  wall screen" — a person who says it in the hallway would be signed out of the
  laptop on their desk. So either sign-out learns to end one session, or the
  voice and screen versions do something narrower than the recovery path does.
- **Voice sign-out on a shared screen is a security control operated by anyone
  in earshot.** That may be exactly right — the risk of a stranger signing
  somebody OUT is small, and the alternative is an account left open on a wall.
  But it should be a decision, not a side effect of reusing the sleep matcher.
- **What the screen becomes afterwards.** Back to the gate, or back to whatever
  the display was before anybody signed in — which are different answers on a
  kiosk and on somebody's own browser.
- **Whether saying goodbye should sign out at all.** The sleep word and a
  sign-out word are close enough in meaning that a person will use one for the
  other, and today the sleep word only puts the figure to rest.

---

## 7 · Ending a session when the browser closes

**Nothing ends when a browser closes today.** The cookie is written with
`Max-Age = hours × 3600`, so it survives being closed and reopened, and the
server's own record — `_user_sessions[token] = {pid, expires}` — knows nothing
about browsers at all. Closing the window leaves a live session that anybody
returning to that machine walks straight into.

Pairs with **§6**: this is the same question asked from the other end, and both
run into `close_user_sessions()` ending every session that person has anywhere.

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
