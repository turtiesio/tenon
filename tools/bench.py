#!/usr/bin/env python3
"""Benchmarks: each bench/NAME has NAME.tn, NAME.c, NAME.py (and optional
gen.py producing input.txt fed on stdin). Outputs must be identical across
implementations. Writes .evidence/bench.json (median of N runs, wall time)."""
import json, os, statistics, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TENON = os.path.join(ROOT, "target", "release", "tenon")
OUT = os.path.join(ROOT, "bench", "out")
RUNS = int(os.environ.get("BENCH_RUNS", "3"))


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


def main():
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
        subprocess.run(["cc", "-O2", "-o", c_bin, os.path.join(d, name + ".c")], check=True)
        row = {}
        outs = {}
        for impl, cmd in [("tenon", [tn_bin]), ("c", [c_bin]), ("python", [sys.executable, os.path.join(d, name + ".py")])]:
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


if __name__ == "__main__":
    main()
