#!/usr/bin/env python3
"""The mechanized link (tenon.md §6, formal/README.md "Differential testing"):
the Lean core's evaluator against `tenon run`, and the Lean checker against
`tenon check`, on the corpus.

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
and the exit status must be the same.

The checker comparison: every program (accepted or rejected by `tenon
check`, tests/reject and tests/v2/reject included) also goes through
`tenon-core check`, the checker proved sound in Lean (formal/TenonCore/Check.lean,
CheckSound.lean). Its verdict (accepted, rejected, or unsupported: outside the
checker's subset) is compared with `tenon check`'s, and each disagreement is
classified (`lean_class`, `tenon_class`): a program tenon accepts and Lean
rejects is the model being too strict, or, if the core gets stuck on it, the
compiler being unsound (a finding); a program tenon rejects and Lean accepts
breaks a rule the core does not need for its guarantees (a language rule
outside the model, by design) or is a finding (the compiler too strict). A
program Lean accepts is run on the core: by `checked_program_never_stuck` it
is never stuck (assuming the builtins respect their signatures), which the
run confirms. Prints each disagreement and the
coverage; writes .evidence/formal_diff.json (`corpus.record`); exit status 1
if any file disagrees, gets stuck, or is accepted by the Lean checker and
stuck in the core. `--list` also prints the files in the subset. Builds
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


# Why the Lean checker rejects what tenon accepts (the model is too strict there).
LEAN_CLASSES = [
    (r"cannot infer|no method Unit\.|annotated type|builtin %map", "type inference (the checker infers types locally)"),
    (r"passed by ref or mut", "linear or unique values passed by ref or mut"),
    (r"list elements of different types|dyn ", "dyn types (not in the checker)"),
    (r"too many instances", "polymorphic recursion (monomorphized, as tenon build does)"),
    (r"pattern does not fit", "or-patterns binding names in different orders"),
    (r"while a linear value is held", "an early exit next to a linear temporary"),
]
# Why tenon rejects what the Lean checker accepts: a rule the core does not need.
TENON_CLASSES = [
    (r"encode|decode|codec", "derived traits (==, hash, encode, Show) on functions, capabilities, dyn, Float keys"),
    (r"a 'dyn' value", "dyn values (the core passes the value itself)"),
    (r"format spec .* applies to", "trait declarations and bounds (impls are checked for coherence only)"),
    (r"not exhaustive|unreachable pattern|always matches|needs a pattern|loop variables need|must end with|block of",
     "exhaustiveness and pattern rules (the core traps on a missing case)"),
    (r"names start with|written in capi|reserved for|already defined|duplicate|shadows|given twice|already def",
     "naming, duplicates and shadowing"),
    (r"cannot be compared|cannot encode|cannot be converted|does not implement|cannot be a|derived structurally|cannot be used with",
     "derived traits (==, hash, encode, Show) on functions, capabilities, dyn, Float keys"),
    (r"this parameter is|arguments refer to|marks an argument|mutates its receiver|is not mutable|only defined",
     "mutability and mut markers (the core copies in and out)"),
    (r"constant", "constants (each use evaluates again)"),
    (r"impl|trait|bound|type parameter|Self", "trait declarations and bounds (impls are checked for coherence only)"),
    (r"contains itself", "recursive types"),
    (r"linear|unique|may copy or|cannot bind", "linearity rules stricter than the model needs"),
    (r"'main'|methods of 'Sys'", "main's signature"),
    (r"module|can only be defined in", "modules"),
    (r"type mismatch|unknown name|unknown type|missing field|no fiel|expects|holds|returns", "type errors in generic code not instantiated"),
]


def classify(table, msg, src=""):
    import re
    for pat, name in table:
        if re.search(pat, msg) or (pat == r"list elements of different types|dyn " and "dyn " in src
                                   and "different types" in msg):
            return name
    return "other (reviewed by hand: formal/README.md)"


def lean_check(dump, preludes):
    r = run([CORE, "check", *preludes, "--", dump], ROOT, timeout=60)
    if r is None:
        return "unsupported", "the checker timed out"
    out = r[0].decode(errors="replace").strip()
    status, _, why = out.partition(": ")
    if status not in ("accepted", "rejected", "unsupported"):
        return "unsupported", out[:200] or r[1].decode(errors="replace")[:200]
    return status, why


def one(job):
    rel, preludes, tmp = job
    path = os.path.join(ROOT, rel)
    src = open(path, errors="replace").read()
    dump = os.path.join(tmp, rel.replace("/", "__") + ".ast")
    a = run([corpus.TENON, "ast", path], ROOT)
    if a is None or a[2] != 0 or a[0].startswith(b"error "):
        return {"rel": rel, "kind": "outside", "why": "tenon ast failed", "tenon": None, "lean": "unsupported",
                "lmsg": "tenon ast failed"}
    with open(dump, "wb") as f:
        f.write(a[0])
    chk = run([corpus.TENON, "check", "--root", ROOT, path], ROOT)
    t_ok = chk is not None and chk[2] == 0
    tmsg = "" if chk is None else (chk[0] + chk[1]).decode(errors="replace").strip()
    tmsg = tmsg.splitlines()[0] if tmsg else ""
    lean, lmsg = lean_check(dump, preludes)
    kind, why = run_core(rel, path, src, dump, preludes, t_ok, lean == "accepted")
    r = {"rel": rel, "kind": kind, "why": why, "tenon": t_ok, "tmsg": tmsg, "lean": lean, "lmsg": lmsg}
    if t_ok and lean == "rejected":
        r["lean_class"] = "compiler unsound" if kind == "monitor" else classify(LEAN_CLASSES, lmsg, src)
    if not t_ok and lean == "accepted":
        r["tenon_class"] = classify(TENON_CLASSES, tmsg)
    return r


def run_core(rel, path, src, dump, preludes, t_ok, lean_ok):
    """Run the program on the core (and on `tenon run` when tenon accepts it)."""
    if not t_ok and not lean_ok:
        return "outside", "rejected by tenon check"
    stdin = hex_escapes(directive(src, "stdin") or "")
    args = (directive(src, "args") or "").split()
    core = run([CORE, "run", *preludes, "--", dump, *args], os.path.dirname(path), stdin, pre=big_stack)
    if core is None:
        return ("outside", "tenon-core timed out")
    if core[2] < 0 or b"Stack overflow detected" in core[1]:
        return ("outside", "tenon-core ran out of stack")
    if core[2] == 3 and b"tenon-core: " in core[1]:
        why = core[1].decode(errors="replace").split("tenon-core: ", 1)[1].strip().splitlines()[0]
        # the checker accepted it, but the core's semantics stops it: an obligation
        # copied, dropped or used after a move, or a type error at run time
        return ("monitor" if why.startswith("stuck") else "outside", why)
    if not t_ok:
        return "ran", ""   # Lean accepts, tenon rejects: the core run is not stuck
    ref = run([corpus.TENON, "run", "--root", ROOT, os.path.basename(path), *args], os.path.dirname(path), stdin)
    if ref is None:
        return ("outside", "tenon run timed out")
    if (ref[0], ref[2]) == (core[0], core[2]):
        return ("same", "")
    return ("diff", f"exit {ref[2]} (tenon run) vs {core[2]} (core)\n  tenon run out {ref[0][-400:]!r}\n"
                         f"  core      out {core[0][-400:]!r}\n  tenon run err {ref[1][-300:]!r}\n  core      err {core[1][-300:]!r}")


def report_checker(rs):
    """Print the Lean checker's verdicts against tenon check's; return the summary for the evidence record."""
    sub = [r for r in rs if r["lean"] != "unsupported"]
    v = lambda t, l: [r for r in sub if r["tenon"] == t and r["lean"] == l]
    both_acc, both_rej, lean_rej, lean_acc = v(True, "accepted"), v(False, "rejected"), v(True, "rejected"), v(False, "accepted")
    tally = lambda xs, key: sorted(__import__("collections").Counter(r[key] for r in xs).items(), key=lambda kv: -kv[1])
    lean_stuck = [r for r in rs if r["lean"] == "accepted" and r["kind"] == "monitor"]
    lean_ran = [r for r in rs if r["lean"] == "accepted" and r["kind"] in ("same", "diff", "ran")]
    rejects = [r for r in sub if r["rel"].startswith(("tests/reject/", "tests/v2/reject/"))]
    print(f"formal_diff: Lean checker: {len(sub)} of {len(rs)} programs in its subset "
          f"({len([r for r in rs if r['lean'] == 'unsupported'])} unsupported); verdicts agree on {len(both_acc) + len(both_rej)} "
          f"({len(both_acc)} accepted, {len(both_rej)} rejected), tenon accepts and Lean rejects {len(lean_rej)}, "
          f"tenon rejects and Lean accepts {len(lean_acc)} (reject tests in the subset: {len(rejects)})")
    for k, n in tally(lean_rej, "lean_class"):
        print(f"formal_diff:   Lean rejects, {n}: {k}")
    for k, n in tally(lean_acc, "tenon_class"):
        print(f"formal_diff:   tenon rejects, {n}: {k}")
    print(f"formal_diff: of the {len([r for r in rs if r['lean'] == 'accepted'])} programs the Lean checker accepts, "
          f"{len(lean_ran)} ran on the core to the end or a trap (never stuck, checked_program_never_stuck), "
          f"{len(lean_stuck)} got stuck")
    return {"subset": len(sub), "agree_accepted": len(both_acc), "agree_rejected": len(both_rej),
            "lean_rejects": len(lean_rej), "tenon_rejects": len(lean_acc), "lean_accepted_ran": len(lean_ran),
            "lean_accepted_stuck": len(lean_stuck), "lean_rejects_classes": dict(tally(lean_rej, "lean_class")),
            "tenon_rejects_classes": dict(tally(lean_acc, "tenon_class")),
            "lean_rejects_files": {r["rel"]: r["lmsg"][:200] for r in lean_rej},
            "tenon_rejects_files": {r["rel"]: r["tmsg"][:200] for r in lean_acc}}


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
    count = lambda k: len([r for r in rs if r["kind"] == k])
    for r in rs:
        rel, kind, why = r["rel"], r["kind"], r["why"]
        if kind == "diff":
            print("DIFF", rel, why)
        elif kind == "monitor":
            print("STUCK", rel, why, "(Lean checker: " + r["lean"] + ")")
        elif listing and kind == "same":
            print("SAME", rel)
        elif listing and kind == "outside":
            print("OUTSIDE", rel, why)
        if r.get("lean_class"):
            print("LEAN-REJECTS", rel, "|", r["lean_class"], "|", r["lmsg"][:160])
        if r.get("tenon_class") and listing:
            print("TENON-REJECTS", rel, "|", r["tenon_class"], "|", r["tmsg"][:160])
    reasons = {}
    for r in rs:
        if r["kind"] == "outside":
            why = r["why"]
            key = why.split(":")[0] if why.startswith(("unsupported", "stuck")) else why
            reasons[key] = reasons.get(key, 0) + 1
    inside = count("same") + count("diff") + count("monitor")
    print("formal_diff: outside the subset: " + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])))
    print(f"formal_diff: {inside} of {len(rs)} corpus programs are in the core's subset; "
          f"{count('same')} agree with tenon run (stdout and exit status), {count('diff')} disagree; "
          f"on {count('monitor')} the core's semantics gets stuck")
    checker = report_checker(rs)
    if not files:
        corpus.record("formal_diff", {"programs": len(rs), "subset": inside, "same": count("same"), "diff": count("diff"),
                                      "stuck": count("monitor"),
                                      "differ": [r["rel"] for r in rs if r["kind"] == "diff"],
                                      "stuck_files": [r["rel"] for r in rs if r["kind"] == "monitor"],
                                      "subset_files": [r["rel"] for r in rs if r["kind"] in ("same", "diff", "monitor")],
                                      "checker": checker})
    return 1 if count("diff") or count("monitor") else 0


if __name__ == "__main__":
    sys.exit(main())
