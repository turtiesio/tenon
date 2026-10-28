#!/usr/bin/env python3
"""The corpus, the binaries and the default parallelism of the tools,
defined once (and `record`, the one way evidence tools write
.evidence/NAME.json).

    ops/corpus.py            every .tn file of the corpus, one path per line (sorted, relative)
    ops/corpus.py --no-v2    the same without files under a v2/ directory
    ops/corpus.py --jobs     the default number of parallel jobs

Python tools import it (each puts ops/ on `sys.path`):
`corpus.files(no_v2=False)`, `corpus.JOBS`, `corpus.TENON`, `corpus.SEED`.

The binaries (shell tools use the same variables and defaults):
TENON, the self-hosted `tenon` under test ($TENON, default target/tenon,
stage1); TENON0, stage0 ($TENON0, default target/tenon0); SEED, the frozen
bootstrap ($SEED, default target/release/tenon-seed), which only builds
stage0 and is the cross-check's other opinion. ./check builds all three.

The corpus is every .tn file under DIRS. Files under a v2/ directory
(lib/v2, tests/v2, programs/v2, bench/v2) use what only `tenon` has
(traits, workers): the seed cannot read them, so cross-checks against the
seed skip them. JOBS is the core count, capped at 8 (the machine is
shared with other workers, tenon.md §2.4)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ["lib", "tests", "programs", "compiler", "bench", "evidence/study"]
JOBS = max(1, min(os.cpu_count() or 4, 8))
TENON = os.environ.get("TENON") or os.path.join(ROOT, "target", "tenon")
TENON0 = os.environ.get("TENON0") or os.path.join(ROOT, "target", "tenon0")
SEED = os.environ.get("SEED") or os.path.join(ROOT, "target", "release", "tenon-seed")


def trusted():
    """What a compiled program's correctness depends on, as {group: [paths]}:
    the self-hosted compiler's compile path (tenon check/build/emit: loading,
    lexing, parsing, checking, packages, the C backend), the runtime and the
    Tenon sources compiled into programs, and the seed that builds stage0.
    The interpreter, test runner, dumps, formatter and language server are
    checks and tools, not trusted code (ops/repo/status.py, ops/evidence/mutate.py)."""
    import glob
    g = lambda *pats: sorted(os.path.relpath(p, ROOT) for pat in pats for p in glob.glob(os.path.join(ROOT, pat)))
    not_seed = {"interp.rs", "builtins.rs", "codec.rs", "testrun.rs", "astdump.rs"}
    return {
        "compiler": g("compiler/lexer.tn", "compiler/parser.tn", "compiler/front.tn", "compiler/pkg.tn", "compiler/pkgtoml.tn",
                      "compiler/checker.tn", "compiler/ck*.tn", "compiler/emit*.tn", "compiler/tenon.tn"),
        "runtime": g("runtime/tenon.h", "lib/prelude.tn", "lib/v2/prelude.tn", "lib/std/*.tn"),
        "seed": [p for p in g("seed/src/*.rs") if os.path.basename(p) not in not_seed],
    }


def record(name, data):
    """Write .evidence/NAME.json (read by ops/repo/status.py): data plus the date and commit."""
    import datetime, json, subprocess
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    os.makedirs(os.path.join(ROOT, ".evidence"), exist_ok=True)
    data = dict(data, date=datetime.date.today().isoformat(), commit=commit)
    with open(os.path.join(ROOT, ".evidence", name + ".json"), "w") as f:
        json.dump(data, f, indent=1)


def is_v2(path):
    return "/v2/" in "/" + path.replace(os.sep, "/")


def files(no_v2=False):
    out = []
    for top in DIRS:
        for d, _, fs in os.walk(os.path.join(ROOT, top)):
            for f in fs:
                if f.endswith(".tn"):
                    rel = os.path.relpath(os.path.join(d, f), ROOT)
                    if not (no_v2 and is_v2(rel)):
                        out.append(rel)
    return sorted(out)


if __name__ == "__main__":
    if sys.argv[1:] == ["--jobs"]:
        print(JOBS)
    elif sys.argv[1:] in ([], ["--no-v2"]):
        print("\n".join(files("--no-v2" in sys.argv)))
    else:
        sys.exit("usage: ops/corpus.py [--no-v2 | --jobs]")
