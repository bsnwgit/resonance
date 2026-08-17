"""Documentation: the registry, and a PDF writer that owes nothing to anybody.

The visualiser's rule is that it carries no runtime dependency, and the
documentation is not a good enough reason to break it. So the PDF here is
written by hand against the format rather than by importing reportlab or
shelling out to a converter that may or may not exist on the box.

That sounds worse than it is, because of one decision: everything is set in
Courier. The base-14 fonts need no embedding, and a monospaced face means the
width of a string is exactly len(s) * 0.6 * size — no font-metric tables, no
kerning, and line wrapping that is correct by construction rather than by
approximation. It also happens to be what the interface itself is set in, so
the printed page looks like the thing it documents.
"""

import os
import re
import time

DOC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")

# Ordered: the reading order somebody new should take, not alphabetical.
# `audience` drives the tag in the list — a viewer signing in should be able to
# tell at a glance which of these are about the screen and which are about the
# panel they are looking at.
#
# `category` is the shelf it sits on. A reading order is right for somebody new
# and useless for somebody who has come looking for one thing, so the page
# groups by this and keeps the reading order inside each group. Categories are
# discovered from the entries below rather than declared in a list of their
# own: two places to edit is one place to forget.
DOCS = [
    {"id": "using",   "file": "using-resonance.md",
     "category": "Using it",
     "title": "Using Resonance",       "audience": "everyone",
     "summary": "Talking to the display: wake words, the three input modes, "
                "and what it remembers."},
    {"id": "admin",   "file": "administration.md",
     "category": "Administration",
     "title": "Administration",        "audience": "admin",
     "summary": "Signing in, how the panel is laid out, saving and reverting, "
                "the live preview, approving the displays that may use each "
                "assistant, and keeping a screen nobody touches working."},
    {"id": "look",    "file": "appearance.md",
     "category": "The display",
     "title": "Appearance & geometry", "audience": "admin",
     "summary": "The palette, layout and glass, the figure and how it "
                "moves, and what each control does."},
    {"id": "speech",  "file": "speech.md",
     "category": "The display",
     "title": "Speech in & out",       "audience": "admin",
     "summary": "Transcription models, voices, wake and sleep words, what the "
                "display's status line is telling you, and why HTTPS is not "
                "optional."},
    {"id": "backend", "file": "assistant.md",
     "category": "Assistants & integration",
     "title": "Assistants", "audience": "admin",
     "summary": "One display, several assistants: the name you say to reach "
                "each, what a browser is told about them, and the services "
                "behind them — models, hosted providers, and Home Assistant."},
    {"id": "app",     "file": "app-settings.md",
     "category": "Administration",
     "title": "Admin settings & accounts", "audience": "admin",
     "summary": "Ports, restarts, session lifetime, keeping unattended screens "
                "up, and the two roles."},
    {"id": "embed",   "file": "embedding.md",
     "category": "Assistants & integration",
     "title": "Embedding it elsewhere", "audience": "admin",
     "summary": "Embed keys, the two axes an integrator has to keep apart, "
                "and the three steps a host application takes."},
]
DOC_BY_ID = {d["id"]: d for d in DOCS}


def read_doc(doc_id):
    """Returns markdown text, or None. The id is looked up in the registry
    rather than joined onto a path, so nothing a browser sends can reach a
    file that is not on this list."""
    entry = DOC_BY_ID.get(doc_id)
    if not entry:
        return None
    try:
        with open(os.path.join(DOC_DIR, entry["file"]), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def doc_index():
    return [{k: d[k] for k in ("id", "title", "audience", "summary", "category")}
            for d in DOCS if read_doc(d["id"]) is not None]


#: How many lines of one document come back before the rest are counted rather
#: than listed. A search that returns four hundred lines from one file is a
#: file, not an answer — and the count of what was left is reported, because a
#: cap nobody is told about reads as "that is all there is".
SEARCH_PER_DOC = 8
#: Below this, a search matches most of the English language and would hand
#: back every document in full, which reads as the thing being broken.
SEARCH_MIN = 2


def _snippet(line, needle, width=170):
    """One matched line, cut to something that fits a row — with the match
    kept inside the cut. Trimming to the first N characters of a paragraph
    that matched on its last word shows somebody a line with nothing in it."""
    text = re.sub(r"\s+", " ", line).strip()
    # Markdown that means nothing once the line is out of its document.
    text = re.sub(r"[*_`]+", "", text).strip()
    if len(text) <= width:
        return text
    i = text.lower().find(needle)
    if i < 0:
        return text[:width].rstrip() + "…"
    start = max(0, i - width // 3)
    end = min(len(text), start + width)
    return (("…" if start else "") + text[start:end].strip()
            + ("…" if end < len(text) else ""))


def search(q, per_doc=SEARCH_PER_DOC):
    """Every document, line by line, for a plain substring.

    No index and no ranking. Seven files is a grep, and an index would be one
    more thing to keep in step with them for a gain nobody could measure on a
    corpus this size.

    What a hit carries is the heading it sits under, because *which document*
    is only half of what somebody searching needs — one of six mentions is the
    one they want, and the heading is what tells them which before they open
    anything.
    """
    needle = str(q or "").strip().lower()
    if len(needle) < SEARCH_MIN:
        return []
    out = []
    for d in DOCS:
        body = read_doc(d["id"])
        if body is None:
            continue
        heading, hits, fenced = "", [], False
        for line in body.split("\n"):
            stripped = line.strip()
            # Inside a fence the text is a command or a payload, and matching
            # "user" against a JSON key sends somebody to a line that cannot
            # answer them. The fence markers themselves are never content.
            if stripped.startswith("```"):
                fenced = not fenced
                continue
            head = re.match(r"#{1,6}\s+(.*)", stripped)
            if head:
                heading = head.group(1).strip().rstrip("#").strip()
            if fenced or not stripped:
                continue
            if needle in stripped.lower():
                hits.append({"heading": heading,
                             "text": _snippet(stripped, needle)})
        if hits:
            out.append({"id": d["id"], "title": d["title"],
                        "category": d["category"],
                        "total": len(hits), "hits": hits[:per_doc]})
    return out


# ------------------------------------------------------------------ encoding
# Courier's built-in encoding is WinAnsi, which covers Latin-1 plus the
# punctuation this project's prose actually uses — em dashes and curly quotes,
# mostly. Anything outside it is transliterated rather than dropped, because a
# missing arrow in a sentence about arrows is worse than an ASCII one.
_WIN = {
    "—": "\x97", "–": "\x96", "‘": "\x91", "’": "\x92",
    "“": "\x93", "”": "\x94", "…": "\x85", "•": "\x95",
    "·": "\xb7", " ": " ",
}
_ASCII = {
    "→": "->", "←": "<-", "⇒": "=>", "✓": "[x]",
    "✗": "[ ]", "≤": "<=", "≥": ">=", "×": "x",
    "⌠": "|", "∞": "inf", "⌘": "Cmd", "⇧": "Shift",
}


def _wa(s):
    for k, v in _ASCII.items():
        s = s.replace(k, v)
    for k, v in _WIN.items():
        s = s.replace(k, v)
    # anything still non-Latin-1 would break the byte encoding below
    return "".join(c if ord(c) < 256 else "?" for c in s)


def _esc(s):
    return _wa(s).replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


# -------------------------------------------------------------------- layout
PAGE_W, PAGE_H = 612.0, 792.0          # US Letter, in points
MARGIN_X, MARGIN_TOP, MARGIN_BOT = 56.0, 62.0, 56.0
BODY_SIZE, BODY_LEAD = 9.0, 12.6
CODE_SIZE, CODE_LEAD = 8.0, 11.0
CHAR_W = 0.6                            # Courier advance, as a fraction of size
FONT_R, FONT_B, FONT_I = "/F1", "/F2", "/F3"

H_STYLE = {1: (15.0, 21.0, FONT_B, 16.0, 8.0),
           2: (11.5, 16.0, FONT_B, 14.0, 6.0),
           3: (9.5, 13.5, FONT_B, 10.0, 4.0)}   # size, lead, font, above, below


def _cols(size):
    return max(20, int((PAGE_W - 2 * MARGIN_X) / (size * CHAR_W)))


def _wrap(text, width):
    """Greedy wrap. A word longer than the line — a URL, usually — is broken
    rather than allowed to run off the page."""
    out, line = [], ""
    for word in text.split():
        while len(word) > width:
            if line:
                out.append(line); line = ""
            out.append(word[:width]); word = word[width:]
        if not line:
            line = word
        elif len(line) + 1 + len(word) <= width:
            line += " " + word
        else:
            out.append(line); line = word
    if line or not out:
        out.append(line)
    return out


_INLINE = (
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), ""),            # images: drop
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), r"\1 (\2)"),  # links: keep both
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),
    (re.compile(r"(?<!\w)\*([^*]+)\*(?!\w)"), r"\1"),
    (re.compile(r"`([^`]+)`"), r"\1"),
)


def _inline(s):
    for pat, rep in _INLINE:
        s = pat.sub(rep, s)
    return s


def _blocks(md):
    """Markdown subset -> a flat list of (kind, payload) laid out in order.

    Only what the documentation actually uses. An unsupported construct falls
    through to a paragraph, which degrades to readable rather than to wrong."""
    out, para, code, fence = [], [], [], False
    rows = []

    def flush_para():
        if para:
            out.append(("p", " ".join(para))); para.clear()

    def flush_table():
        if rows:
            out.append(("table", list(rows))); rows.clear()

    for raw in md.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if line.strip().startswith("```"):
            if fence:
                out.append(("code", list(code))); code.clear()
            else:
                flush_para(); flush_table()
            fence = not fence
            continue
        if fence:
            code.append(line)
            continue
        if not line.strip():
            flush_para(); flush_table()
            continue
        if line.lstrip().startswith("|") and line.rstrip().endswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # the |---|---| separator carries no content
            if not all(set(c) <= set("-: ") and c for c in cells):
                flush_para()
                rows.append([_inline(c) for c in cells])
            continue
        flush_table()
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para()
            out.append(("h", (min(3, len(m.group(1))), _inline(m.group(2)))))
            continue
        if re.match(r"^\s*([-*_])\1{2,}\s*$", line):
            flush_para(); out.append(("hr", None)); continue
        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            flush_para()
            out.append(("li", (len(m.group(1)) // 2, "•", _inline(m.group(2)))))
            continue
        m = re.match(r"^(\s*)(\d+)[.)]\s+(.*)$", line)
        if m:
            flush_para()
            out.append(("li", (len(m.group(1)) // 2, m.group(2) + ".",
                               _inline(m.group(3)))))
            continue
        if line.startswith("> "):
            flush_para(); out.append(("quote", _inline(line[2:]))); continue
        para.append(_inline(line.strip()))
    flush_para(); flush_table()
    if fence and code:
        out.append(("code", code))
    return out


class _Page:
    def __init__(self):
        self.ops = []

    def text(self, x, y, size, font, s):
        self.ops.append("BT %s %.1f Tf %.1f %.1f Td (%s) Tj ET"
                        % (font, size, x, y, _esc(s)))

    def rule(self, y, x0, x1, grey=0.72, w=0.5):
        self.ops.append("q %.2f G %.2f w %.1f %.1f m %.1f %.1f l S Q"
                        % (grey, w, x0, y, x1, y))

    def box(self, x, y, w, h, grey=0.94):
        self.ops.append("q %.2f g %.1f %.1f %.1f %.1f re f Q" % (grey, x, y, w, h))


def _lay_out(title, subtitle, blocks):
    pages, page = [], _Page()
    y = PAGE_H - MARGIN_TOP
    bottom = MARGIN_BOT + 18            # leave room for the footer

    def new_page():
        nonlocal page, y
        pages.append(page)
        page = _Page()
        y = PAGE_H - MARGIN_TOP

    def need(h):
        if y - h < bottom:
            new_page()

    # masthead, first page only
    page.text(MARGIN_X, y, 17.0, FONT_B, title)
    y -= 21
    if subtitle:
        page.text(MARGIN_X, y, 8.5, FONT_I, subtitle)
        y -= 11
    page.rule(y, MARGIN_X, PAGE_W - MARGIN_X, grey=0.55, w=0.8)
    y -= 20

    # The masthead already carries the title, so the document's own opening H1
    # would print it twice. The markdown keeps its H1 — it has to stand alone
    # when read as a file — and this drops it at render time instead.
    if blocks and blocks[0][0] == "h" and blocks[0][1][0] == 1:
        blocks = blocks[1:]

    for kind, payload in blocks:
        if kind == "h":
            level, text = payload
            size, lead, font, above, below = H_STYLE[level]
            need(above + lead + below + 6)
            y -= above
            for ln in _wrap(text, _cols(size)):
                page.text(MARGIN_X, y, size, font, ln)
                y -= lead
            if level <= 2:
                page.rule(y + lead - 4, MARGIN_X, PAGE_W - MARGIN_X,
                          grey=0.80 if level == 2 else 0.6)
            y -= below

        elif kind == "p":
            lines = _wrap(payload, _cols(BODY_SIZE))
            for ln in lines:
                need(BODY_LEAD)
                page.text(MARGIN_X, y, BODY_SIZE, FONT_R, ln)
                y -= BODY_LEAD
            y -= 4

        elif kind == "li":
            depth, marker, text = payload
            ind = MARGIN_X + depth * 14
            hang = len(marker) + 1
            width = _cols(BODY_SIZE) - depth * 2 - hang
            for i, ln in enumerate(_wrap(text, max(20, width))):
                need(BODY_LEAD)
                if i == 0:
                    page.text(ind, y, BODY_SIZE, FONT_R, marker)
                page.text(ind + hang * BODY_SIZE * CHAR_W, y,
                          BODY_SIZE, FONT_R, ln)
                y -= BODY_LEAD
            y -= 1.5

        elif kind == "quote":
            for ln in _wrap(payload, _cols(BODY_SIZE) - 4):
                need(BODY_LEAD)
                page.rule(y + 2, MARGIN_X, MARGIN_X, grey=0.6)   # dot of a rule
                page.text(MARGIN_X + 12, y, BODY_SIZE, FONT_I, ln)
                y -= BODY_LEAD
            y -= 4

        elif kind == "code":
            lines = payload or [""]
            need(min(len(lines), 6) * CODE_LEAD + 10)
            for ln in lines:
                if y - CODE_LEAD < bottom:
                    new_page()
                page.box(MARGIN_X - 4, y - 3, PAGE_W - 2 * MARGIN_X + 8,
                         CODE_LEAD)
                for seg in _wrap(ln, _cols(CODE_SIZE)) if ln.strip() else [""]:
                    page.text(MARGIN_X, y, CODE_SIZE, FONT_R, seg)
                y -= CODE_LEAD
            y -= 6

        elif kind == "table":
            rows = payload
            n = max(len(r) for r in rows)
            rows = [r + [""] * (n - len(r)) for r in rows]
            widths = [max(len(r[i]) for r in rows) for i in range(n)]
            total = sum(widths) + 3 * (n - 1)
            avail = _cols(CODE_SIZE)
            if total > avail:                    # squeeze the widest column
                over = total - avail
                widest = widths.index(max(widths))
                widths[widest] = max(8, widths[widest] - over)
            for ri, r in enumerate(rows):
                # a cell may need more than one line; the row is as tall as
                # its tallest cell, which is what keeps columns aligned
                cells = [_wrap(r[i], widths[i]) for i in range(n)]
                height = max(len(c) for c in cells)
                need(height * CODE_LEAD + 4)
                for li in range(height):
                    parts = [(cells[i][li] if li < len(cells[i]) else "")
                             .ljust(widths[i]) for i in range(n)]
                    page.text(MARGIN_X, y, CODE_SIZE,
                              FONT_B if ri == 0 else FONT_R, "   ".join(parts))
                    y -= CODE_LEAD
                if ri == 0:
                    page.rule(y + CODE_LEAD - 3, MARGIN_X, PAGE_W - MARGIN_X,
                              grey=0.7)
                    y -= 2
            y -= 6

        elif kind == "hr":
            need(14)
            y -= 6
            page.rule(y, MARGIN_X, PAGE_W - MARGIN_X, grey=0.82)
            y -= 10

    pages.append(page)

    stamp = time.strftime("%Y-%m-%d")
    for i, p in enumerate(pages, 1):
        p.rule(MARGIN_BOT + 8, MARGIN_X, PAGE_W - MARGIN_X, grey=0.85)
        p.text(MARGIN_X, MARGIN_BOT - 4, 7.5, FONT_R,
               "Resonance · %s · %s" % (title, stamp))
        foot = "%d / %d" % (i, len(pages))
        p.text(PAGE_W - MARGIN_X - len(foot) * 7.5 * CHAR_W,
               MARGIN_BOT - 4, 7.5, FONT_R, foot)
    return pages


def render_pdf(title, markdown, subtitle=""):
    """A complete PDF 1.4 file as bytes. Objects are emitted in order and the
    xref is built from the byte offsets as we go, which is the whole trick."""
    pages = _lay_out(title, subtitle, _blocks(markdown))
    n_pages = len(pages)

    # 1 catalog, 2 pages tree, 3..5 fonts, then per page: page obj + stream
    first_page_obj = 6
    kids = " ".join("%d 0 R" % (first_page_obj + 2 * i) for i in range(n_pages))

    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Count %d /Kids [%s] >>" % (n_pages, kids),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Courier "
        "/Encoding /WinAnsiEncoding >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold "
        "/Encoding /WinAnsiEncoding >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Oblique "
        "/Encoding /WinAnsiEncoding >>",
    ]
    streams = {}
    for i, p in enumerate(pages):
        pid = first_page_obj + 2 * i
        objs.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.0f %.0f] "
            "/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
            "/Contents %d 0 R >>" % (PAGE_W, PAGE_H, pid + 1))
        body = "\n".join(p.ops).encode("latin-1", "replace")
        objs.append(None)                     # placeholder for the stream obj
        streams[len(objs) - 1] = body

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for idx, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % idx
        if obj is None:
            body = streams[idx - 1]
            out += b"<< /Length %d >>\nstream\n" % len(body)
            out += body + b"\nendstream\n"
        else:
            out += obj.encode("latin-1", "replace") + b"\n"
        out += b"endobj\n"

    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root 1 0 R /Info << /Title (%s) "
            b"/Producer (Resonance) >> >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objs) + 1, _esc(title).encode("latin-1", "replace"), xref))
    return bytes(out)
