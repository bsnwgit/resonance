# Troubleshooting

Symptom, cause, and the thing to look at. The mechanisms themselves are
elsewhere — [node setup](node-setup.md), [speech](speech.md),
[administration](administration.md), [app settings](app-settings.md),
[the HTTP API](http-api.md). This is the path through them when something is
not working.

**One habit first.** A node that "does nothing" is almost always a link further
back in the chain than the one being looked at. Resonance is not one form with
one setting — it is MODELS and NETWORK feeding a CONNECTION, which a LAYOUT and
an AUTHENTICATE/AUTHORIZE pair then decide who may open. Work the chain in
[node setup](node-setup.md) from the front, not from the screen.

---

## Contents

- [Start here: the startup banner](#start-here-the-startup-banner)
- [The server will not start](#the-server-will-not-start)
- [`serve.sh status` disagrees with reality](#servesh-status-disagrees-with-reality)
- [The admin interface is missing](#the-admin-interface-is-missing)
- [A port is taken](#a-port-is-taken)
- [The microphone does not work](#the-microphone-does-not-work)
- [Transcription is wrong, slow, or silent](#transcription-is-wrong-slow-or-silent)
- [The wake word never triggers](#the-wake-word-never-triggers)
- [A display shows nothing, or the wrong thing](#a-display-shows-nothing-or-the-wrong-thing)
- [A screen never dims, or dims at the wrong time](#a-screen-never-dims-or-dims-at-the-wrong-time)
- [The status line is missing](#the-status-line-is-missing)
- [A page silently does nothing](#a-page-silently-does-nothing)
- [The assistant does not answer](#the-assistant-does-not-answer)
- [An embed will not render](#an-embed-will-not-render)
- [You are locked out](#you-are-locked-out)
- [What to capture before reporting a problem](#what-to-capture-before-reporting-a-problem)

---

## Start here: the startup banner

Resonance prints what it actually started, every time. Read that before
believing any setting.

```bash
./serve.sh status
```

```bash
tail -n 60 server.log
```

The banner tells you which listeners came up. **A listener you configured that
is not in the banner did not start**, and the reason is on the lines around it.
That single check answers more questions here than anything else, because most
of Resonance's confusing states are a listener that quietly declined to bind.

Two things the banner will also tell you loudly, deliberately, and repeatedly:

- **Reachable beyond this machine with no sign-in.** This is permitted, and it
  is warned about at every startup, in the panel, and across the display itself.
  It is not a bug report — it is the configuration you chose.
- **No certificate**, where one is needed. See below.

---

## The server will not start

There is no systemd unit and no sudo involved — Resonance is deliberately a
plain process:

```bash
./serve.sh start
./serve.sh stop
./serve.sh status
```

If it does not come up, `serve.sh` says so and names the file to read:

```bash
tail -n 100 server.log
```

| Symptom | Cause |
|---|---|
| Exits immediately, nothing in the banner | A configuration that cannot work. The server refuses those rather than starting into a half-state — the error names what it refused |
| Admin listener absent | No certificate, on a non-loopback bind. See [The admin interface is missing](#the-admin-interface-is-missing) |
| A profile's listener absent | Its port is taken, or its address is not on this machine. See [A port is taken](#a-port-is-taken) |
| Starts, but no display anywhere | Every network profile is its own listener now. There is no built-in display listener to fall back on — if no profile is up, nothing serves a display |
| Python or dependency error | Check the interpreter `serve.sh` resolved and that `requirements.txt` is installed |

A configuration that cannot work is refused on purpose. Starting anyway and
appearing to succeed is worse than any error, because it looks like it worked.

---

## `serve.sh status` disagrees with reality

`serve.sh` reads the **admin** port from `app.json` to decide whether the server
is running — not a display port.

That is deliberate, and it is a fix for a real failure: it used to anchor on
`http_port`, the old built-in display listener. That listener is gone. Every
network profile is its own listener and none of them is special, so a
deployment can legitimately have nothing on the old display port at all. When
that happened, `status` reported "down" for a server that was running, and
`stop` did nothing.

| Symptom | Cause |
|---|---|
| Says down, but it is clearly serving | You are on an older copy of `serve.sh` that anchors on the display port |
| `stop` does nothing | Same |
| Says up, but nothing answers | The admin listener is up and a profile's is not — check the banner |

`serve.sh` never pattern-kills. It prefers the recorded pid, and a pid is only
treated as ours if it is alive **and** running this directory's `serve.py`.
If you are killing processes by hand, apply the same standard.

---

## The admin interface is missing

The admin listener (default **9702**) is the configuration interface, and it is
the only port still configured in `app.json`. It stays there deliberately: **it
is the way back in when what is in a profile is wrong.**

Whether it needs a certificate depends entirely on the bind:

| Bind | Admin listener |
|---|---|
| **Loopback** | Plain HTTP. No certificate involved — browsers already treat `http://localhost` as a secure origin, and nothing crosses a network |
| **Anything else** | **HTTPS-only, and refuses to start without a certificate.** It takes a password and holds the assistant's API key; neither may cross a network in the clear |

So: admin missing from the banner on a non-loopback bind means no certificate.

```bash
./make-cert.sh
```

Then restart. A self-signed certificate throws one browser warning — accept it,
and the origin counts as secure from then on.

**The public listeners cannot substitute.** There is no way to write settings
from them: they serve the display and answer `GET /settings`, and nothing more.
If the admin listener is down, settings cannot be changed from anywhere else.

---

## A port is taken

Every listener binds. Two settings decide the shape of it, and they are
deliberately **not** collapsed into one "mode" — a single label covering both
starts lying the moment somebody changes half of it:

- `bind` — loopback, a specific address, or everything
- `auth` — none, or accounts

| Symptom | Cause |
|---|---|
| Refusal naming a port | Something else holds it. The message names the port **and the address**, because a refusal that names only the port sends you looking at the wrong thing |
| Wildcard bind refused | The kernel refuses a wildcard bind when a specific address on that port is already held. Bind the specific address, or free the other listener |
| A port that "should be free" is not | Another Resonance instance, or a stale process. Resolve the pid exactly rather than pattern-killing |

For a second instance, the environment still overrides everything:
`PORT`, `HTTPS_PORT` and `ADMIN_PORT`. **`PORT` alone shifts all three** to
`PORT`, `PORT+1`, `PORT+2` — so a second instance needs no stored configuration
of its own.

Note that an upgrade turns the ports an install already had into a profile
called **Display** — 9701, with 9700 redirecting to it. If your ports moved
after an upgrade and you did not change anything, that is what happened.

---

## The microphone does not work

**Browsers will not open a microphone on an insecure origin.** Nothing in
Resonance can override that, because it is not Resonance's decision — the
browser refuses before any of this code runs.

| Situation | Microphone |
|---|---|
| HTTPS | Works |
| `http://localhost` (loopback) | Works — the browser already treats loopback as secure |
| Plain HTTP over a network | **No microphone.** The display still works; it just cannot listen |

So the fix is almost always: **give people the HTTPS address**, not the plain
one. If HTTPS is not running, see [The admin interface is
missing](#the-admin-interface-is-missing) — the same missing certificate
disables both.

A self-signed certificate throws one browser warning. Accept it once and the
origin is secure from then on — including for `getUserMedia`.

---

## Transcription is wrong, slow, or silent

`POST /stt` takes an audio blob and returns `{"text": "..."}`, transcribed by
faster-whisper running **on this machine**. Nothing is sent to a third party —
that is the whole reason it exists rather than using the browser's
`SpeechRecognition`, which ships audio to Google.

It is served from the same origin as the page, so there is no CORS and no
mixed-content problem to chase.

| Symptom | Cause |
|---|---|
| No transcription at all | The microphone never opened — see above. Check the browser console for a `getUserMedia` refusal before suspecting the model |
| Very slow | The model is running locally on this host's CPU. A larger model on a small machine is slow, and that is the trade-off being made |
| Poor accuracy | Model size, microphone placement, and room noise. The transcriber is chosen on the speech profile |
| Works for one display, not another | Speech settings are a property of the **speech profile**, which is shared where a wake word cannot be |

---

## The wake word never triggers

**The words are on the LAYOUT profile, not the speech tab.** The wake word, the
alternate spellings it will also accept, LEARN, whether matching is forgiving,
and the sleep word with its spellings all sit beside the face, the voice and the
greeting — because those are one answer to *what is this assistant*, rather than
four.

The speech tab is what a display **hears and says** — the transcriber, the
voice, how long it stays awake. That is a property of the room and the machine,
which is why a speech profile can be shared where a word cannot.

| Symptom | Cause |
|---|---|
| Never triggers | Looking on the wrong tab. The word is on LAYOUT |
| Triggers on the wrong assistant | **Two layouts given the same word are not caught.** The word is what tells two assistants apart — settle it before a household learns them |
| Sometimes triggers | Forgiving matching is off, or the spoken form is not among the alternate spellings. Add the spellings people actually say |
| Responds to any conversation in the room | No wake word set on an AUTO display. Without one it answers any speech near it, including two people talking to each other. That is what the wake word is for |

---

## A display shows nothing, or the wrong thing

Work the chain from [node setup](node-setup.md), in order — MODELS and NETWORK,
then CONNECTION, then LAYOUT, AUTHENTICATE and AUTHORIZE. Each link can only
name the one before it, which is why the failure is usually further back than
the screen.

| Symptom | Likely link |
|---|---|
| Nothing served at that address at all | NETWORK — the profile's bind address and port |
| Served, but no assistant answers | MODELS, or the CONNECTION joining a model to a network |
| Wrong appearance, greeting or voice | LAYOUT |
| Asked to sign in unexpectedly | AUTHENTICATE — whether there must be a person, and how long a session lasts |
| Signed in, still refused | AUTHORIZE — ANY DISPLAY, or only the ticked screens, people, groups and embeds |
| The display is stale after a change | A screen takes a change at its **next check-in**; a person's applies at their **next sign-in** |

**A device is never told the list.** It is handed the three numbers of the
profile it uses and nothing else — the list of names is a description of a
building, and no screen has any use for the names of places it is not in. So do
not expect a screen to know about a profile it is not on.

Resonance sends `no-store` on everything, precisely so a browser cannot sit on a
cached `index.html` and leave you debugging code that is no longer running. If
you are seeing genuinely stale behaviour, it is not the HTTP cache.

---

## A screen never dims, or dims at the wrong time

**A listening screen is an idle screen.** The microphone being open is not a
conversation: a wall display transcribes every noise in the room, because that
is the only way a wake word is ever caught, and none of it is somebody talking
to that screen. The idle clock does not stop for it.

What *does* stop it: the assistant speaking aloud, a clip playing, a question
outstanding, or the wake window still open after somebody woke it.

| Symptom | Cause |
|---|---|
| Never reaches the screensaver | On an older build this asked the figure's own state — a flag set from six places, where any one returning early left it set, after which that screen never dimmed again with nothing on screen to say why. Confirm you are current |
| Dims mid-conversation | The wake window closed. It exists to stop a screen dimming at somebody standing in front of it |
| Dark at the wrong hour | **Dark hours are read off the device's own clock, not the server's.** A building with screens in two time zones has each dark at its own two in the morning |
| Dims more than expected at night | Idle and dark hours are different questions and never add up — whichever is darker at that moment wins. A screen already drifting at night does not go past black |
| Content looks cut off while drifting | It should not be: the travel is exactly the margin the shrink bought |
| Transcript and composer vanish | They hide while it drifts, and come back the instant you touch it. Text sliding around a screen is worse than either state alone |

---

## The status line is missing

**It is a troubleshooting tool and it is off** — on every screen and every
person — until somebody turns it on.

There are two switches and **either one is enough**: a **device** carries one,
and a **person** carries one that follows them to whatever they sign in at.
On/off, off/on and on/on all show it; only off/off hides it.

| Where | How |
|---|---|
| Per row | The row's own bottom bar, on both registers. It says the state it **is in**, not the state it would move to |
| In bulk | Tick the rows and use *Status line* — the bar above the device register on EndPoints, and the one above the people on IDENTITY ▸ USER |

A screen takes the change at its next check-in; a person's applies at their next
sign-in.

---

## A page silently does nothing

There is no build step here, and that is deliberate — but it means nothing reads
these files between saving them and a browser running them.

**An inline script that does not parse is not a broken feature: it is a page
where nothing runs.** It looks like three unrelated things missing at once
rather than like a syntax error. That has happened, from a statement added under
a brace-less `if`, and the first thing to notice was a browser.

So when a page is inert:

```bash
./check.sh
```

It runs both pages' inline scripts and `embed.js` through node's parser, and
both Python modules through Python's. Line numbers come back pointing at the
HTML file rather than at the extracted script, because a number that needs
arithmetic done to it is a number somebody reads wrong.

**It parses. It does not run, and it cannot tell you the page works.** A missing
parser is a failure, not a skip — a check that quietly passes when its tool is
absent is worse than no check.

---

## The assistant does not answer

| Symptom | Cause |
|---|---|
| No answer at all | The CONNECTION has no usable model, or the model profile's provider cannot be reached |
| A hosted provider with no key | It cannot answer. The configuration is refused rather than silently producing nothing |
| Answers on one display, not another | Different connections. Check which profile that endpoint uses |
| Slow first answer | Model load, or a cold provider |
| Home Assistant routes fail | See [assistants](assistant.md) — the route configuration is separate from the provider |

---

## An embed will not render

Resonance refuses to render inside a page nobody authorised, and **that refusal
looks exactly like a broken widget rather than a configuration gap.** It is
almost always the origins list.

| Symptom | Cause |
|---|---|
| Nothing renders on the host page | The host's address is not on the key's origins list. Add it |
| Renders, then fails later on the session call | The wrong server address was given to the host — the *interface* server, not the admin portal. The admin portal looks almost right and fails at exactly that point |
| Works for some users | The roles allowed to open it |
| Not sure the key is right | Use the test path before turning the feature on — it proves the key and reads back what it grants |

[Embedding](embedding.md) is the operator's side of this; [integrating](integrating.md)
is the contract to send the host's developer.

---

## You are locked out

The admin listener is the way back in, and that is why it is the one port still
pinned in `app.json` rather than living in a profile that could be misconfigured.

| Situation | Way back |
|---|---|
| A profile's settings are wrong | Use the admin listener — it is independent of every profile |
| The admin listener will not start | No certificate on a non-loopback bind. Run `make-cert.sh`, or temporarily bind loopback and reach it over SSH |
| Admin port unknown or changed | It is in `app.json`. `serve.sh` reads it from there too |
| Nothing is reachable at all | Bind loopback and use an SSH tunnel. Loopback needs no certificate |

Do not try to change settings from a display listener. They serve the display
and answer `GET /settings` — there is no write path there by design.

---

## What to capture before reporting a problem

1. The **startup banner** from `server.log` — which listeners actually came up.
2. `./serve.sh status`, and whether it agrees with what is really serving.
3. `./check.sh` output, if a page is inert.
4. Which link in the [node setup](node-setup.md) chain you have verified,
   starting from MODELS and NETWORK — not from the screen.
5. Whether the address in use is HTTPS, loopback, or plain HTTP over a network.
   That decides the microphone before anything else does.
6. For a wake word problem: which LAYOUT the endpoint uses, and whether another
   layout shares the word.
7. For an embed: the host origin, and whether it is on the key's origins list.

Never paste the assistant's API key, account passwords, or the contents of
`app.json`.
