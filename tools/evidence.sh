#!/usr/bin/env bash
# The evidence loop (asynchronous, off the critical path): fuzzing, sanitizers,
# mutation testing and benchmarks against main, then a regenerated STATUS.md
# landed through the normal path. Run daily; failures are reported, not hidden.
set -u
# Always run in a dedicated clone: this script resets its checkout to origin/main.
EV=${EVIDENCE_DIR:-$HOME/.tenon-evidence}
if [ "$(cd "$(dirname "$0")/.." && pwd)" != "$EV" ]; then
  [ -d "$EV/.git" ] || git clone -q "$(cd "$(dirname "$0")/.." && git remote get-url origin)" "$EV"
  exec "$EV/tools/evidence.sh" "$@"
fi
cd "$EV"
git fetch -q origin main && git checkout -q main && git reset -q --hard origin/main
cargo build --release --quiet || { echo "evidence: main does not build"; exit 1; }
log=.evidence/last-run.txt; mkdir -p .evidence; : > "$log"
python3 tools/fuzz.py 300 "$(date +%s)" 2>&1 | tail -3 | tee -a "$log"
tools/asan.sh 2>&1 | tail -3 | tee -a "$log"
nice -n 15 python3 tools/mutate.py 20 "$(date +%s)" 2>&1 | tail -6 | tee -a "$log"
BENCH_RUNS=5 python3 tools/bench.py 2>&1 | tee -a "$log"
python3 tools/status.py | tee -a "$log"
tools/land.sh "STATUS.md: daily evidence run $(date +%F)" | tee -a "$log"
