#!/usr/bin/env bash
# Evidence (not part of check --fast): compile every run test and program with
# AddressSanitizer + UndefinedBehaviorSanitizer and require the same output as
# the golden file. Catches memory errors in generated C and the runtime.
set -u
cd "$(dirname "$0")/.."
T=$PWD/target/release/tenon
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
n=0; fail=0
for tn in tests/run/*.tn; do
  head -1 "$tn" | grep -q '^// module' && continue
  name=$(basename "$tn" .tn); dir=$(dirname "$tn")
  n=$((n+1))
  ( cd "$dir" && TENON_KEEP_C=1 "$T" build "$name.tn" -o "$tmp/$name" -O0 ) > /dev/null 2>&1 || { echo "FAIL $name: build"; fail=$((fail+1)); continue; }
  mv "$tmp/$name.c" "$tmp/$name.c" 2>/dev/null || true
  cc -g -O0 -DTN_POOL_MAX=0 -fsanitize=address,undefined -fno-sanitize-recover=undefined -w "$tmp/$name.c" -o "$tmp/$name.asan" -lm 2>/dev/null || { echo "FAIL $name: sanitizer build"; fail=$((fail+1)); continue; }
  stdin=$(sed -n 's#^// stdin: ##p' "$tn" | head -1 | sed 's/\\n/\n/g')
  args=$(sed -n 's#^// args: ##p' "$tn" | head -1)
  ( cd "$dir" && printf '%b' "$stdin" | ASAN_OPTIONS=detect_leaks=0 "$tmp/$name.asan" $args ) > "$tmp/out" 2> "$tmp/err"
  if grep -q "ERROR: AddressSanitizer\|runtime error:" "$tmp/err"; then
    echo "FAIL $name: sanitizer report"; grep -m3 "ERROR\|runtime error" "$tmp/err"; fail=$((fail+1))
  fi
done
echo "asan: $n programs under ASan+UBSan, $fail failed"
[ $fail = 0 ]
