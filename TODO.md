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
