#!/usr/bin/env bash
# The evidence loop (asynchronous, off the critical path): fuzzing,
# sanitizers, mutation testing and benchmarks against main, all on `tenon`,
# the self-hosted compiler in use, built as ./check builds it (the seed builds
# stage0, stage0 builds target/tenon at -O2); the seed ($SEED) only as
# a differential reference: its own test run of tests/, its interpreter
# against tenon's on the corpus (interp_diff), its checker and emitter
# against tenon's on mutated programs (checkfuzz), and a third opinion in
# fuzz.py. Then a regenerated STATUS.md landed through the normal path. Run
# daily; failures are reported, not hidden.
set -u
# Always run in a dedicated clone: this script resets its checkout to origin/main.
EV=${EVIDENCE_DIR:-$HOME/.tenon-evidence}
if [ "$(cd "$(dirname "$0")/.." && pwd)" != "$EV" ]; then
  [ -d "$EV/.git" ] || git clone -q "$(cd "$(dirname "$0")/.." && git remote get-url origin)" "$EV"
  exec "$EV/tools/evidence.sh" "$@"
fi
cd "$EV"
git fetch -q origin main && git checkout -q main && git reset -q --hard origin/main
export SEED=$PWD/target/release/tenon-seed TENON0=$PWD/target/tenon0 TENON=$PWD/target/tenon TENON_ROOT=$PWD
{ cargo build --release --quiet && "$SEED" build selfhost/tenon.tn -o "$TENON0" -O0 &&
  "$TENON0" build selfhost/tenon.tn -o "$TENON"; } || { echo "evidence: main does not build"; exit 1; }
log=.evidence/last-run.txt; mkdir -p .evidence; : > "$log"
seed=$(date +%s)
python3 tools/fuzz.py 300 "$seed" 2>&1 | tail -3 | tee -a "$log"
tools/asan.sh 2>&1 | tail -3 | tee -a "$log"
tools/tsan.sh 2>&1 | tail -3 | tee -a "$log"
tools/fmt_check.sh --all 2>&1 | tail -3 | tee -a "$log"
"$SEED" test tests 2>&1 | tail -1 | tee -a "$log" |
  python3 -c 'import sys; sys.path.insert(0, "tools"); import corpus; corpus.record("seed_test", {"summary": sys.stdin.read().strip()})'
python3 tools/interp_diff.py 2>&1 | tail -3 | tee -a "$log"
python3 tools/checkfuzz.py 500 "$seed" 2>&1 | tail -3 | tee -a "$log"
nice -n 15 python3 tools/mutate.py 20 "$seed" 2>&1 | tail -6 | tee -a "$log"
BENCH_RUNS=5 python3 tools/bench.py 2>&1 | tee -a "$log"
python3 tools/status.py | tee -a "$log"
tools/land.sh "STATUS.md: daily evidence run $(date +%F)" | tee -a "$log"
