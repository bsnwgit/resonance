#!/usr/bin/env python3
"""Top-level calls to names a page never defines.

A SCRIPT THAT PARSES CAN STILL BE DEAD ON ARRIVAL, and check.sh only proves it
parses. Three faults in one day got past it: a call to a helper that exists in
the OTHER page, a stray decorator that landed on the next function down, and a
selector that matched nothing. Only the first is findable statically, and this
is that check.

TOP LEVEL ONLY, deliberately. A call inside a function is resolved when the
function runs, so a missing name there breaks one feature. A call out here runs
at load, throws before anything is wired up, and takes the whole page with it —
which does not present as a broken feature. It presents as several unrelated
parts of the interface being absent at once.

Checking further than this was tried and dropped: matching every call in the
file flags object-literal methods, callback parameters and the word "endpoint"
inside a string, and a check people learn to ignore is worse than no check.
"""
import io
import os
import re
import sys

KEYWORD = {"if", "for", "while", "switch", "catch", "return", "typeof",
           "function", "new", "delete", "void"}


def undefined_top_level_calls(path):
    src = io.open(path, encoding="utf-8").read()
    body = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", src, re.S))
    body = re.sub(r"/\*.*?\*/", " ", body, flags=re.S)
    body = re.sub(r"(?<![:\w])//[^\n]*", " ", body)
    known = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)", body))
    known |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)", body))
    depth, bad = 0, []
    for n, line in enumerate(body.split("\n"), 1):
        if depth == 0:
            for name in re.findall(r"^\s*([A-Za-z_$][\w$]*)\s*\(", line):
                if name not in known and name not in KEYWORD:
                    bad.append((n, name, line.strip()[:64]))
        depth = max(0, depth + line.count("{") + line.count("(")
                    - line.count("}") - line.count(")"))
    return bad


def main(argv):
    failed = False
    for path in argv[1:]:
        bad = undefined_top_level_calls(path)
        if bad:
            failed = True
            print("%s: top-level call to a name this page never defines"
                  % os.path.basename(path), file=sys.stderr)
            for n, name, line in bad:
                print("    %s(...)  — %s" % (name, line), file=sys.stderr)
        else:
            print("%-12s no undefined top-level calls"
                  % os.path.basename(path))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
