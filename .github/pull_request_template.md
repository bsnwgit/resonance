<!--
Short on purpose. CONTRIBUTING.md carries the reasoning; this is the part that
has to be true before anybody reads the diff.
-->

## What this changes, and why

<!-- The reasoning, not the file list — the diff already has the file list.
     If it fixes something that was not obvious, say what the cause turned out
     to be: docs/progress-log.md exists so the same day is not lost twice. -->

## Checks

- [ ] `./check.sh` passes locally (it needs `node` and `python3`, nothing else)
- [ ] Ran against a live display, or says below why that was not possible —
      the visualiser, the microphone and the voice pipeline can only really be
      judged in a browser
- [ ] User-visible behaviour is reflected in `docs/`
- [ ] Nothing here writes a credential to disk without an entry in both
      `.gitignore` and the table in CONTRIBUTING.md
- [ ] No real hostname, address or credential in the diff — including in
      comments, examples and fixtures

## If it adds a route

- [ ] Behind `_require('admin')` and answers 404 when `self.admin_port` is false
- [ ] Anything rendered from user or device data goes to `textContent`, or
      through `esc`/`rtEsc` where it genuinely has to be markup
