#!/usr/bin/env bash
# The evidence loop (asynchronous, off the critical path): fuzzing,
# sanitizers, mutation testing and benchmarks against main, all on `tenon`,
# the self-hosted compiler in use, built as ./check builds it (the seed builds
# stage0, stage0 builds target/tenon at -O2); the seed ($SEED) only as
# a differential reference: its own test run of tests/, its interpreter
# against tenon's on the corpus (interp_diff), its checker and emitter
# against tenon's on mutated programs (checkfuzz), and a third opinion in
# fuzz.py. Then a regenerated STATUS.md landed through the normal path
# (EVIDENCE_LAND=0: only written; the nightly workflow opens a pull request
# instead, docs/dev/automation.md). Sizes: FUZZ_N, CHECKFUZZ_N, MUTATE_N,
# BENCH_RUNS. Each tool's whole output is kept in .evidence/NAME.log. Run
# daily; failures are reported, not hidden.
set -u
# Always run in a dedicated clone: this script resets its checkout to origin/main.
EV=${EVIDENCE_DIR:-$HOME/.tenon-evidence}
if [ "$(cd "$(dirname "$0")/../.." && pwd)" != "$EV" ]; then
  [ -d "$EV/.git" ] || git clone -q "$(cd "$(dirname "$0")/../.." && git remote get-url origin)" "$EV"
  # main's copy of this script, wherever main keeps it (it moved from tools/ on 2026-10-28)
  git -C "$EV" fetch -q origin main && git -C "$EV" checkout -q main && git -C "$EV" reset -q --hard origin/main
  exec "$EV/ops/evidence/evidence.sh" "$@"
fi
cd "$EV"
git fetch -q origin main && git checkout -q main && git reset -q --hard origin/main
export SEED=$PWD/target/release/tenon-seed TENON0=$PWD/target/tenon0 TENON=$PWD/target/tenon TENON_ROOT=$PWD
{ cargo build --release --quiet && "$SEED" build compiler/tenon.tn -o "$TENON0" -O0 &&
  "$TENON0" build compiler/tenon.tn -o "$TENON"; } || { echo "evidence: main does not build"; exit 1; }
log=.evidence/last-run.txt; mkdir -p .evidence; : > "$log"
seed=$(date +%s)
ev() { # ev NAME LINES COMMAND...: run it, keep its output in .evidence/NAME.log, its last LINES lines in the run's log
  local name=$1 lines=$2; shift 2
  "$@" > ".evidence/$name.log" 2>&1; tail -"$lines" ".evidence/$name.log" | tee -a "$log"
}
ev fuzz 3 python3 ops/evidence/fuzz.py "${FUZZ_N:-300}" "$seed"
ev asan 3 ops/evidence/asan.sh
ev tsan 3 ops/evidence/tsan.sh
ev fmt 3 ops/gates/fmt_check.sh --all
ev seed_test 1 "$SEED" test tests
tail -1 .evidence/seed_test.log |
  python3 -c 'import sys; sys.path.insert(0, "ops"); import corpus; corpus.record("seed_test", {"summary": sys.stdin.read().strip()})'
ev interp_diff 3 python3 ops/evidence/interp_diff.py
ev formal_diff 3 python3 ops/gates/formal_diff.py
ev checkfuzz 3 python3 ops/evidence/checkfuzz.py "${CHECKFUZZ_N:-500}" "$seed"
ev mutation 6 nice -n 15 python3 ops/evidence/mutate.py "${MUTATE_N:-20}" "$seed"
ev bench 100 env BENCH_RUNS="${BENCH_RUNS:-5}" python3 ops/evidence/bench.py
python3 ops/repo/status.py | tee -a "$log"
[ "${EVIDENCE_LAND:-1}" = 0 ] || ops/repo/land.sh "STATUS.md: daily evidence run $(date +%F)" | tee -a "$log"
