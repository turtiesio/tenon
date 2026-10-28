#!/usr/bin/env python3
"""Doc-snippet check: every whole program in the docs must compile.

Extracts each ```tenon block of the user docs (README.md and docs/*.md:
reference, quickstart, library, tools, packages) that contains `fn main`, writes it to a temporary file and runs `tenon check` on
it ($TENON, default target/tenon: the self-hosted compiler, so the docs may
show v2 features such as traits). Blocks without `fn main` are fragments and
are skipped. Std modules (`import regex`) are found by the compiler as usual.

Conventions for doc authors:
  ```tenon        a code block; checked when it contains `fn main`
  ```tenon-error  a deliberate error example; never checked
A fence may be indented (inside a list item); the indentation is removed.

Reports each failing block with its line number in the doc; exit status 1 if
any block fails. Usage: tools/doctest.py [DOC...]
"""
import glob
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

import corpus

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TENON = corpus.TENON
DOCS = ["README.md"] + sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "docs", "*.md")))
FENCE = re.compile(r"^(\s*)```(\S*)\s*$")


def blocks(path):
    """Yield (line number of the opening fence, info string, code)."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    i = 0
    while i < len(lines):
        m = FENCE.match(lines[i])
        if not m or not m.group(2):
            i += 1
            continue
        indent, info, start = m.group(1), m.group(2), i + 1
        body = []
        i += 1
        while i < len(lines) and not FENCE.match(lines[i]):
            line = lines[i]
            body.append(line[len(indent):] if line.startswith(indent) else line.lstrip())
            i += 1
        i += 1  # closing fence
        yield start, info, "\n".join(body) + "\n"


def check(tmp, doc, line, code):
    name = os.path.join(tmp, "%s_%d.tn" % (os.path.basename(doc).replace(".", "_"), line))
    with open(name, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([TENON, "check", name], capture_output=True, text=True)
    if r.returncode == 0:
        return None
    # report positions as doc lines: line L of the block is doc line `line + L`
    msg = re.sub(re.escape(name) + r":(\d+):",
                 lambda m: "%s:%d:" % (doc, line + int(m.group(1))), r.stderr + r.stdout)
    return "FAIL %s:%d: the code block does not compile\n%s" % (doc, line, msg.rstrip())


def main():
    docs = sys.argv[1:] or DOCS
    jobs = []
    for doc in docs:
        for line, info, code in blocks(os.path.join(ROOT, doc)):
            if info == "tenon" and re.search(r"\bfn main\b", code):
                jobs.append((doc, line, code))
    with tempfile.TemporaryDirectory() as tmp:
        with ThreadPoolExecutor(max_workers=corpus.JOBS) as ex:
            results = list(ex.map(lambda j: check(tmp, *j), jobs))
    failed = [r for r in results if r]
    for r in failed:
        print(r)
    print("doctest: %d doc program(s) checked, %d failed" % (len(jobs), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
