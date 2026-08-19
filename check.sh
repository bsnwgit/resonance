#!/usr/bin/env bash
# Everything that has to parse before this is deployed.
#   ./check.sh
#
# There is no build step here, and that is deliberate — but it means nothing
# reads these files between saving them and a browser running them. An inline
# script that does not parse is not a broken feature: it is a page where
# NOTHING runs, and it looks like three unrelated things missing at once
# rather than like a syntax error. That happened once, from a statement added
# under a brace-less `if`, and the first thing to notice was a browser.
#
# So: both pages' inline scripts through node's parser, both Python modules
# through Python's. Line numbers come back pointing at the HTML file rather
# than at the extracted script, because a number that needs arithmetic done to
# it is a number somebody reads wrong.
#
# It parses. It does not run, and it cannot tell you the page works.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

# A missing parser is a FAILURE, not a skip. A check that quietly passes when
# its tool is absent is worse than no check: it is the same green line either
# way, and the one time it matters is the time nobody notices it went quiet.
if ! command -v node >/dev/null 2>&1; then
  echo "check: node is not installed — the pages cannot be parsed" >&2
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "check: python3 is not installed" >&2
  exit 2
fi

# The inline scripts out of a page, parsed, with node's line numbers moved back
# onto the file a person edits.
check_page() {
  python3 - "$DIR/$1" <<'PY' || return 1
import os, re, subprocess, sys, tempfile
from html.parser import HTMLParser

page = sys.argv[1]
name = os.path.basename(page)
try:
    src = open(page, encoding="utf-8").read()
except (OSError, UnicodeDecodeError) as e:
    # A traceback here is a false lead — it looks like a fault in the checker
    # rather than in the thing being checked.
    print("%s: cannot be read — %s" % (name, e), file=sys.stderr)
    sys.exit(1)


# WHERE A SCRIPT ENDS IS THE BROWSER'S ANSWER, NOT A REGULAR EXPRESSION'S.
#
# This started as first `<script>` to last `</script>`, which is wrong in both
# directions and wrong in the dangerous one first: a browser ends the script at
# the FIRST `</script`, inside a string or a comment or anywhere else, because
# the HTML tokenizer has never heard of JavaScript syntax. So a page carrying
# that text in a string ships as a truncated script that stops at the string
# and runs nothing after it — and a checker reading to the last `</script>`
# hands the parser the whole file and calls it well. That is this checker
# passing the exact failure it was written to catch.
#
# html.parser tokenizes script content the way a browser does, and it reports
# the line each block starts on, which is what makes the numbers below point at
# the page rather than at an extract of it.
class Scripts(HTMLParser):
    def __init__(self):
        # Character references are NOT decoded inside a script by a browser,
        # and must not be here either, or `&amp;&amp;` would be checked as the
        # `&&` the browser will never see.
        HTMLParser.__init__(self, convert_charrefs=False)
        self.blocks = []                 # (first line, attrs, text)
        self.stray = []                  # `</script>` closing nothing
        self._open = None
    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self._open = dict(attrs)
            self._line = self.getpos()[0]
            self._text = ""
    def handle_data(self, data):
        if self._open is not None:
            self._text += data
    def handle_endtag(self, tag):
        if tag != "script":
            return
        if self._open is None:
            self.stray.append(self.getpos()[0])
            return
        self.blocks.append((self._line, self._open, self._text))
        self._open = None

p = Scripts()
p.feed(src)
p.close()

# `src` is somebody else's file; a block with one of these is not this page's
# own code and is not ours to parse.
def inline_js(attrs):
    if attrs.get("src"):                 # loaded from elsewhere
        return False
    kind = (attrs.get("type") or "").strip().lower()
    return kind in ("", "text/javascript", "application/javascript", "module")

# A `</script>` that closes nothing is the fingerprint of the failure above,
# and the reason it needs its own check: when an earlier one truncates the
# block, what is left can still be perfectly valid JavaScript — the first 900
# lines of a 4500-line script usually are — so the parser is happy and the
# page is dead from that line down. The real closing tag, now orphaned, is what
# says so. Nothing else in these pages ever produces one.
if p.stray:
    print("%s: `</script>` at line %s closes nothing — an earlier one inside "
          "the script ended it, and a browser stops there too"
          % (name, ", ".join(str(n) for n in p.stray)), file=sys.stderr)
    sys.exit(1)

blocks = [b for b in p.blocks if inline_js(b[1])]
# A FLOOR ON WHAT COUNTS AS A PASS. Empty is valid JavaScript, so an extraction
# that collapsed to nothing parses perfectly and says so — the one outcome that
# must never read as success, because it means the file was never examined.
if not any(b[2].strip() for b in blocks):
    print("%s: no inline script found — nothing was checked" % name,
          file=sys.stderr)
    sys.exit(1)

bad = 0
for start, attrs, body in blocks:
    if not body.strip():
        continue
    tmp = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                      encoding="utf-8")
    try:
        tmp.write(body)
        tmp.close()
        r = subprocess.run(["node", "--check", tmp.name],
                           capture_output=True, text=True)
    finally:
        os.unlink(tmp.name)

    where = "%s (line %d)" % (name, start) if len(blocks) > 1 else name
    if r.returncode == 0:
        print("%-12s script parses (%d lines%s)"
              % (name, body.count("\n") + 1,
                 ", block at line %d" % start if len(blocks) > 1 else ""))
        continue

    bad = 1
    # node prints `/tmp/xxxx.js:3597` and then quotes the line. Rewrite that to
    # `index.html:4303`, which is where the person reading this has to go.
    #
    # Matched on the temp file's BASENAME with an unconstrained prefix: node
    # resolves symlinks before it reports, so on a Mac the path it prints
    # (/private/var/…) is not the path Python was handed (/var/…) — and a
    # temporary directory is allowed to contain a space, which a `\S*` prefix
    # cannot cross. Getting this match wrong loses the line number, which is
    # the one thing this rewrite exists to produce.
    out = r.stderr or r.stdout
    out = re.sub(r"^.*%s:(\d+)" % re.escape(os.path.basename(tmp.name)),
                 lambda m: "%s:%d" % (name, int(m.group(1)) + start - 1),
                 out, flags=re.M)
    # node's own frames, which are about node and not about this file.
    out = "\n".join(l for l in out.splitlines()
                    if not l.startswith("    at ")
                    and not l.startswith("Node.js v")).strip()
    print("%s: script does NOT parse" % where, file=sys.stderr)
    print(out.rstrip(), file=sys.stderr)

sys.exit(bad)
PY
}

# Compiled in memory rather than through py_compile: this leaves no __pycache__
# behind, so running the check never changes what a deploy would carry.
check_py() {
  python3 - "$DIR/$1" <<'PY' || return 1
import os, sys
path = sys.argv[1]
name = os.path.basename(path)
try:
    src = open(path, encoding="utf-8").read()
except (OSError, UnicodeDecodeError) as e:
    print("%s: cannot be read — %s" % (name, e), file=sys.stderr)
    sys.exit(1)
try:
    compile(src, name, "exec")
except SyntaxError as e:
    print("%s: does NOT compile" % name, file=sys.stderr)
    print("%s:%s: %s" % (name, e.lineno, e.msg), file=sys.stderr)
    if e.text:
        print("    " + e.text.rstrip(), file=sys.stderr)
    sys.exit(1)
print("%-12s compiles (%d lines)" % (name, src.count("\n") + 1))
PY
}

for page in index.html admin.html; do
  check_page "$page" || fail=1
done
# …and that nothing called at LOAD is missing. Parsing proves the script is
# well formed; this proves it gets past its first line. See check_calls.py.
python3 "$DIR/check_calls.py" "$DIR/index.html" "$DIR/admin.html" || fail=1
for mod in serve.py manual.py; do
  check_py "$mod" || fail=1
done

if [ "$fail" -ne 0 ]; then
  echo
  echo "check: FAILED — do not deploy this" >&2
  exit 1
fi
echo
echo "check: everything parses"
