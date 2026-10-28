#!/usr/bin/env bash
# Real programs (programs/NAME/NAME.tn, and programs/v2/NAME/NAME.tn for the
# ones using workers) with scenario tests (programs/NAME/test.sh), run by $TENON
# (default target/tenon).
# Each scenario runs against the interpreter AND the native build; both
# transcripts must equal programs/NAME/expected.txt. `--bless` rewrites it.
set -euo pipefail
cd "$(dirname "$0")/../.."
C=${TENON:-$PWD/target/tenon}
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
fail=0; n=0
for dir in programs/*/ programs/v2/*/; do
  name=$(basename "$dir"); src="$dir$name.tn"; [ -f "$src" ] || continue
  n=$((n+1))
  "$C" build "$src" -o "$tmp/$name" -O0
  # each scenario gets 60 s; the alarm kills it rather than hanging the check
  # (SIGALRM reset to default: an inherited "ignore" would disable the timeout)
  RUN="$C run $PWD/$src" perl -e '$SIG{ALRM}="DEFAULT"; alarm 60; exec @ARGV' bash "$dir/test.sh" > "$tmp/$name.interp" 2>&1 || true
  RUN="$tmp/$name" perl -e '$SIG{ALRM}="DEFAULT"; alarm 60; exec @ARGV' bash "$dir/test.sh" > "$tmp/$name.native" 2>&1 || true
  if ! cmp -s "$tmp/$name.interp" "$tmp/$name.native"; then
    echo "FAIL $name: backends disagree"; diff "$tmp/$name.interp" "$tmp/$name.native" | head -20; fail=1; continue
  fi
  if [ "${1:-}" = "--bless" ]; then cp "$tmp/$name.native" "$dir/expected.txt"; fi
  if ! cmp -s "$tmp/$name.native" "$dir/expected.txt"; then
    echo "FAIL $name: transcript differs from expected.txt"; diff "$dir/expected.txt" "$tmp/$name.native" | head -20; fail=1
  fi
done
echo "programs: $n scenario(s) x2 backends, $([ $fail = 0 ] && echo 0 || echo some) failed"
exit $fail
