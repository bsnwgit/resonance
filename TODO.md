# Todo

Open questions and work not yet started. Each entry says what is wrong, what
has to be decided before it can be built, and what was actually found in the
code — so the next person to pick it up is not starting the investigation
again.

---

## 1 · Building up embeds

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

## 2 · A real certificate on the server

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

## 3 · Password rules an admin can set

**There is one rule and it is a constant.** `MIN_PASSWORD = 10`, in
`serve.py`, and length is the whole of it — nothing asks for a mix of cases, a
digit, a symbol, or anything a password is not. A deployment with a policy to
meet cannot say so, and one that wants something laxer for a house full of
tablets cannot say that either.

What is actually there today:

- **One number for both populations, deliberately.** `password_fault()` says so
  in as many words: "there is one rule in this product for how long a password
  has to be, and a second number for a second population would be two answers
  to one question." It judges a person's password; the panel's own accounts are
  judged by two separate `len(new) < MIN_PASSWORD` tests in the admin routes.
- **So the rule is written out three times.** `password_fault()` for people,
  and twice more where an admin account's password is set or changed. A fourth
  rule added to only one of them is a rule that applies to some passwords.
- **The panel is told the number** — `pw_min` rides along with the identities
  payload — so whatever is chosen has somewhere to be shown without a second
  fetch.
- **512 is the ceiling**, and it is not a policy: it is there so a hash is not
  computed over a megabyte somebody pasted.

**To decide first**, and each answer is a different amount of work:

- **A length, or a policy?** A number in a box is one setting and covers most
  of what a deployment is asked to prove. Character classes are four more
  ticks, and they are the part security guidance has been moving away from for
  a decade — worth deciding on purpose rather than adding because a form
  usually has them.
- **One rule or two?** The comment above is a decision already taken, and a
  panel account and a hallway sign-in are genuinely different risks. Changing
  it means saying why the earlier reasoning no longer holds.
- **What happens to passwords that already exist.** Raising the minimum cannot
  retroactively refuse them: they are hashes, and the length is unknowable. So
  either the rule applies at the next change only — quiet, and leaves weak
  passwords in place — or somebody has to be forced to set a new one, which is
  a mechanism this product does not have.
- **Where it is said.** The rule has to reach the person choosing a password,
  on a page they open from a one-shot link, or they find out by being refused.

Whatever it becomes, it should be **one place that answers "is this password
allowed"**, called by all three sites — the value is a setting, the judgement
is not three copies of an `if`.
