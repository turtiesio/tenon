#!/usr/bin/env python3
"""Generate STATUS.md from measurements. Never edit STATUS.md by hand.

Runs ./check (the loop time, its per-step times, the test counts and the
cross-check), reads what the evidence tools wrote (.evidence/*.json, through
corpus.record; ops/evidence/evidence.sh runs them all) and the published usability
rows (evidence/study/results/waveN/rows.json), measures the trusted base
(corpus.trusted()) and the self-hosted compile time, and judges each goal of
milestones 1 and 2 (tenon.md §4, §5) from that data where a number decides it.
ops/repo/unmet.md holds only the prose that cannot be computed. A summary line
of ./check that no longer parses is reported as an open regression, never
silently skipped."""
import glob, json, os, re, shutil, statistics, subprocess, sys, time, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ops/: corpus.py
import corpus
sys.path.insert(0, os.path.join(corpus.ROOT, "ops", "study"))
import study

ROOT = corpus.ROOT
EV = os.path.join(ROOT, ".evidence")
# where ./check is timed; the 60 s budget is the development machine's ("local"),
# the nightly workflow sets TENON_MACHINE (docs/dev/automation.md)
MACHINE = os.environ.get("TENON_MACHINE", "local")


def sh(cmd):
    return subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True)


def load(name):
    p = os.path.join(EV, name)
    return json.load(open(p)) if os.path.exists(p) else {}


def code_lines(path):
    """Non-blank lines that are not only a comment."""
    n = 0
    for line in open(os.path.join(ROOT, path)):
        s = line.strip()
        if s and not (s.startswith("//") or s.startswith("/*") or s.startswith("* ") or s in ("*", "*/")):
            n += 1
    return n


# The summary lines of ./check that STATUS.md reports, by name.
PATTERNS = {
    "tests": r"tests: (\d+) run \(x2 backends\), (\d+) reject, (\d+) lex/parse, (\d+) failed",
    "programs": r"programs: (\d+) scenario\(s\) x2 backends, (\S+) failed",
    "selfhost": r"selfhost: lexer, parser and checker agree with the seed on (\d+) files \((\d+) accepted, (\d+) rejected\);"
                r" emitter on the \d+ accepted; fixpoint: stage0 = stage1 on (\d+) accepted files, v2 included"
                r" \(compiler/tenon\.tn: (\d+) bytes of C\); (\d+) disagreements",
    "fmt": r"fmt: (\d+) files in canonical layout \((\d+) skipped by ops/gates/fmt_skip\.txt, (\d+) more do not parse\).*?; (\d+) problems",
    "grammar": r"vscode grammar: ok: (\d+) files",
    "lsp": r"lsp: ok \(",
    "pkg": r"pkg: ok \((\d+) checks",
    "doctest": r"doctest: (\d+) doc program\(s\) checked, (\d+) failed",
    "approvals": r"approvals_test: refuses .* \((\d+) scenarios\)",
    "formal": r"formal_check: formal/ builds; no sorry; (\d+) guarded theorems",
}


def excerpt(tool, needle, n=6):
    """The lines of TOOL's last output (.evidence/NAME.log, ops/evidence/evidence.sh) from the first one naming NEEDLE."""
    name = {"ops/evidence/asan.sh": "asan", "ops/evidence/tsan.sh": "tsan", "ops/evidence/interp_diff.py": "interp_diff",
            "ops/evidence/checkfuzz.py": "checkfuzz", "ops/gates/formal_diff.py": "formal_diff"}[tool]
    p = os.path.join(EV, name + ".log")
    out = open(p, errors="replace").read().splitlines() if os.path.exists(p) else []
    i = next((i for i, l in enumerate(out) if needle in l), None)
    return "\n".join(out[i:i + n])[:3000] if i is not None else f"(not in .evidence/{name}.log)"


def findings():
    """Opened and fixed findings: GitHub issues per label (when gh can read them; the queue since 2026-10-28)
    and the findings tables of tests/redteam/FINDINGS*.md (rows whose status says FIXED)."""
    rows = []
    for label in ["redteam", "regression"] if shutil.which("gh") else []:
        r = subprocess.run(["gh", "issue", "list", "--label", label, "--state", "all", "--limit", "1000", "--json", "state"],
                           cwd=ROOT, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            states = [i["state"] for i in json.loads(r.stdout)]
            rows.append((f"GitHub issues labeled `{label}`", len(states), states.count("CLOSED")))
    for p in sorted(glob.glob(os.path.join(ROOT, "tests", "redteam", "FINDINGS*.md"))):
        fixed = {}  # finding number -> fixed, from every table that has a row for it (a later status table wins)
        for l in open(p):
            m = re.match(r"\| *(\d+) *\|(.*)", l)
            if m:
                tail = " ".join(m.group(2).rstrip().rstrip("|").split("|")[-2:]).lower()
                fixed[m.group(1)] = fixed.get(m.group(1), False) or bool(re.search(r"\b(fixed|documented)\b", tail))
        rows.append((os.path.relpath(p, ROOT), len(fixed), sum(fixed.values())))
    return rows


def trends(w, row):
    """Append ROW to .evidence/history.jsonl (one line per run) and write the correctness trends."""
    path = os.path.join(EV, "history.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    by_date = {}
    for line in open(path):
        r = json.loads(line)
        by_date[(r["date"], r["machine"])] = r  # the last run of each day
    w("## Correctness over time\n")
    w("Findings opened and fixed (closed):\n")
    w("| Source | Opened | Fixed | Open |\n|---|---|---|---|")
    for src, n, fixed in findings():
        w(f"| {src} | {n} | {fixed} | {n - fixed} |")
    w("\nEvidence per day (the last run of each day; `.evidence/history.jsonl`):\n")
    cols = [("check_s", "check s"), ("fuzz_disagreements", "fuzz disagreements"), ("fuzz_programs", "of programs"),
            ("asan_failed", "ASan failed"), ("tsan_failed", "TSan failed"), ("mutation_score", "mutation score"),
            ("mutants_survived_last", "new survivors"), ("checkfuzz_disagreements", "checkfuzz"),
            ("interp_diff", "interp_diff"), ("regressions", "open regressions")]
    w("| Date | Machine | Commit | " + " | ".join(c for _, c in cols) + " |\n|---|---|---|" + "---|" * len(cols))
    for (d, m), r in sorted(by_date.items())[-14:]:
        w(f"| {d} | {m} | `{r['commit']}` | " + " | ".join("-" if r.get(k) is None else str(r[k]) for k, _ in cols) + " |")
    w("")


def best_of(cmd, n=3):
    ts = []
    for _ in range(n):
        t = time.perf_counter()
        subprocess.run(cmd, cwd=ROOT, capture_output=True, env=dict(os.environ, TENON_ROOT=ROOT))
        ts.append(time.perf_counter() - t)
    return min(ts)


def latest_wave():
    waves = sorted(glob.glob(os.path.join(ROOT, "evidence", "study", "results", "wave*", "rows.json")),
                   key=lambda p: int(re.search(r"wave(\d+)", p).group(1)))
    if not waves:
        return None, None
    p = waves[-1]
    return int(re.search(r"wave(\d+)", p).group(1)), json.load(open(p))


def verdict(ok, text):
    return ("**met**" if ok else "**not met**") + (f": {text}" if text else "")


def main():
    os.makedirs(EV, exist_ok=True)
    today = datetime.date.today().isoformat()
    commit = sh("git rev-parse --short HEAD").stdout.strip()
    t = time.time()
    r = sh("./check --fast 2>&1")
    total = time.time() - t
    passed = r.returncode == 0
    out = r.stdout
    got = {k: re.search(p, out, re.M) for k, p in PATTERNS.items()}
    regressions = []

    def reg(key, title, body="", agent_ok=True):
        """One open regression: KEY is stable across runs (the nightly workflow keeps one issue per key)."""
        regressions.append({"key": key, "title": title, "body": body,
                            "labels": ["regression"] + (["agent-ok"] if agent_ok else [])})

    if not passed:
        reg("check:fails", f"`./check` fails at commit `{commit}`: " + (re.findall(r"FAILED at: (.*)", out) or ["see its output"])[-1],
            "\n".join(out.splitlines()[-30:]))
    for k, m in got.items():
        if m is None and passed:
            reg(f"status:{k}", f"ops/repo/status.py cannot read the `{k}` summary line of ./check (the line changed)")
    g = lambda k, i, d="?": got[k].group(i) if got[k] else d
    steps = re.findall(r"^\s+([\d.]+)  (.+)$", out.split("check: seconds per step")[-1], re.M) if "check: seconds per step" in out else []
    loops = load("loops.json")
    lkey = "check_fast" if MACHINE == "local" else f"check_fast@{MACHINE}"
    before = [v for d, v in sorted(loops.get(lkey, {}).items()) if d != today][-7:]
    if passed:  # a failed run measures nothing
        loops.setdefault(lkey, {})[today] = round(total, 1)
        json.dump(loops, open(os.path.join(EV, "loops.json"), "w"), indent=1, sort_keys=True)
        if MACHINE == "local" and total > 60:
            reg("check:budget", f"`./check` took {total:.0f} s, over its 60 s budget", agent_ok=False)
        elif MACHINE != "local" and len(before) >= 3 and total > 1.5 * statistics.median(before):
            reg(f"check:time@{MACHINE}", f"`./check` took {total:.0f} s on {MACHINE}, over 1.5x its median of the"
                f" last {len(before)} runs there ({statistics.median(before):.0f} s)", agent_ok=False)
    hist = sorted(loops.get("check_fast", {}).items())  # the development machine's: what the 60 s budget is about

    trusted = corpus.trusted()
    groups = {k: [(p, code_lines(p)) for p in v] for k, v in trusted.items()}
    sizes = {k: sum(n for _, n in v) for k, v in groups.items()}
    fuzz, mut, asan, tsan = load("fuzz.json"), load("mutation.json"), load("asan.json"), load("tsan.json")
    idiff, cfuzz, seedt = load("interp_diff.json"), load("checkfuzz.json"), load("seed_test.json")
    fdiff = load("formal_diff.json")
    bench, par = load("bench.json"), load("bench_parallel.json")
    wave, rows = latest_wave()
    usab = study.summarize(rows) if rows else None

    def when(d):
        return f"{d.get('date', '?')}, `{d.get('commit', '?')}`"

    lines = []
    w = lines.append
    w("# Status\n")
    w(f"Generated by `ops/repo/status.py` at commit `{commit}` on {today}. Do not edit by hand.")
    w("Evidence rows give the date and commit they were measured at (`ops/evidence/evidence.sh` runs them all).\n")

    w("## Loops\n")
    w("| Loop | Budget | Measured | Reproduce |\n|---|---|---|---|")
    w(f"| `check --fast` | 60 s (on the development machine) | {total:.1f} s on {MACHINE} ({'PASS' if passed else 'FAIL'}) | `./check --fast` |")
    w("| landing | 5 min | not measured here (`ops/repo/land.sh` prints its time) | `ops/repo/land.sh MSG` |")
    if steps:
        w("\nPer step (this run; ./check prints the same table):\n")
        w("| Step | Seconds |\n|---|---|")
        for sec, name in steps:
            w(f"| {name} | {sec} |")
    for k, v in sorted(loops.items()):
        if k.startswith("check_fast") and len(v) > 1:
            where = k.partition("@")[2] or "local"
            w(f"\nHistory on {where} (passing runs): " + ", ".join(f"{d}: {s} s" for d, s in sorted(v.items())[-7:]))

    w("\n## Tests on main\n")
    w(f"- `tenon test tests tests/v2`: {g('tests', 1)} run programs, each executed by tenon's interpreter **and** its C backend"
      f" and compared with golden output; {g('tests', 2)} reject programs (must fail to compile with a specific diagnostic);"
      f" {g('tests', 3)} lexer/parser cases; failed: {g('tests', 4)}")
    w(f"- program scenarios: {g('programs', 1)} real programs, each on both backends (`ops/gates/programs.sh`); failed: {g('programs', 2)}")
    w(f"- cross-check with the seed (`ops/gates/selfhost.sh`): tokens, AST, checker verdict and C agree on {g('selfhost', 1)} files"
      f" ({g('selfhost', 2)} accepted, {g('selfhost', 3)} rejected); fixpoint: stage0 and stage1 emit the same C on"
      f" {g('selfhost', 4)} accepted files, compiler/tenon.tn ({g('selfhost', 5)} bytes of C) included; disagreements: {g('selfhost', 6)}")
    w(f"- doc programs: {g('doctest', 1)} compile (`ops/gates/doctest.py`); formatter: {g('fmt', 1)} files canonical,"
      f" {g('fmt', 2)} skipped, {g('fmt', 4)} problems (`ops/gates/fmt_check.sh`); packages: {g('pkg', 1)} checks (`ops/gates/pkg_test.sh`);"
      f" language server: {'ok' if got['lsp'] else '?'} (`ops/gates/lsp_test.py`); editor grammar: {g('grammar', 1)} files"
      f" (`ops/gates/vscode_grammar_check.py`); approvals checker: {g('approvals', 1)} scenarios (`ops/gates/approvals_test.sh`);"
      f" proofs: {g('formal', 1)} guarded theorems check (`ops/gates/formal_check.sh`)")

    w("\n## Evidence on main (`ops/evidence/evidence.sh`)\n")
    if fuzz:
        last = fuzz.get("last", {})
        w(f"- differential fuzzing of tenon (both backends, the seed's interpreter as a third opinion): {fuzz['programs']} generated"
          f" programs, {fuzz['disagreements']} disagreements, {fuzz['rejected']} rejected by the checker (generator imprecision);"
          f" last run {last.get('programs', '?')} programs, {when(fuzz)} (`ops/evidence/fuzz.py N`)")
        if last.get("disagreements"):
            reg("fuzz", f"fuzzing: {last['disagreements']} disagreements in the last run",
                "Generated programs on which the backends or the seed disagree (reproduce: `python3 ops/evidence/fuzz.py 1 SEED`;"
                " the programs are in .evidence/fuzz-failures/):\n\n" + "\n".join(f"- {x}" for x in last.get("failures", [])))
    else:
        w("- differential fuzzing: not run yet (`ops/evidence/fuzz.py N`)")
    if mut:
        n = mut["killed"] + len(mut["survived"])
        w(f"- mutation testing of the self-hosted compile path and the runtime: {mut['killed']}/{n} mutants killed ({mut['score']}),"
          f" {mut['nobuild']} did not build; survivors become tests or are judged equivalent ({when(mut)}; `ops/evidence/mutate.py N`)")
        for s in mut["survived"]:
            w(f"  - survived: `{s['file']}:{s['line']}`: `{s['from']}` -> `{s['to']}`")
        for s in mut.get("last", {}).get("survived", []):
            reg(f"mutant:{s['file']}:{s['line']}", f"mutation survived at {s['file']}:{s['line']}: `{s['to'][:80]}`",
                f"Changing `{s['from']}` to `{s['to']}` ({s['file']}:{s['line']}) builds and passes every test. Add a test"
                " that fails on the mutant, or explain why the mutant is equivalent (`ops/evidence/mutate.py`).")
    else:
        w("- mutation testing: not run yet (`ops/evidence/mutate.py N`)")
    for name, d, tool, what in [("ASan+UBSan", asan, "ops/evidence/asan.sh", "run tests and programs"),
                                ("ThreadSanitizer", tsan, "ops/evidence/tsan.sh", "programs with workers")]:
        if d:
            runs = f" ({d['runs']} runs)" if "runs" in d else ""
            w(f"- {name}: {d['programs']} {what}{runs}, {'all clean' if d['failed'] == 0 else '**%d FAILED**' % d['failed']} ({when(d)}; `{tool}`)")
            for f in d.get("failures", []) if d["failed"] else []:
                prog = f.split(":")[0]
                reg(f"{os.path.basename(tool)[:-3]}:{prog}", f"{name}: {f}", f"`{tool}` reports `{f}`:\n\n```\n{excerpt(tool, prog)}\n```")
        else:
            w(f"- {name}: not run yet (`{tool}`)")
    if idiff:
        w(f"- seed's interpreter vs tenon's on the corpus: {idiff['same']} of {idiff['files']} files the same, {idiff['diff']} differ,"
          f" {idiff['skipped']} skipped ({when(idiff)}; `ops/evidence/interp_diff.py`)")
        for f in idiff.get("differ", []):
            reg(f"interp_diff:{f}", f"interp_diff: `tenon-seed run` and `tenon run` differ on {f}",
                f"```\n{excerpt('ops/evidence/interp_diff.py', f)}\n```")
    else:
        w("- seed's interpreter vs tenon's: not run yet (`ops/evidence/interp_diff.py`)")
    if fdiff:
        w(f"- Lean core semantics vs `tenon run` (formal/README.md): {fdiff['subset']} of {fdiff['programs']} corpus programs in"
          f" the core's subset; {fdiff['same']} agree, {fdiff['diff']} differ, {fdiff.get('stuck', 0)} accepted by the checker"
          f" but stuck in the core ({when(fdiff)}; `ops/gates/formal_diff.py`)")
        for f in fdiff.get("differ", []) + fdiff.get("stuck_files", []):
            reg(f"formal_diff:{f}", f"formal_diff: the Lean core and `tenon run` disagree on {f}",
                f"```\n{excerpt('ops/gates/formal_diff.py', f)}\n```")
    else:
        w("- Lean core semantics vs `tenon run`: not run yet (`ops/gates/formal_diff.py`)")
    if cfuzz:
        w(f"- seed's checker and emitter vs tenon's on {cfuzz['mutants']} mutated corpus programs: {cfuzz['disagreements']} disagreements"
          f" ({when(cfuzz)}; `ops/evidence/checkfuzz.py N`)")
        if cfuzz["disagreements"]:
            reg("checkfuzz", f"checkfuzz: {cfuzz['disagreements']} disagreements between the seed's checker and tenon's",
                f"Seed {cfuzz.get('seed')} (`python3 ops/evidence/checkfuzz.py {cfuzz['mutants']} {cfuzz.get('seed')}`):\n\n"
                f"```\n{excerpt('ops/evidence/checkfuzz.py', 'DISAGREE', 40)}\n```")
    else:
        w("- seed's checker vs tenon's on mutated programs: not run yet (`ops/evidence/checkfuzz.py N`)")
    if seedt:
        w(f"- the seed's own suite (`tenon-seed test tests`): {seedt['summary']} ({when(seedt)})")
        m = re.search(r"(\d+) failed", seedt["summary"])
        if not m or m.group(1) != "0":
            reg("seed_test", f"the seed's own test suite: {seedt['summary']}")

    w("\n## Benchmarks (wall time, median; `python3 ops/evidence/bench.py`, Tenon built by tenon -O2)\n")
    worst = None
    if bench:
        w("| Program | Tenon | C (cc -O2) | Rust (-O) | Python | TypeScript (node) | Tenon / C | Binary (Tenon / C) |\n|---|---|---|---|---|---|---|---|")
        for k, v in sorted(bench.items()):
            if not isinstance(v, dict):
                continue
            opt = lambda key: f"{v[key]:.3f} s" if key in v else "-"
            w(f"| {k} | {v['tenon']:.3f} s | {v['c']:.3f} s | {opt('rust')} | {v['python']:.3f} s | {opt('typescript')} | {v['tenon_vs_c']}x | {v['size_tenon'] // 1024} KB / {v['size_c'] // 1024} KB |")
        worst = max(v["tenon_vs_c"] for v in bench.values() if isinstance(v, dict))
        for k, v in sorted(bench.items()):
            if isinstance(v, dict) and v["tenon_vs_c"] > 1.5:
                reg(f"bench:{k}", f"benchmark {k}: Tenon takes {v['tenon_vs_c']}x the time of C (target: within 1.5x)",
                    f"`python3 ops/evidence/bench.py {k}`: Tenon {v['tenon']:.3f} s, C {v['c']:.3f} s.", agent_ok=False)
        w(f"\nTarget: within 1.5x of C. Worst: {worst}x — {'met' if worst <= 1.5 else '**not met**'}.")
    else:
        w("Not run yet.")
    s4 = None
    if par:
        w("\n### Parallel (workers; `python3 ops/evidence/bench.py --parallel`)\n")
        ns = sorted(int(k[1:]) for k in next(iter(par.values())) if re.fullmatch(r"w\d+", k))
        w("| Program | C (serial) | Tenon serial | " + " | ".join(f"{n} workers" for n in ns) + " |\n|---|---|---|" + "---|" * len(ns))
        for k, v in sorted(par.items()):
            c = f"{v['c']:.3f} s" if "c" in v else "-"
            w(f"| {k} | {c} | {v['serial']:.3f} s | " + " | ".join(f"{v[f'w{n}']:.3f} s ({v[f'speedup{n}']}x)" for n in ns) + " |")
        s4 = min(v.get("speedup4", 0) for v in par.values())
        cores = next(iter(par.values())).get("cores", "?")
        w(f"\nTarget: at least 3x on 4 cores. Lowest: {s4}x on a {cores}-core machine — {'met' if s4 >= 3 else '**not met**'}.")

    w("\n## Usability study\n")
    if usab:
        w(f"Wave {wave} (evidence/study/results/wave{wave}/rows.json). " + usab[0] + "\n")
    else:
        w("Not run yet. Task specifications: `evidence/study/tasks/`; hidden tests are kept out of authors' view.\n")

    w("## Trusted base\n")
    w("Non-blank, non-comment lines that must be correct for compiled programs to be correct (`corpus.trusted()`).")
    w("The interpreter, test runner, dumps, formatter and language server are checks and tools, not trusted code.\n")
    w("| Part | Files | Lines |\n|---|---|---|")
    labels = {"compiler": "self-hosted compiler (compile path of `tenon`)", "runtime": "runtime and the Tenon sources compiled into programs",
              "seed": "seed (frozen bootstrap: builds stage0 only; anchor)"}
    for k in ["compiler", "runtime", "seed"]:
        w(f"| {labels[k]} | {len(groups[k])} | {sizes[k]} |")
    w(f"\nTrusted for a compiled program: **{sizes['compiler'] + sizes['runtime']}** (compiler + runtime), plus the seed's"
      f" {sizes['seed']} and the named trust anchors `rustc` and the C compiler.\n")
    w("<details><summary>Per file</summary>\n\n| File | Lines |\n|---|---|")
    for k in ["compiler", "runtime", "seed"]:
        for p, n in groups[k]:
            w(f"| `{p}` | {n} |")
    w("\n</details>\n")

    # milestone goals, judged from the data above where a number decides them
    seed_t = best_of([corpus.SEED, "emit", "compiler/tenon.tn"])
    self_t = best_of([corpus.TENON, "emit", "compiler/tenon.tn"])
    progs = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(ROOT, "programs", "*", "test.sh"))
                   + glob.glob(os.path.join(ROOT, "programs", "v2", "*", "test.sh")))
    wk_progs = [os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(ROOT, "programs", "v2", "*", "*.tn"))
                if "workers()" in open(p).read()]
    fuzz_ok = bool(fuzz) and fuzz.get("disagreements", 1) == 0
    nprog = int(g("programs", 1, "0")) if got["programs"] else 0
    tn, py = (usab[1].get("tenon"), usab[1].get("python")) if usab else (None, None)
    days = len(hist)
    loop_ok = passed and all(v <= 60 for _, v in hist)
    sh_ok = got["selfhost"] is not None and g("selfhost", 6) == "0"
    tests_ok = got["tests"] is not None and g("tests", 4) == "0"
    v2 = lambda d: len([f for f in glob.glob(os.path.join(ROOT, "tests", "v2", d, "*.tn")) if not open(f).readline().startswith("// module")])
    row = lambda goal, status: w("| " + goal + " | " + status + " |")
    w("## Milestones\n")
    w("Judged by ops/repo/status.py from the data above; hand-written notes follow (ops/repo/unmet.md).\n")
    w("Milestone 1 (tenon.md §4):\n")
    w("| Goal | Status |\n|---|---|")
    row("10 real programs, differential and fuzz testing green",
        verdict(nprog >= 10 and fuzz_ok and g("programs", 2) == "0", "%d programs with scenarios (%s); fuzzing %s disagreements"
                % (nprog, ", ".join(progs), fuzz.get("disagreements", "?"))))
    if tn and py:
        lines_ok, time_ok = tn["code_lines"] <= py["code_lines"], tn["minutes_total"] <= py["minutes_total"]
        row("Blind usability study at or below Python on line count and task time",
            verdict(lines_ok and time_ok, "wave %s: lines %s vs %s (%s); minutes %s vs %s (%.2fx Python, %s)"
                    % (wave, tn["code_lines"], py["code_lines"], "met" if lines_ok else "not met", tn["minutes_total"],
                       py["minutes_total"], tn["minutes_total"] / py["minutes_total"], "met" if time_ok else "not met")))
    else:
        row("Blind usability study at or below Python on line count and task time", "no published wave")
    row("Performance within 1.5x of C on the program benchmarks",
        verdict(worst <= 1.5, "worst %sx" % worst) if worst is not None else "not measured")
    row("`check --fast` <= 60 s and landing <= 5 min over a week",
        verdict(loop_ok and days >= 7, "check %.1f s now on %s; %d day(s) of history on the development machine, a week needed;"
                " every day <= 60 s: %s; landing not measured here" % (total, MACHINE, days, loop_ok)))
    row("Self-hosted lexer, parser and checker agree with the bootstrap on the full corpus",
        verdict(sh_ok, "%s files, %s disagreements" % (g("selfhost", 1), g("selfhost", 6))))
    row("Approvals log and checker exist and refused a real weakening in a test",
        verdict(got["approvals"] is not None, "%s scenarios" % g("approvals", 1)))
    w("\nMilestone 2 (tenon.md §5):\n")
    w("| Goal | Status |\n|---|---|")
    frozen = "frozen seed/*" in open(os.path.join(ROOT, "ops", "governance", "guarded.txt")).read()
    ratio = self_t / seed_t if seed_t else 0
    row("Fully self-hosted compiler: fixpoint, every test on both backends, frozen seed, compile time within 3x of the bootstrap's",
        verdict(sh_ok and tests_ok and frozen and ratio <= 3,
                "fixpoint on %s files; tests failed: %s; seed frozen: %s; `emit compiler/tenon.tn` %.2f s vs the seed's %.2f s (%.2fx)"
                % (g("selfhost", 4), g("tests", 4), frozen, self_t, seed_t, ratio)))
    row("Traits (bounds, `dyn`, derived traits, coherence)",
        "implemented (docs/reference.md §17); tests/v2: %d run and %d reject tests, all passing: %s" % (v2("run"), v2("reject"), tests_ok))
    tsan_ok = bool(tsan) and tsan.get("failed", 1) == 0
    row("Multi-core: isolated workers and channels, no data races (reject tests), `par_map`, >= 3x on 4 cores, a real program uses workers",
        verdict(s4 is not None and s4 >= 3 and bool(wk_progs) and tsan_ok,
                "lowest 4-worker speedup %sx; programs with workers: %s; ThreadSanitizer %s"
                % (s4, ", ".join(wk_progs) or "none", "clean" if tsan_ok else "not clean or not run")))
    fmt_all = got["fmt"] is not None and g("fmt", 2) == "0" and g("fmt", 4) == "0"
    row("Tooling: `tenon fmt` on the whole corpus, language server, packages, VS Code",
        "formatter " + verdict(fmt_all, "%s files canonical, %s skipped by ops/gates/fmt_skip.txt" % (g("fmt", 1), g("fmt", 2)))
        + "; language server %s; packages: %s checks; editor grammar checked on %s files"
        % ("tested" if got["lsp"] else "?", g("pkg", 1), g("grammar", 1)))
    new_wave = wave is not None and wave > 6
    row("Evidence: a new usability wave without regression against wave 6; benchmarks within 1.5x of C; check <= 60 s, landing <= 5 min",
        verdict(new_wave and worst is not None and worst <= 1.5 and loop_ok,
                "latest wave %s%s; worst benchmark %sx; check %.1f s" % (wave, "" if new_wave else " (no new wave yet)", worst, total)))
    w("\nMilestone 3 (tenon.md §6) is defined; its goals are not measured here yet.\n")
    um = os.path.join(ROOT, "ops", "repo", "unmet.md")
    if os.path.exists(um):
        w("### Notes (hand-written, ops/repo/unmet.md)\n")
        w(open(um).read().strip() + "\n")

    trends(w, {"date": today, "commit": commit, "machine": MACHINE, "check_s": round(total, 1), "check_passed": passed,
               "fuzz_programs": fuzz.get("last", {}).get("programs"), "fuzz_disagreements": fuzz.get("last", {}).get("disagreements"),
               "asan_failed": asan.get("failed"), "tsan_failed": tsan.get("failed"), "mutation_score": mut.get("score"),
               "mutants_survived_last": len(mut.get("last", {}).get("survived", [])) if mut else None,
               "checkfuzz_disagreements": cfuzz.get("disagreements"), "interp_diff": idiff.get("diff"),
               "regressions": len(regressions)})
    w("## Open regressions\n")
    w("Computed from the results above (a failing check, evidence tool or unreadable summary line); the nightly"
      " workflow keeps one GitHub issue per line, labeled `regression` (docs/dev/automation.md).\n")
    w("\n".join(f"- {x['title']}" for x in regressions) if regressions else "None.")
    json.dump(regressions, open(os.path.join(EV, "regressions.json"), "w"), indent=1)
    open(os.path.join(ROOT, "STATUS.md"), "w").write("\n".join(lines) + "\n")
    print(f"STATUS.md written (check --fast {total:.1f}s, {'PASS' if passed else 'FAIL'}; {len(regressions)} open regressions)")


if __name__ == "__main__":
    main()
