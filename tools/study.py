#!/usr/bin/env python3
"""Usability study tooling (protocol: study/README.md).

  tools/study.py kit LANG AUTHOR      create an author's isolated kit in $STUDY_ROOT
  tools/study.py eval                 score every kit: hidden tests, size, time, errors
                                      -> .evidence/study.json and study/results/

LANG is tenon, python or typescript. Kits live outside the repository
(default /tmp/tenon-study) so authors see only the task specifications and,
for Tenon, its user documentation. Every compile and run goes through the
kit's try.sh, which timestamps attempts in attempts.jsonl.
"""
import glob, json, os, re, shutil, statistics, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDY_ROOT = os.environ.get("STUDY_ROOT", "/tmp/tenon-study")
# Authors use a frozen copy of the compiler (STUDY_ROOT/bin/tenon), made when
# the first Tenon kit is created, so changes to the repo cannot affect a study.
TENON = os.path.join(STUDY_ROOT, "bin", "tenon")
EXT = {"tenon": "tn", "python": "py", "typescript": "ts"}

TRY = r'''#!/usr/bin/env bash
# try.sh TASK [ARGS...]   build (Tenon) and run your solution for TASK, logging the attempt.
# try.sh --start TASK     mark that you start working on TASK (starts its 30-minute clock)
# try.sh --done TASK      mark that your solution passes the visible examples
# try.sh --give-up TASK   mark that you stop without passing the visible examples
set -u
cd "$(dirname "$0")"
now() { python3 -c 'import time; print(time.time())'; }
log() { printf '%s\n' "$1" >> attempts.jsonl; }
case "${1:-}" in
  --start|--done|--give-up) log "{\"event\": \"${1#--}\", \"task\": \"$2\", \"t\": $(now)}"; exit 0 ;;
esac
task=$1; shift
dir=solutions/$task
LANG_KIND=__LANG__
case $LANG_KIND in
  tenon)
    if ! __TENON__ build "$dir/main.tn" -o "$dir/main" 2> "$dir/.build.err"; then
      cat "$dir/.build.err" >&2
      log "{\"event\": \"compile-error\", \"task\": \"$task\", \"t\": $(now)}"
      exit 1
    fi
    run=("$dir/main") ;;
  python) run=(python3 "$dir/main.py") ;;
  typescript) run=(node "$dir/main.ts") ;;
esac
"${run[@]}" "$@" 2> >(tee "$dir/.run.err" >&2)
code=$?
sleep 0.05
crashed=false
if grep -qE 'Traceback|trap:|TypeError|ReferenceError|SyntaxError|Error \[|at .*\.ts:' "$dir/.run.err" 2>/dev/null; then crashed=true; fi
log "{\"event\": \"run\", \"task\": \"$task\", \"t\": $(now), \"exit\": $code, \"crash\": $crashed}"
exit $code
'''


def kit(lang, author):
    d = os.path.join(STUDY_ROOT, f"{lang}-{author}")
    if os.path.exists(d):
        raise SystemExit(f"{d} exists")
    os.makedirs(os.path.join(d, "tasks"))
    for t in sorted(glob.glob(os.path.join(ROOT, "study", "tasks", "*.md"))):
        shutil.copy(t, os.path.join(d, "tasks"))
        os.makedirs(os.path.join(d, "solutions", os.path.basename(t)[:-3]))
    if lang == "tenon":
        if not os.path.exists(TENON):
            os.makedirs(os.path.dirname(TENON), exist_ok=True)
            shutil.copy(os.path.join(ROOT, "target", "release", "tenon"), TENON)
        os.makedirs(os.path.join(d, "docs"))
        shutil.copy(os.path.join(ROOT, "docs", "reference.md"), os.path.join(d, "docs", "reference.md"))
        shutil.copy(os.path.join(ROOT, "src", "prelude.tn"), os.path.join(d, "docs", "prelude.tn"))
        shutil.copy(os.path.join(ROOT, "std", "journal.tn"), os.path.join(d, "docs", "std-journal.tn"))
    open(os.path.join(d, "try.sh"), "w").write(TRY.replace("__LANG__", lang).replace("__TENON__", TENON))
    os.chmod(os.path.join(d, "try.sh"), 0o755)
    open(os.path.join(d, "attempts.jsonl"), "w").close()
    print(d)


def code_lines(path, lang):
    n, toks = 0, 0
    in_block = False
    for line in open(path, encoding="utf-8", errors="replace"):
        s = line.strip()
        if lang == "python":
            if not s or s.startswith("#"):
                continue
        else:
            if in_block:
                if "*/" in s:
                    in_block = False
                continue
            if s.startswith("/*"):
                in_block = "*/" not in s
                continue
            if not s or s.startswith("//"):
                continue
        n += 1
        toks += len(re.findall(r"[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|\S", s))
    return n, toks


def evaluate():
    rows = []
    for d in sorted(glob.glob(os.path.join(STUDY_ROOT, "*-*"))):
        lang, author = os.path.basename(d).rsplit("-", 1)
        if lang not in EXT:
            continue
        events = [json.loads(l) for l in open(os.path.join(d, "attempts.jsonl")) if l.strip()]
        for t in sorted(os.listdir(os.path.join(d, "solutions"))):
            src = os.path.join(d, "solutions", t, "main." + EXT[lang])
            ev = [e for e in events if e.get("task") == t]
            start = next((e["t"] for e in ev if e["event"] == "start"), None)
            done = next((e["t"] for e in ev if e["event"] == "done"), None)
            row = {"lang": lang, "author": author, "task": t, "exists": os.path.exists(src)}
            row["attempts"] = sum(1 for e in ev if e["event"] in ("run", "compile-error"))
            row["errors"] = sum(1 for e in ev if e["event"] == "compile-error" or e.get("crash"))
            row["minutes_to_visible"] = round((done - start) / 60, 1) if start and done else None
            if row["exists"]:
                row["lines"], row["tokens"] = code_lines(src, lang)
                if lang == "tenon":
                    exe = os.path.join(d, "solutions", t, "main")
                    subprocess.run([TENON, "build", src, "-o", exe], capture_output=True)
                    cmd = [exe]
                else:
                    cmd = ["python3", src] if lang == "python" else ["node", src]
                out = os.path.join(d, f".hidden-{t}.json")
                subprocess.run([sys.executable, os.path.join(ROOT, "study", "harness.py"), t, "--json", out, "--"] + cmd,
                               capture_output=True, cwd=ROOT)
                res = json.load(open(out)) if os.path.exists(out) else {}
                row["hidden_pass"] = res.get("passed", 0)
                row["hidden_total"] = res.get("total", 0)
            rows.append(row)
    summary = {}
    for lang in EXT:
        rs = [r for r in rows if r["lang"] == lang and r["exists"]]
        if not rs:
            continue
        per_author = {}
        for r in rs:
            a = per_author.setdefault(r["author"], {"pass": 0, "total": 0, "lines": 0, "tokens": 0, "minutes": [], "errors": 0})
            a["pass"] += r.get("hidden_pass", 0)
            a["total"] += r.get("hidden_total", 0)
            a["lines"] += r["lines"]
            a["tokens"] += r["tokens"]
            a["errors"] += r["errors"]
            if r["minutes_to_visible"] is not None:
                a["minutes"].append(r["minutes_to_visible"])
        med = lambda xs: statistics.median(xs) if xs else None
        summary[lang] = {
            "authors": len(per_author),
            "hidden_pass_rate": med([a["pass"] / a["total"] for a in per_author.values() if a["total"]]),
            "lines": med([a["lines"] for a in per_author.values()]),
            "tokens": med([a["tokens"] for a in per_author.values()]),
            "minutes_total": med([sum(a["minutes"]) for a in per_author.values()]),
            "errors": med([a["errors"] for a in per_author.values()]),
        }
    os.makedirs(os.path.join(ROOT, ".evidence"), exist_ok=True)
    lines = ["| Language | Authors | Hidden-test pass rate | Lines (sum of 10) | Tokens | Minutes to visible | Errors |", "|---|---|---|---|---|---|---|"]
    for lang, s in summary.items():
        rate = f"{s['hidden_pass_rate'] * 100:.0f}%" if s["hidden_pass_rate"] is not None else "-"
        lines.append(f"| {lang} | {s['authors']} | {rate} | {s['lines']} | {s['tokens']} | {s['minutes_total']} | {s['errors']} |")
    text = "Medians over authors (protocol: study/README.md; per-solution data: study/results/).\n\n" + "\n".join(lines)
    json.dump({"summary": text, "per_language": summary}, open(os.path.join(ROOT, ".evidence", "study.json"), "w"), indent=1)
    os.makedirs(os.path.join(ROOT, "study", "results"), exist_ok=True)
    json.dump(rows, open(os.path.join(ROOT, "study", "results", "rows.json"), "w"), indent=1)
    print(text)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "kit":
        kit(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 2 and sys.argv[1] == "eval":
        evaluate()
    else:
        print(__doc__)
