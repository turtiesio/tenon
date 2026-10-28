#!/usr/bin/env bash
# Evidence (not part of check --fast): compile every v2 run test (workers,
# channels, traits) and every program that starts workers with
# ThreadSanitizer, run each RUNS times (default 3: races depend on
# scheduling), and require no ThreadSanitizer report and the exit status of
# the golden file. Built by `tenon` ($TENON, default target/tenon) with the
# runtime's normal allocator (free lists on), as programs run.
set -u
cd "$(dirname "$0")/.."
C=${TENON:-$PWD/target/tenon}
RUNS=${RUNS:-3}
export TENON_ROOT=$PWD
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
n=0; fail=0; failures=""; runs=0
bad() { echo "FAIL $1"; failures+="\"$1\","; fail=$((fail+1)); } # a failure, also named in the JSON
check() { # check NAME DIR FILE.tn EXPECTED_STATUS STDIN ARGS
  local name=$1 dir=$2 tn=$3 want=$4 stdin=$5 args=$6
  n=$((n+1))
  ( cd "$dir" && TENON_KEEP_C=1 "$C" build "$tn" -o "$tmp/$name" -O0 ) > /dev/null 2>&1 || { bad "$name: build"; return; }
  cc -g -O1 -fsanitize=thread -w -std=gnu11 -pthread "$tmp/$name.c" -o "$tmp/$name.tsan" -lm 2>/dev/null || { bad "$name: sanitizer build"; return; }
  for _ in $(seq "$RUNS"); do
    runs=$((runs+1))
    ( cd "$dir" && printf '%b' "$stdin" | TSAN_OPTIONS=halt_on_error=1 "$tmp/$name.tsan" $args ) > "$tmp/out" 2> "$tmp/err"
    local st=$?
    if grep -q "ThreadSanitizer" "$tmp/err"; then
      bad "$name: ThreadSanitizer report"; grep -m5 "WARNING\|SUMMARY\|#[0-3] " "$tmp/err"; return
    fi
    if [ "$st" != "$want" ]; then bad "$name: exit $st, expected $want"; head -3 "$tmp/err"; return; fi
  done
}
for tn in tests/v2/run/*.tn; do
  head -1 "$tn" | grep -q '^// module' && continue
  name=$(basename "$tn" .tn)
  # ThreadSanitizer cannot run a stack overflow to its end (asan.sh covers it)
  grep -q "stack overflow" "tests/v2/run/$name.out" && continue
  want=$(sed -n 's/^exit: //p' "tests/v2/run/$name.out" | head -1)
  stdin=$(sed -n 's#^// stdin: ##p' "$tn" | head -1)
  args=$(sed -n 's#^// args: ##p' "$tn" | head -1)
  check "$name" tests/v2/run "$name.tn" "${want:-0}" "$stdin" "$args"
done
# programs with workers: their scenario (programs/NAME/test.sh) is run by
# tools/programs.sh; here the main file with the inputs its sanitizer.args names
for d in programs/*/ programs/v2/*/; do
  p=$(basename "$d")
  [ -f "$d/sanitizer.args" ] || continue
  check "prog_$p" "$d" "$p.tn" 0 "" "$(cat "$d/sanitizer.args")"
done
echo "tsan: $n programs under ThreadSanitizer ($runs runs), $fail failed"
mkdir -p .evidence
printf '{"programs": %d, "runs": %d, "failed": %d, "failures": [%s], "date": "%s", "commit": "%s"}\n' "$n" "$runs" "$fail" "${failures%,}" "$(date +%F)" "$(git rev-parse --short HEAD)" > .evidence/tsan.json
[ $fail = 0 ]
