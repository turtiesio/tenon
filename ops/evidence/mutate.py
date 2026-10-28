#!/usr/bin/env python3
"""Mutation testing (evidence, not a gate; ops/governance/README.md).

    ops/evidence/mutate.py [COUNT] [SEED]

Mutates the compiler actually used: the self-hosted compile path and the C
runtime (corpus.trusted(): compiler/{lexer,parser,front,checker,ck*,emit*,...}.tn,
runtime/tenon.h). Copies the repository to a scratch directory, then for
each mutant: applies one small change (flip a comparison, swap +/-, negate a
boolean, swap and/or, ...), builds `tenon` from the mutated source as
./check does (the seed builds stage0 with -O0, stage0 builds stage1), and
runs its test suite (`tenon test tests tests/v2`, both backends) as the
oracle. A mutant the seed cannot compile "did not build"; one whose stage0
cannot build stage1 is killed (./check fails); one that builds and passes
every test "survived": the tests do not notice that change. Survivors are
added to .evidence/mutation.json as tasks.
"""
import json, os, random, re, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ops/: corpus.py
import corpus

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEED = corpus.SEED
TARGETS = corpus.trusted()["compiler"] + ["runtime/tenon.h"]
KIND = "tenonc"  # what .evidence/mutation.json counts: the self-hosted compiler's tag (it was called tenonc; totals of an older kind are not carried over)
OPS = [(r" < ", " <= "), (r" <= ", " < "), (r" > ", " >= "), (r" >= ", " > "), (r" == ", " != "),
       (r" != ", " == "), (r" \+ 1", " - 1"), (r" - 1", " + 1"), (r"\btrue\b", "false"), (r"\bfalse\b", "true"),
       (r" && ", " || "), (r" \|\| ", " && "), (r" and ", " or "), (r" or ", " and ")]


def candidates(text):
    out = []
    for i, line in enumerate(text.splitlines()):
        s = line.strip()
        if s.startswith("//") or s.startswith("/*") or s.startswith("*") or s.startswith("#") or "assert" in s or '"' in s:
            continue
        for pat, rep in OPS:
            for m in re.finditer(pat, line):
                out.append((i, m.start(), m.end(), rep))
    return out


def run(cmd, cwd, timeout, env=None):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env).returncode
    except subprocess.TimeoutExpired:
        return -9


def verdict(work, env):
    """nobuild, killed or survived, for the source tree in work."""
    s0, s1 = os.path.join(work, "tenon0"), os.path.join(work, "tenon")
    if run([SEED, "build", "compiler/tenon.tn", "-o", s0, "-O0"], work, 600, env) != 0:
        return "nobuild"
    if run([s0, "build", "compiler/tenon.tn", "-o", s1], work, 600, env) != 0:
        return "killed"
    return "killed" if run([s1, "test", "tests", "tests/v2"], work, 900, env) != 0 else "SURVIVED"


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    rnd = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else int(time.time()))
    work = tempfile.mkdtemp(prefix="tenon-mutate-")
    # the seed's build cache is shared; tenon's (the mutants' C) stays in the scratch directory
    env = dict(os.environ, TENON_ROOT=work, TENON_CACHE=os.path.join(work, ".cache"))
    try:
        for d in ["compiler", "runtime", "lib", "tests"]:
            shutil.copytree(os.path.join(ROOT, d), os.path.join(work, d), symlinks=True)
        if verdict(work, env) != "SURVIVED":
            raise SystemExit("mutate: the unmutated tree does not build or pass its tests")
        results = {"killed": 0, "survived": [], "nobuild": 0}
        for n in range(count):
            path = rnd.choice(TARGETS)
            full = os.path.join(work, path)
            orig = open(full).read()
            cands = candidates(orig)
            if not cands:
                continue
            li, a, b, rep = rnd.choice(cands)
            lines = orig.splitlines(keepends=True)
            before = lines[li]
            lines[li] = before[:a] + rep + before[b:]
            open(full, "w").write("".join(lines))
            try:
                v = verdict(work, env)
                if v == "nobuild":
                    results["nobuild"] += 1
                elif v == "killed":
                    results["killed"] += 1
                else:
                    results["survived"].append({"file": path, "line": li + 1, "from": before.strip(), "to": lines[li].strip()})
                print(f"[{n + 1}/{count}] {v:8} {path}:{li + 1}: {lines[li].strip()[:90]}", flush=True)
            finally:
                open(full, "w").write(orig)
        path = os.path.join(ROOT, ".evidence", "mutation.json")
        old = json.load(open(path)) if os.path.exists(path) else {}
        if old.get("kind") != KIND:
            old = {"kind": KIND, "killed": 0, "survived": [], "nobuild": 0}
        old["killed"] += results["killed"]
        old["nobuild"] += results["nobuild"]
        old["survived"] += results["survived"]
        t = old["killed"] + len(old["survived"])
        old["score"] = round(old["killed"] / t, 2) if t else None
        old["last"] = results
        corpus.record("mutation", old)
        print(f"mutation: {results['killed']} killed, {len(results['survived'])} survived, {results['nobuild']} did not build")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
