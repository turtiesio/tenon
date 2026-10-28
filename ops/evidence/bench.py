#!/usr/bin/env python3
"""Benchmarks: each bench/NAME has NAME.tn, NAME.c, NAME.py (and optional
gen.py producing input.txt fed on stdin). Outputs must be identical across
implementations. Writes .evidence/bench.json (median of N runs, wall time).

Parallel benchmarks (workers, v2): each bench/v2/NAME has NAME.tn,
which takes the number of workers as its argument (0: the same function on
one thread, the serial baseline), and optionally NAME.c, a serial C
reference with the same output. Each is run serially and with 1, 2, 4 and 8 workers (PAR_WORKERS
to change); the speedup is over the serial run of the same binary. Writes
.evidence/bench_parallel.json. `bench.py --parallel` runs only these.

Tenon programs are built (-O2) by `tenon`, the compiler in use: $TENON,
default target/tenon (./check and ops/evidence/evidence.sh build it)."""
import json, os, statistics, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TENON = os.environ.get("TENON") or os.path.join(ROOT, "target", "tenon")
os.environ.setdefault("TENON_ROOT", ROOT)
OUT = os.path.join(ROOT, "bench", "out")
RUNS = int(os.environ.get("BENCH_RUNS", "3"))
# The C programs are built by the C compiler `tenon build` uses ($CC, default
# cc) with the flags it passes (compiler/tenon.tn cc_flags): the same compiler
# and flags on both sides.
CC = os.environ.get("CC") or "cc"
CFLAGS = ["-O2", "-w", "-std=gnu11", "-pthread", "-fno-tree-slp-vectorize"]
# Every compiled baseline has Tenon's integer semantics (bench/README.md): the
# C references use bench/checked.h, Rust is built with overflow checks on.


def timed(cmd, stdin_path):
    times, out = [], None
    for _ in range(RUNS):
        with open(stdin_path or os.devnull, "rb") as f:
            t = time.perf_counter()
            r = subprocess.run(cmd, stdin=f, capture_output=True)
            times.append(time.perf_counter() - t)
        if r.returncode != 0:
            raise SystemExit(f"{cmd} failed: {r.stderr.decode()[:500]}")
        out = r.stdout
    return statistics.median(times), out


def parallel():
    os.makedirs(OUT, exist_ok=True)
    counts = [int(x) for x in os.environ.get("PAR_WORKERS", "1,2,4,8").split(",")]
    d0 = os.path.join(ROOT, "bench", "v2")
    results = {}
    for name in sorted(os.listdir(d0)):
        d = os.path.join(d0, name)
        if not os.path.isfile(os.path.join(d, name + ".tn")):
            continue
        tn_bin, c_bin = os.path.join(OUT, name + "_par"), os.path.join(OUT, name + "_par_c")
        subprocess.run([TENON, "build", os.path.join(d, name + ".tn"), "-o", tn_bin], check=True)
        serial, out = timed([tn_bin, "0"], None)
        row = {"serial": round(serial, 4), "cores": os.cpu_count()}
        line = f"{name:10} serial {serial:.3f}s"
        if os.path.exists(os.path.join(d, name + ".c")):
            # -ffp-contract=off: no fused multiply-add, as Tenon's floats (same results)
            subprocess.run([CC] + CFLAGS + ["-ffp-contract=off", "-o", c_bin, os.path.join(d, name + ".c"), "-lm"], check=True)
            c_t, c_out = timed([c_bin], None)
            if out != c_out:
                raise SystemExit(f"{name}: Tenon and C disagree")
            row["c"] = round(c_t, 4)
            line += f"  c {c_t:.3f}s"
        for n in counts:
            t, o = timed([tn_bin, str(n)], None)
            if o != out:
                raise SystemExit(f"{name}: {n} workers give another output")
            row[f"w{n}"] = round(t, 4)
            row[f"speedup{n}"] = round(serial / t, 2)
            line += f"  {n}w {t:.3f}s ({serial / t:.2f}x)"
        results[name] = row
        print(line)
    os.makedirs(os.path.join(ROOT, ".evidence"), exist_ok=True)
    json.dump(results, open(os.path.join(ROOT, ".evidence", "bench_parallel.json"), "w"), indent=1, sort_keys=True)


def main():
    if not os.path.exists(TENON):
        raise SystemExit(f"bench: no tenon at {TENON} (./check builds it)")
    if sys.argv[1:] == ["--parallel"]:
        return parallel()
    os.makedirs(OUT, exist_ok=True)
    names = sys.argv[1:] or sorted(os.listdir(os.path.join(ROOT, "bench")))
    results = {}
    for name in names:
        d = os.path.join(ROOT, "bench", name)
        if not os.path.isfile(os.path.join(d, name + ".tn")):
            continue
        inp = None
        if os.path.exists(os.path.join(d, "gen.py")):
            inp = os.path.join(d, "input.txt")
            if not os.path.exists(inp):
                subprocess.run([sys.executable, "gen.py"], cwd=d, check=True)
        tn_bin, c_bin = os.path.join(OUT, name + "_tn"), os.path.join(OUT, name + "_c")
        subprocess.run([TENON, "build", os.path.join(d, name + ".tn"), "-o", tn_bin], check=True)
        subprocess.run([CC] + CFLAGS + ["-o", c_bin, os.path.join(d, name + ".c"), "-lm"], check=True)
        impls = [("tenon", [tn_bin]), ("c", [c_bin]), ("python", [sys.executable, os.path.join(d, name + ".py")])]
        rs = os.path.join(d, name + ".rs")
        if os.path.exists(rs):
            rs_bin = os.path.join(OUT, name + "_rs")
            subprocess.run(["rustc", "-O", "-C", "overflow-checks=on", "-o", rs_bin, rs], check=True, capture_output=True)
            impls.append(("rust", [rs_bin]))
        ts = os.path.join(d, name + ".ts")
        if os.path.exists(ts):
            impls.append(("typescript", ["node", ts]))
        row = {}
        outs = {}
        for impl, cmd in impls:
            t, out = timed(cmd, inp)
            row[impl] = round(t, 4)
            outs[impl] = out
        if len(set(outs.values())) != 1:
            for k, v in outs.items():
                print(f"--- {k}\n{v.decode()[:400]}")
            raise SystemExit(f"{name}: implementations disagree")
        row["tenon_vs_c"] = round(row["tenon"] / row["c"], 2)
        row["size_tenon"] = os.path.getsize(tn_bin)
        row["size_c"] = os.path.getsize(c_bin)
        results[name] = row
        print(f"{name:10} tenon {row['tenon']:.3f}s  c {row['c']:.3f}s  python {row['python']:.3f}s  tenon/c {row['tenon_vs_c']}x")
    os.makedirs(os.path.join(ROOT, ".evidence"), exist_ok=True)
    path = os.path.join(ROOT, ".evidence", "bench.json")
    old = json.load(open(path)) if os.path.exists(path) else {}
    old.update(results)
    json.dump(old, open(path, "w"), indent=1, sort_keys=True)
    if not sys.argv[1:]:
        parallel()


if __name__ == "__main__":
    main()
