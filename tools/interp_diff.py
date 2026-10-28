#!/usr/bin/env python3
"""Differential evidence for the self-hosted interpreter (selfhost/interp.tn).

    tools/interp_diff.py [TENONC]

Runs every .tn file of the corpus (bootstrap lib tests programs selfhost bench
study) with `tenon run` and `tenonc run`, from the file's directory, with its
`// stdin:` and `// args:` directives (as the test runner gives them), and
compares standard output, standard error and the exit status byte for byte.
Files the bootstrap rejects are compared too (the diagnostic must be the
same). Files the bootstrap needs more than 20 s for are skipped. Prints each
difference and a summary; exit status 1 if any file differs. TENONC defaults
to target/tenonc (./check builds it).
"""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, "target", "release", "tenon")
C = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "target", "tenonc")
TIMEOUT = 20


def directive(src, key):
    for line in src.splitlines()[:3]:
        if line.startswith(f"// {key}:"):
            return line[len(key) + 4:].strip().replace("\\n", "\n")
    return None


def hex_escapes(s):
    b, out, i = s.encode(), bytearray(), 0
    while i < len(b):
        if b[i:i + 2] == b"\\x" and i + 4 <= len(b):
            try:
                out.append(int(b[i + 2:i + 4].decode(), 16))
                i += 4
                continue
            except ValueError:
                pass
        out.append(b[i])
        i += 1
    return bytes(out)


def run(cmd, cwd, stdin):
    try:
        r = subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, timeout=TIMEOUT)
        return (r.stdout, r.stderr, r.returncode)
    except subprocess.TimeoutExpired:
        return None


def one(path):
    src = open(path, errors="replace").read()
    stdin = hex_escapes(directive(src, "stdin") or "")
    args = (directive(src, "args") or "").split()
    d, name = os.path.split(path)
    a = run([T, "run", name] + args, d, stdin)
    if a is None:
        return (path, "skip", "")
    b = run([C, "run", "--root", ROOT, name] + args, d, stdin)
    if b is None:
        return (path, "diff", "tenonc timed out")
    if a == b:
        return (path, "same", "")
    return (path, "diff", f"exit {a[2]} vs {b[2]}\n  tenon  out {a[0][-300:]!r}\n  tenonc out {b[0][-300:]!r}"
                          f"\n  tenon  err {a[1][-300:]!r}\n  tenonc err {b[1][-300:]!r}")


def main():
    files = sorted(os.path.join(d, f) for top in ["bootstrap", "lib", "tests", "programs", "selfhost", "bench", "study"]
                   for d, _, fs in os.walk(os.path.join(ROOT, top)) for f in fs if f.endswith(".tn"))
    # a repro that needs a prepared directory and changes it when run
    files = [f for f in files if not f.endswith("02-fs-symlink-escape.tn")]
    with ThreadPoolExecutor(8) as ex:
        rs = list(ex.map(one, files))
    for path, kind, why in rs:
        if kind == "diff":
            print("DIFF", os.path.relpath(path, ROOT), why)
    count = lambda k: len([r for r in rs if r[1] == k])
    print(f"interp_diff: {count('same')} of {len(rs)} corpus files give the same stdout, stderr and exit status"
          f" under tenon run and tenonc run; {count('diff')} differ; {count('skip')} skipped (tenon run > {TIMEOUT}s)")
    return 1 if count("diff") else 0


if __name__ == "__main__":
    sys.exit(main())
