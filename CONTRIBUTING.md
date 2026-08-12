# Contributing to Resonance

## Branch strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready code — reflects what is deployed |
| `feature/<name>` / `fix/<name>` | Individual features or bug fixes, branched from `main` |

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

```bash
rsync -az --exclude-from=.gitignore ./ <host>:<path>/
ssh <host> '<path>/serve.sh stop; <path>/serve.sh start'
```

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
| `admin.key` | grants write access to the shared settings |
| `key.pem`, `cert.pem` | TLS private key and certificate |
| `settings.json` | deployment state, not source |
| `voices/` | Piper models, 60–120 MB each, downloadable |
| `stt-venv/` | virtualenv |
| `server.log`, `*.wav` | runtime noise |

If you add anything that writes a credential to disk, add it here **and** to
`.gitignore` in the same commit.

## Project layout

Deliberately flat — this is a single page plus a single server file.

| File | Purpose |
|---|---|
| `index.html` | the display: visualiser and chat surface. No controls. |
| `admin.html` | the configuration interface, served only on the admin port |
| `serve.py` | static serving, `/stt`, `/tts`, `/settings`, accounts and sessions |
| `serve.sh` | start/stop, resolving the PID from the port |
| `make-cert.sh` | self-signed certificate for the HTTPS listener |

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

**Settings are admin-only by design.** Ordinary users get the microphone, mute,
and the push-to-talk/hands-free choice. Nothing else. A visibility gate must be
confirmed by the server — never inferred in the browser.

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
  docs: expand the admin key section
```
