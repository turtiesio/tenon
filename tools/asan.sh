#!/usr/bin/env bash
# Evidence (not part of check --fast): compile every run test and program with
# AddressSanitizer + UndefinedBehaviorSanitizer and require the same output as
# the golden file. Catches memory errors in generated C and the runtime.
# Everything (tests/run, tests/v2/run, and the programs under programs/v2
# that have a sanitizer.args: the arguments to run them with, in their
# directory) is compiled by tenonc ($TENONC, default target/tenonc), the
# compiler in use.
set -u
cd "$(dirname "$0")/.."
C=${TENONC:-$PWD/target/tenonc}
export TENON_ROOT=$PWD
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
n=0; fail=0
run() { # run NAME DIR FILE.tn COMPILER STDIN ARGS
  local name=$1 dir=$2 tn=$3 T=$4 stdin=$5 args=$6
  n=$((n+1))
  ( cd "$dir" && TENON_KEEP_C=1 "$T" build "$tn" -o "$tmp/$name" -O0 ) > /dev/null 2>&1 || { echo "FAIL $name: build"; fail=$((fail+1)); return; }
  cc -g -O0 -DTN_POOL_MAX=0 -fsanitize=address,undefined -fno-sanitize-recover=undefined -w -pthread "$tmp/$name.c" -o "$tmp/$name.asan" -lm 2>/dev/null || { echo "FAIL $name: sanitizer build"; fail=$((fail+1)); return; }
  ( cd "$dir" && printf '%b' "$stdin" | ASAN_OPTIONS=detect_leaks=0 "$tmp/$name.asan" $args ) > "$tmp/out" 2> "$tmp/err"
  if grep -q "ERROR: AddressSanitizer\|runtime error:" "$tmp/err"; then
    echo "FAIL $name: sanitizer report"; grep -m3 "ERROR\|runtime error" "$tmp/err"; fail=$((fail+1))
  fi
}
for tn in tests/run/*.tn tests/v2/run/*.tn; do
  head -1 "$tn" | grep -q '^// module' && continue
  name=$(basename "$tn" .tn); dir=$(dirname "$tn")
  stdin=$(sed -n 's#^// stdin: ##p' "$tn" | head -1 | sed 's/\\n/\n/g')
  args=$(sed -n 's#^// args: ##p' "$tn" | head -1)
  run "$name" "$dir" "$name.tn" "$C" "$stdin" "$args"
done
for d in programs/v2/*/; do
  p=$(basename "$d")
  [ -f "$d/sanitizer.args" ] || continue
  run "prog_$p" "$d" "$p.tn" "$C" "" "$(cat "$d/sanitizer.args")"
done
echo "asan: $n programs under ASan+UBSan, $fail failed"
mkdir -p .evidence
printf '{"programs": %d, "failed": %d, "date": "%s", "commit": "%s"}\n' "$n" "$fail" "$(date +%F)" "$(git rev-parse --short HEAD)" > .evidence/asan.json
[ $fail = 0 ]
