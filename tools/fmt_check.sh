#!/usr/bin/env bash
# The formatter (selfhost/tenonfmt.tn, rules in docs/reference.md "Formatting")
# on the whole corpus:
#   1. every .tn file not listed in tools/fmt_skip.txt is in canonical layout
#      (`tenonfmt --check`);
#   2. formatting preserves meaning, on every .tn file it changes (skipped
#      ones included; with --all on every file): `tenonc ast` of the original
#      and of the formatted text are identical except positions, and so are
#      the tokens (`tenonc tokens`) except a `,` or `;` directly before a
#      closing bracket (the self-hosted parser, so v2 files are covered too;
#      tenonc is $TENONC, else built here);
#   3. formatting is idempotent: the formatted text is in canonical layout;
#   4. a file is refused (left unchanged) exactly when `tenonc ast` cannot
#      parse it; files that do not parse are exempt from 1;
#   5. tests/fmt/NAME.in.tn formats to tests/fmt/NAME.out.tn (and tests/v2/fmt).
set -euo pipefail
cd "$(dirname "$0")/.."
T=target/release/tenon
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
"$T" build selfhost/tenonfmt.tn -o "$tmp/tenonfmt"
if [ -n "${TENONC:-}" ]; then A=$TENONC; else A=$tmp/tenonc; "$T" build selfhost/tenonc.tn -o "$A" -O0; fi
python3 - "$A" "$tmp" "$@" <<'EOF'
import fnmatch, os, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

T, tmp, every = os.path.abspath(sys.argv[1]), sys.argv[2], "--all" in sys.argv
F = os.path.join(tmp, "tenonfmt")
sys.path.insert(0, "tools")
import corpus
files = corpus.files()
skip_globs = [l.split("#")[0].strip() for l in open("tools/fmt_skip.txt")]
skip_globs = [g for g in skip_globs if g]
skipped = [f for f in files if any(fnmatch.fnmatch(f, g) for g in skip_globs)]
problems = []

def run(*args, cwd=None, stdin=None):
    return subprocess.run(args, cwd=cwd, input=stdin, capture_output=True, text=True)

# format a copy of everything; a file that does not parse is refused
c = os.path.join(tmp, "c")
for f in files:
    os.makedirs(os.path.join(c, os.path.dirname(f)), exist_ok=True)
    shutil.copyfile(f, os.path.join(c, f))
r = run(F, *files, cwd=c)
refused = set(re.findall(r"^tenonfmt: (.*?\.tn):", r.stderr, re.M))
problems += [l for l in r.stderr.splitlines() if "internal error" in l or not re.match(r"^tenonfmt: .*?\.tn:", l)]
changed = [f for f in files if f not in refused and open(f, "rb").read() != open(os.path.join(c, f), "rb").read()]
# 1. canonical layout
for f in changed:
    if f not in skipped:
        problems.append(f"{f}: not in canonical layout (run: target/tenonfmt {f})")
# 3. idempotence
r = run(F, "--check", *[f for f in files if f not in refused], cwd=c)
for f in r.stdout.split():
    problems.append(f"{f}: formatting is not idempotent")

def strip_ast(s):
    return re.sub(r"@\d+:\d+ ?", "", s)

def strip_tokens(s):
    rows = [re.sub(r"^(\s*)\d+:\d+ ", r"\1", l) for l in s.splitlines()]
    rows = [re.sub(r"^(\s*spec )\d+:\d+ ", r"\1", l) for l in rows]
    pad = lambda l: l[:len(l) - len(l.lstrip())]
    out = []
    for i, l in enumerate(rows):
        if l.strip() in ("sym ,", "sym ;"):
            j = i + 1
            while j < len(rows) and rows[j].strip() in ("sym ,", "sym ;") and pad(rows[j]) == pad(l):
                j += 1
            if j < len(rows) and rows[j].strip() in ("sym )", "sym ]", "sym }") and pad(rows[j]) == pad(l):
                continue
        out.append(l)
    return out

# 2 and 4. meaning preserved (trivially so where the text is unchanged)
def same(f):
    a = run(T, "ast", f)
    parses = not a.stdout.startswith("error ")
    if f in refused:
        return [f"{f}: refused by tenonfmt, but `tenonc ast` parses it"] if parses else []
    if not parses:
        return [f"{f}: formatted by tenonfmt, but `tenonc ast` does not parse it"]
    if f not in changed and not every:
        return []
    b = run(T, "ast", os.path.join(c, f))
    out = []
    if strip_ast(a.stdout) != strip_ast(b.stdout):
        out.append(f"{f}: formatting changed the AST")
    if strip_tokens(run(T, "tokens", f).stdout) != strip_tokens(run(T, "tokens", os.path.join(c, f)).stdout):
        out.append(f"{f}: formatting changed the tokens")
    return out

with ThreadPoolExecutor(corpus.JOBS) as ex:
    for p in ex.map(same, [f for f in files if f in refused or f in changed or every]):
        problems += p

# 5. golden tests
pairs = sorted(os.path.join(d, f[:-6]) for d in ["tests/fmt", "tests/v2/fmt"] for f in os.listdir(d) if f.endswith(".in.tn"))
for name in pairs:
    src = open(f"{name}.in.tn").read()
    want = open(f"{name}.out.tn").read()
    r = run(F, "-", stdin=src)
    if r.returncode != 0 or r.stdout != want:
        problems.append(f"{name}.in.tn: does not format to {os.path.basename(name)}.out.tn{': ' + r.stderr.strip() if r.stderr else ''}")

for p in problems:
    print("FAIL", p)
canonical = [f for f in files if f not in skipped and f not in refused and f not in changed]
print(f"fmt: {len(canonical)} files in canonical layout ({len(skipped)} skipped by tools/fmt_skip.txt,",
      f"{len([f for f in refused if f not in skipped])} more do not parse); idempotent on {len(files) - len(refused)};",
      f"meaning preserved on {len(files) - len(refused) if every else len(changed)} formatted{'' if every else ' (the ones it changes)'};",
      f"{len(pairs)} golden tests; {len(problems)} problems")
sys.exit(1 if problems else 0)
EOF
