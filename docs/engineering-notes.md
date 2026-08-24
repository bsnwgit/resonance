# Engineering notes

Things that cost real time and are not obvious. Recorded so they are not
rediscovered.

**A certificate valid for more than 398 days fails in Chrome**, and often as a
*blank page* rather than the usual click-through warning. `make-cert.sh` uses
365 days.

**Do not bias the decoder toward your wake word.** Both `initial_prompt` and
`hotwords` cause faster-whisper to treat the hinted word as context already
supplied and **omit it from the transcript** — silently breaking the matching
the hint was meant to help. Measured both ways. `?hint=` remains useful for
domain vocabulary you only need spelled correctly when it does appear.

**A general speech model will not reliably spell one short word the way a given
person says it.** A one-syllable wake word comes back with the wrong vowel,
a stray plural, or a trailing full stop. Tuning
the model, the beam size and the thresholds all helped a little and none of it
was enough. The fix was to stop fighting the speller: capture what the
transcriber actually produces for that speaker and accept those forms.

**Silence-only voice detection is a trap.** If the room's noise floor sits above
the gate, the level never returns to zero, the utterance never "ends", and
nothing is ever transcribed — while the visualiser keeps reacting happily. There
is now a maximum-utterance cut, a live level meter, and a calibrate button.

**Never let one threshold serve both the visuals and the speech detector.**
Sharing it means raising the gate so utterances end also forces the user to
shout to be heard. They are separate now: the geometry keeps the configured
gate, detection uses an adaptive threshold that floats above the measured room
floor.

**Browser speech synthesis cannot be tapped by an analyser**, so a browser-voice
envelope has to be estimated from word-boundary events. Rendering the voice
server-side and playing it through Web Audio removes the guesswork entirely —
the geometry follows the actual waveform.

**Turn the browser's audio processing back on when a human is being
transcribed.** Auto-gain and noise suppression were disabled to preserve the
dynamics the visualiser feeds on; the result was quiet audio and constant
mishearing. There is now a toggle, defaulting to clean.

**Setting `scrollbar-width` makes Chrome ignore `::-webkit-scrollbar`.** The
standard property and the pseudo-elements are not additive: specify the
standard one and the browser drops the webkit rules and falls back to the
operating system's overlay bar, which on macOS is invisible until you scroll.
Measured — the scroller reserved 0px of layout instead of 9. Safari ignores
the standard properties entirely, so neither alone covers both. The
pseudo-elements are unconditional and the standard properties sit behind
`@supports not selector(::-webkit-scrollbar)`.

**A `stop` that returns before the process exits will take the service down.**
`stop && start` raced: the old process still held the listening sockets, the
new one died on `Address already in use`, and the result was nothing running
at all rather than an obvious failure. Stopping now waits for the pid to
actually go, with a ceiling after which it reports failure instead of claiming
success, and starting waits for the bind rather than assuming a second is
enough.

**Two code paths that render the same thing will not stay in step.** The
transcript was revealed by three different routes — token stream, browser
voice, neural voice — and only two of them scrolled. The neural path is the
default engine, so the visible symptom was that a long spoken reply ran off
the bottom and only appeared once something else forced a scroll. Everything
that reveals text goes through one helper now.

**A control panel hidden by CSS is still shipped.** The settings panel used to
live in the display page and be revealed once an admin key checked out. Every
viewer was still sent the whole thing — 105 elements of it — and the gate was
one bug away from being the only thing standing between them and it. It is a
separate page on a separate port now, and the public listeners do not serve it
at all.

**A top-level `const` is not a property of `window`.** The admin page tried to
read the display's settings out of the iframe with `frame.contentWindow.S` and
got `undefined`, so every slider silently fell back to the browser's default
midpoint — a page full of plausible wrong numbers, with nothing logged. The
display now sends its settings in the message that announces it is ready.

**A visibility gate must be confirmed by the server.** An early version checked
only that an admin key was *present*, not that it was *correct* — so
`?admin=anything` opened the settings panel. Writes still failed, but the
interface users are not supposed to have was one guessed parameter away.

**A deliberately inert feature must say it is inert.** The wake word applied
only to hands-free mode and did nothing in push-to-talk, with no indication —
it read as simply broken. The panel's live status text now states whether each
gate is in effect and why, and the gate grew an ALWAYS mode for anyone who
wants the word required in push-to-talk too.

**And saying so in the panel is not saying so where it happens.** That status
text was written for the admin sitting in front of the settings; the person
standing in front of the *display* got nothing, for a year, because the two
elements it writes to were never in `index.html` at all. The lesson is not
"add a status line" — it is that a message is only delivered where the fault
is experienced, and a panel that reports faults to their configurer instead of
their witness has not reported them.

**A deployment directory is not a document root.** `SimpleHTTPRequestHandler`
serves what is beside it, and beside it were `key.pem`, `users.json`,
`routes.json` and the source. The fix is an allow-list of the four files that
are genuinely pages or artwork; the lesson is that a *denylist* of secrets
cannot be written correctly, because the file holding one credential per route
did not exist yet when it would have been written. Deny by default, and
enumerate what is published rather than what is withheld — the same shape as
`public_routes()`.

**A dangling CSS selector list is invisible to every check.** Deleting a rule
took the `{max-width:560px}` off the end of a shared selector list, leaving
three selectors reading on into the next rule — which was `display:none`, so
the filter field, the tab caption and the whole tab row vanished. The braces
still balanced, the JavaScript still parsed, and CSS has no error to report:
it simply continues to the next block. The check that catches it is that no
comma-terminated selector line may be followed by a comment or a blank line.

**A script that does not parse is a page where nothing runs**, and it does not
present as a syntax error. It presents as several unrelated pieces of the
interface being absent at once — here the visualiser, the enrolment box, the
request form and the sign-in box, leaving the static markup alone on screen — which
reads as four faults rather than one, and sends you looking at four features
instead of at the parser. The cause was a statement added under a brace-less
`if`, which pushed it out of the body and orphaned the `else` below it. With no
build step, nothing between saving the file and a browser opening it ever reads
it, so this shipped and deployed clean; `check.sh` is the answer, and it must
end the script where a browser does — at the FIRST `</script`, in a string or a
comment or anywhere else — because reading to the last one hands the parser a
file no browser will run.

**The two tool-calling dialects agree on the definitions and disagree on the
replay.** A tool definition is the same object in both, one field name apart —
`parameters` for the OpenAI shape, `input_schema` for Anthropic. What differs
is how the round already taken is handed back: OpenAI wants an `assistant`
message carrying `tool_calls` followed by a `role: "tool"` message keyed on
`tool_call_id`, and Anthropic wants an `assistant` message whose content is a
`tool_use` block followed by a **user** message whose content is a
`tool_result` block keyed on `tool_use_id`. Get it wrong and the model does not
error — it calls the same tool again, because from where it sits nothing came
back.

**A model that cannot see a result will loop for ever, so the lap is what needs
bounding, not the call.** The obvious guard is a timeout on the request. The
failure in practice is a model calling the same operation on every pass because
its result never reached it in a shape it recognised — each pass a fresh
request, each one fast, none of them wrong enough to throw. Four laps, counted
in the request rather than held on the server.

**An embedded panel cannot reach the host's API and must not try.** It is on
another origin, holds no credential of theirs, and any fix for that — CORS on
their side, a service account on ours — is worse than the problem. The page it
is framed in is already authenticated as the person; make the request there.
The cost is that the loop runs through a request rather than inside one, which
is a smaller price than it sounds and buys the whole permission model.

**`flex: 1` on an `<input>` is not enough.** An input's default `size`
attribute is its flex basis, so it sits at about twenty characters on a row
with plenty of room. It needs `min-width: 0` beside it.

**A reverse proxy's read timeout applies to each lap, not to the question.**
A tool-calling turn is several HTTP requests, each waiting on a whole model
pass. nginx's `proxy_read_timeout` defaults to 60 seconds and is usually not
set anywhere, so nobody remembers choosing it. When it fires the server
completes the lap and then dies writing the response — `ssl.SSLEOFError: EOF
occurred in violation of protocol` — and the browser sees a dead connection.
Measured on a CPU-only box: 30s a lap warm, 48s cold, and a question needing
three laps failed while the same question in two laps succeeded. The tell is
that it looks intermittent and looks like the assistant, and it is neither.

**A small model answers a rejected tool call by calling the same one again.**
Given a 400 it does not reconsider which operation it chose; it re-guesses a
parameter and re-sends. Observed: `getSyslogTimeline?hours=24&point_limit=10`
→ 400 → `getSyslogTimeline?hours=24&bucket_minutes=144`, when the question
wanted a different operation entirely. Two consequences. An API's 400 should
name the valid values rather than say no, because a model reads it and is the
one retrying. And every wrong choice costs a whole extra lap, which is what
turns a latency problem into a timeout.

**Tool calling is where model size stops being a preference.** The job is
choosing among a set of operations and filling parameters from a sentence, and
a 3B model does it wrongly often enough to matter — while the fix, a larger
model, is the opposite of what a latency-sensitive voice interface wants on
CPU-only hardware. There is no local answer to that tension on a box without a
GPU; the honest options are a hosted endpoint for the sites that need it, or
different hardware.

**Log the request and never the response.** For a call made on somebody else's
behalf into somebody else's application, the method, path and query are the
line to keep — it matches what their own access log recorded, so the two can be
laid side by side and the argument about who dropped it ends in a minute. The
body is their data, and `server.log` is a stream that travels off the machine.

**`strings` cuts a line at the first multi-byte character.** Reading a log
that contains an em-dash, every line appeared truncated exactly where the
message became interesting, which reads convincingly as a bug in the code that
wrote it. Decode the file rather than scraping printable runs out of it.
