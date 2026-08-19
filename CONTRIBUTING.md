# Contributing to Resonance

## Branch strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready code — reflects what is deployed |
| `feature/<name>` / `fix/<name>` / `design/<name>` | One round of work, branched from `main` |

## Workflow

### Starting new work

```bash
cd resonance

# Make sure you're up to date
git checkout main
git pull

# Create a feature branch
git checkout -b feature/your-feature-name
```

### Committing changes

```bash
git add -A
git commit -m "short description of what changed"
git push -u origin feature/your-feature-name
```

### Opening a PR

```bash
gh pr create --base main --head feature/your-feature-name --title "Your feature title"
```

Always cut a brand-new branch off `main` for each round of work — don't reuse a
branch name across unrelated changes, since a previously merged branch name can
be silently re-merged as a no-op.

**PRs are not self-merged.** Open it and leave it for review.

### Deploying

Deploy to the test server and confirm it works **before** pushing or opening
the PR, not after. The visualiser, the microphone and the voice pipeline can
only really be judged live.

Parse first, deploy second:

```bash
./check.sh
```

There is no build step here, so nothing reads these files between saving them
and a browser running them. `check.sh` puts both pages' inline scripts through
node's parser and both Python modules through Python's, and reports the line
number of the **HTML file** rather than of the extracted script. It ends a
script where a browser ends it — at the first `</script`, wherever that falls —
so a page it passes is the page a browser will actually run. It only parses: a
page that parses can still be wrong, but a page that does not parse is one
where *nothing* runs, and that reads as several unrelated pieces of the
interface missing at once rather than as a syntax error.

It needs `node` on the machine you deploy **from** — for parsing only, nothing
is installed and nothing about the server changes. A missing parser is a
failure rather than a skip, so it cannot pass quietly on a machine that cannot
run it.

Then deploy:

```bash
rsync -az --exclude=.git --exclude-from=.gitignore ./ <host>:<path>/
ssh <host> '<path>/serve.sh stop && <path>/serve.sh start'
```

**`--exclude=.git` is not optional.** `.gitignore` does not list `.git`, so
without it one rsync puts the entire repository — source and full history —
into a directory the display listener serves files out of. `serve.py` now
refuses any path with a dot-prefixed segment, so a repository that got there
before is no longer readable over HTTP, but do not rely on that: it should
not be on the box in the first place.

- **Never deploy directly from a feature branch to anything shared** — merge to
  `main` first.
- **Nothing hardcodes an absolute install path.** Every path derives from the
  location of `serve.py` at runtime.
- **`serve.sh` runs as the normal user**, never `sudo ./serve.sh`.

## What must never be committed

Already covered by `.gitignore`, but worth stating plainly, because several of
these are generated on the server and are either secret or large:

| Path | Why |
|---|---|
| `users.json` | password hashes and roles |
| `key.pem`, `cert.pem` | TLS private key and certificate |
| `settings.json` | the shared interface configuration — deployment state, not source |
| `app.json` | ports and session length — deployment state, not source |
| `server.pid` | whichever process happens to be running |
| `voices/` | Piper models, 60–120 MB each, downloadable |
| `stt-venv/` | virtualenv |
| `server.log`, `*.wav` | runtime noise |

`admin.key` appears in `.gitignore` and no longer exists. The shared key it
held was retired when administration moved behind accounts; the ignore rule
stays so an old deployment's leftover file cannot be committed by accident.

If you add anything that writes a credential to disk, add it here **and** to
`.gitignore` in the same commit.

## Project layout

Deliberately flat — this is a single page plus a single server file.

| File | Purpose |
|---|---|
| `index.html` | the display: visualiser and chat surface. No controls. |
| `admin.html` | the configuration interface, served only on the admin port |
| `serve.py` | static serving, `/stt`, `/tts`, `/settings`, `/app`, accounts and sessions |
| `manual.py` | the in-app manual's registry, and its dependency-free PDF writer |
| `serve.sh` | start/stop, resolving the PID from the port |
| `make-cert.sh` | self-signed certificate for the HTTPS listener |
| `check.sh` | parses both pages and both modules; run it before a deploy |

Resist splitting `index.html` until the visualiser is extracted as a package —
at that point the split should be *core vs demo shell*, not an arbitrary
file-per-concern.

## Conventions

**The visualiser has zero runtime dependencies and should stay that way.**
Canvas 2D, no WebGL, no charting library. It is the main reason this is easy to
embed elsewhere.

**Everything that drives the geometry goes through `Drive`.** `hit(weight)` and
`level` are the entire contract. If a new input source needs anything more than
those two, that is a design smell worth discussing first.

**The demo backend stays forever.** It is how you tell whether a fault is the
front-end or the model behind it. Don't remove it when a real assistant is
connected.

**Nothing privileged is reachable from the public listeners.** Not gated —
absent. If you add a route that writes, it goes behind `_require('admin')` and
returns 404 when `self.admin_port` is false. The display page must never
regain a control that writes.

**Settings are admin-only by design.** A viewer gets the microphone, mute, the
push-to-talk/hands-free choice, and whether the transcript is shown. Nothing
else, and adding a fifth is a decision rather than a convenience. Those four
are remembered in that viewer's browser and outrank whatever the screen was
given; everything else is set in the panel, because the point of it is that one
person decides what everyone sees. A visibility gate must be confirmed by the
server — never inferred in the browser.

**There is no shared appearance document.** APPEARANCE, GEOMETRY and SPEECH are
a workbench: you tune them against the preview and capture the result as a
profile, and a screen shows the profiles it NAMES and nothing else. The keys
those tabs own are dropped out of a display's settings on the way to it — see
`display_document` — so tuning a tab and walking away cannot repaint a
building. Nothing in any list is nominated as a default, in either sense: no
profile stands in for a choice nobody made, and none of them recreates itself
when the one before it is deleted.

**Record the non-obvious failures.** The *Engineering notes* section of the
README exists so the same day isn't lost twice. If something cost you hours and
the cause was surprising, add it.

## Commit message style

```
type: short description (imperative, lowercase)

Examples:
  feat: add barge-in during playback
  fix: stop the wake gate expiring mid-answer
  chore: bump faster-whisper
  docs: expand the accounts section
```
