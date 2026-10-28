#!/usr/bin/env python3
"""Differential evidence for the self-hosted interpreter (selfhost/interp.tn).

    tools/interp_diff.py [TENON]

Runs every .tn file of the corpus (tools/corpus.py, without v2/: the seed
cannot read those) with `tenon-seed run` (the seed's interpreter) and `tenon run`
(tools/evidence.sh), from the file's directory, with its
`// stdin:` and `// args:` directives (as the test runner gives them), and
compares standard output, standard error and the exit status byte for byte.
Files the bootstrap rejects are compared too (the diagnostic must be the
same). Files the bootstrap needs more than 20 s for are skipped; tenon may
take three times as long as the bootstrap (at least 20 s). Prints each
difference and a summary; exit status 1 if any file differs. TENON defaults
to $TENON, else target/tenon (./check builds it); the seed is $SEED.
"""
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import corpus

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = corpus.SEED
C = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else corpus.TENON
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


def run(cmd, cwd, stdin, timeout=TIMEOUT):
    try:
        r = subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, timeout=timeout)
        return (r.stdout, r.stderr, r.returncode)
    except subprocess.TimeoutExpired:
        return None


def one(path):
    src = open(path, errors="replace").read()
    stdin = hex_escapes(directive(src, "stdin") or "")
    args = (directive(src, "args") or "").split()
    d, name = os.path.split(path)
    start = time.time()
    a = run([T, "run", name] + args, d, stdin)
    if a is None:
        return (path, "skip", "")
    # tenon gets three times the bootstrap's time (at least TIMEOUT)
    b = run([C, "run", "--root", ROOT, name] + args, d, stdin, max(TIMEOUT, 3 * (time.time() - start)))
    if b is None:
        return (path, "diff", "tenon timed out")
    if a == b:
        return (path, "same", "")
    return (path, "diff", f"exit {a[2]} vs {b[2]}\n  seed  out {a[0][-300:]!r}\n  tenon out {b[0][-300:]!r}"
                          f"\n  seed  err {a[1][-300:]!r}\n  tenon err {b[1][-300:]!r}")


def main():
    # a repro that needs a prepared directory and changes it when run
    files = [os.path.join(ROOT, f) for f in corpus.files(no_v2=True) if not f.endswith("02-fs-symlink-escape.tn")]
    with ThreadPoolExecutor(corpus.JOBS) as ex:
        rs = list(ex.map(one, files))
    for path, kind, why in rs:
        if kind == "diff":
            print("DIFF", os.path.relpath(path, ROOT), why)
    count = lambda k: len([r for r in rs if r[1] == k])
    print(f"interp_diff: {count('same')} of {len(rs)} corpus files give the same stdout, stderr and exit status"
          f" under tenon-seed run and tenon run; {count('diff')} differ; {count('skip')} skipped (tenon-seed run > {TIMEOUT}s)")
    corpus.record("interp_diff", {"files": len(rs), "same": count("same"), "diff": count("diff"), "skipped": count("skip"),
                                  "differ": [os.path.relpath(p, ROOT) for p, k, _ in rs if k == "diff"]})
    return 1 if count("diff") else 0


if __name__ == "__main__":
    sys.exit(main())
