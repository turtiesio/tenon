#!/usr/bin/env python3
"""The mechanized link (tenon.md §6, formal/README.md "Differential testing"):
the Lean core's evaluator against `tenon run` on the corpus.

    ops/gates/formal_diff.py [--list] [FILE.tn...]

For every corpus program (ops/corpus.py; a file with `fn main` that is not a
`// module`), `tenon ast` dumps it and `tenon-core run` (formal/, the
executable semantics the proofs are about) runs the translated program. A
run the core cannot complete (a construct outside the core, a stuck state,
no fuel left) ends with a `tenon-core:` line and exit status 3: the file is
outside the subset; but if the core is stuck (its dynamic checks of the
obligation and type rules stop it) on a program `tenon check` accepts, that
is a disagreement with the checker. For the others, `tenon run` runs the file from its
directory with its `// stdin:` and `// args:` directives, and standard output
and the exit status must be the same. Prints each disagreement and the
coverage; writes .evidence/formal_diff.json (`corpus.record`); exit status 1
if any file disagrees or gets stuck. `--list` also prints the files in the subset. Builds
formal/ with `lake build` first when TENON_CORE is not set (the Lean
toolchain: formal/lean-toolchain). Each disagreement is a finding
(tests/redteam/FINDINGS-*-formal.md).
"""
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ops/: corpus.py
import corpus

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TIMEOUT = 20
CORE = os.environ.get("TENON_CORE") or os.path.join(ROOT, "formal", ".lake", "build", "bin", "tenon-core")


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


def big_stack():
    import resource
    _, hard = resource.getrlimit(resource.RLIMIT_STACK)
    want = 512 << 20 if hard == resource.RLIM_INFINITY else min(hard, 512 << 20)
    try:
        resource.setrlimit(resource.RLIMIT_STACK, (want, hard))
    except (ValueError, OSError):
        pass


def run(cmd, cwd, stdin=b"", timeout=TIMEOUT, pre=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, timeout=timeout, preexec_fn=pre)
        return (r.stdout, r.stderr, r.returncode)
    except subprocess.TimeoutExpired:
        return None


def lake():
    for c in [shutil.which("lake"), os.path.expanduser("~/.elan/bin/lake")]:
        if c and os.path.exists(c):
            return c
    return None


def is_program(rel):
    src = open(os.path.join(ROOT, rel), errors="replace").read()
    return "fn main(" in src and not src.startswith("// module")


def one(job):
    rel, preludes, tmp = job
    path = os.path.join(ROOT, rel)
    src = open(path, errors="replace").read()
    stdin = hex_escapes(directive(src, "stdin") or "")
    args = (directive(src, "args") or "").split()
    dump = os.path.join(tmp, rel.replace("/", "__") + ".ast")
    a = run([corpus.TENON, "ast", path], ROOT)
    if a is None or a[2] != 0 or a[0].startswith(b"error "):
        return (rel, "outside", "tenon ast failed")
    with open(dump, "wb") as f:
        f.write(a[0])
    chk = run([corpus.TENON, "check", "--root", ROOT, path], ROOT)
    if chk is None or chk[2] != 0:
        return (rel, "outside", "rejected by tenon check")
    core = run([CORE, "run", *preludes, "--", dump, *args], os.path.dirname(path), stdin, pre=big_stack)
    if core is None:
        return (rel, "outside", "tenon-core timed out")
    if core[2] < 0 or b"Stack overflow detected" in core[1]:
        return (rel, "outside", "tenon-core ran out of stack")
    if core[2] == 3 and b"tenon-core: " in core[1]:
        why = core[1].decode(errors="replace").split("tenon-core: ", 1)[1].strip().splitlines()[0]
        # the checker accepted it, but the core's semantics stops it: an obligation
        # copied, dropped or used after a move, or a type error at run time
        return (rel, "monitor" if why.startswith("stuck") else "outside", why)
    ref = run([corpus.TENON, "run", "--root", ROOT, os.path.basename(path), *args], os.path.dirname(path), stdin)
    if ref is None:
        return (rel, "outside", "tenon run timed out")
    if (ref[0], ref[2]) == (core[0], core[2]):
        return (rel, "same", "")
    return (rel, "diff", f"exit {ref[2]} (tenon run) vs {core[2]} (core)\n  tenon run out {ref[0][-400:]!r}\n"
                         f"  core      out {core[0][-400:]!r}\n  tenon run err {ref[1][-300:]!r}\n  core      err {core[1][-300:]!r}")


def main():
    argv = sys.argv[1:]
    listing = "--list" in argv
    files = [a for a in argv if a != "--list"]
    if not os.environ.get("TENON_CORE"):
        lk = lake()
        if not lk:
            print("formal_diff: no Lean toolchain (lake); install elan (formal/README.md)")
            return 1
        b = subprocess.run([lk, "build", "tenon-core"], cwd=os.path.join(ROOT, "formal"), capture_output=True, text=True)
        if b.returncode != 0:
            print(b.stdout[-2000:], b.stderr[-2000:])
            print("formal_diff: lake build failed")
            return 1
    rels = [os.path.relpath(os.path.abspath(f), ROOT) for f in files] if files else \
        [f for f in corpus.files() if is_program(f)]
    with tempfile.TemporaryDirectory() as tmp:
        preludes = []
        for p in ["lib/prelude.tn", "lib/v2/prelude.tn"]:
            d = os.path.join(tmp, p.replace("/", "__") + ".ast")
            r = run([corpus.TENON, "ast", os.path.join(ROOT, p)], ROOT)
            if r is None or r[2] != 0:
                print(f"formal_diff: tenon ast {p} failed")
                return 1
            with open(d, "wb") as f:
                f.write(r[0])
            preludes.append(d)
        with ThreadPoolExecutor(corpus.JOBS) as ex:
            rs = list(ex.map(one, [(r, preludes, tmp) for r in rels]))
    count = lambda k: len([r for r in rs if r[1] == k])
    for rel, kind, why in rs:
        if kind == "diff":
            print("DIFF", rel, why)
        elif kind == "monitor":
            print("STUCK", rel, why)
        elif listing and kind == "same":
            print("SAME", rel)
        elif listing and kind == "outside":
            print("OUTSIDE", rel, why)
    reasons = {}
    for _, kind, why in rs:
        if kind == "outside":
            key = why.split(":")[0] if why.startswith(("unsupported", "stuck")) else why
            reasons[key] = reasons.get(key, 0) + 1
    inside = count("same") + count("diff") + count("monitor")
    print("formal_diff: outside the subset: " + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])))
    print(f"formal_diff: {inside} of {len(rs)} corpus programs are in the core's subset; "
          f"{count('same')} agree with tenon run (stdout and exit status), {count('diff')} disagree; "
          f"on {count('monitor')} that tenon check accepts the core's semantics gets stuck")
    if not files:
        corpus.record("formal_diff", {"programs": len(rs), "subset": inside, "same": count("same"), "diff": count("diff"),
                                      "stuck": count("monitor"),
                                      "differ": [r for r, k, _ in rs if k == "diff"],
                                      "stuck_files": [r for r, k, _ in rs if k == "monitor"],
                                      "subset_files": [r for r, k, _ in rs if k != "outside"]})
    return 1 if count("diff") or count("monitor") else 0


if __name__ == "__main__":
    sys.exit(main())
