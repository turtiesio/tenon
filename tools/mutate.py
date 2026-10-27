#!/usr/bin/env python3
"""Mutation testing (evidence, not a gate; governance/README.md).

    tools/mutate.py [COUNT] [SEED]

Copies the repository to a scratch directory, then for each mutant: applies
one small change to the compiler or runtime (flip a comparison, swap +/-,
negate a boolean, ...), rebuilds, and runs the test corpus. A mutant that
builds and still passes every test "survived": the tests do not notice that
change. Survivors are written to .evidence/mutation.json as tasks.
"""
import json, os, random, re, shutil, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = ["src/check.rs", "src/check_expr.rs", "src/linear.rs", "src/exhaust.rs", "src/emit_body.rs",
           "src/emit_ctl.rs", "src/emit_builtins.rs", "runtime/tenon.h", "src/lexer.rs", "src/parser.rs"]
OPS = [(r" < ", " <= "), (r" <= ", " < "), (r" > ", " >= "), (r" >= ", " > "), (r" == ", " != "),
       (r" != ", " == "), (r" \+ 1", " - 1"), (r" - 1", " + 1"), (r"\btrue\b", "false"), (r"\bfalse\b", "true"),
       (r" && ", " || "), (r" \|\| ", " && ")]


def candidates(text):
    out = []
    for i, line in enumerate(text.splitlines()):
        s = line.strip()
        if s.startswith("//") or s.startswith("/*") or s.startswith("*") or "assert" in s or '"' in s:
            continue
        for pat, rep in OPS:
            for m in re.finditer(pat, line):
                out.append((i, m.start(), m.end(), rep))
    return out


def run(cmd, cwd, timeout):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        return -9


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    rnd = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else int(time.time()))
    work = tempfile.mkdtemp(prefix="tenon-mutate-")
    try:
        for d in ["src", "runtime", "std", "tests"]:
            shutil.copytree(os.path.join(ROOT, d), os.path.join(work, d), symlinks=True)
        for f in ["Cargo.toml", "Cargo.lock"]:
            shutil.copy(os.path.join(ROOT, f), work)
        if run(["cargo", "build", "--release", "-q"], work, 600) != 0:
            raise SystemExit("baseline does not build")
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
                if run(["cargo", "build", "--release", "-q"], work, 600) != 0:
                    results["nobuild"] += 1
                    verdict = "nobuild"
                elif run([os.path.join(work, "target/release/tenon"), "test", "tests"], work, 600) != 0:
                    results["killed"] += 1
                    verdict = "killed"
                else:
                    results["survived"].append({"file": path, "line": li + 1, "from": before.strip(), "to": lines[li].strip()})
                    verdict = "SURVIVED"
                print(f"[{n + 1}/{count}] {verdict:8} {path}:{li + 1}: {lines[li].strip()[:90]}", flush=True)
            finally:
                open(full, "w").write(orig)
        tested = results["killed"] + len(results["survived"])
        results["score"] = round(results["killed"] / tested, 2) if tested else None
        os.makedirs(os.path.join(ROOT, ".evidence"), exist_ok=True)
        path = os.path.join(ROOT, ".evidence", "mutation.json")
        old = json.load(open(path)) if os.path.exists(path) else {"killed": 0, "survived": [], "nobuild": 0}
        old["killed"] += results["killed"]
        old["nobuild"] += results["nobuild"]
        old["survived"] += results["survived"]
        t = old["killed"] + len(old["survived"])
        old["score"] = round(old["killed"] / t, 2) if t else None
        json.dump(old, open(path, "w"), indent=1)
        print(f"mutation: {results['killed']} killed, {len(results['survived'])} survived, {results['nobuild']} did not build")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
