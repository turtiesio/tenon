#!/usr/bin/env bash
# Self-compilation fixpoint of the self-hosted compiler (selfhost/tenonc.tn):
#   stage1 = the bootstrap compiling tenonc.tn       (tenon build)
#   stage2 = stage1 compiling tenonc.tn              (stage1 build)
# Then stage1's and stage2's `emit selfhost/tenonc.tn` must be byte-identical
# to each other and to `tenon emit selfhost/tenonc.tn`, and stage2 must emit
# the same C as stage1 for every corpus file the bootstrap accepts (stage1
# itself is compared with the bootstrap on the corpus by tools/selfhost.sh).
# Built with -O0 (fast to build); the C is the same at any -O level.
set -euo pipefail
cd "$(dirname "$0")/.."
T=target/release/tenon
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
"$T" build selfhost/tenonc.tn -o "$tmp/stage1" -O0
"$tmp/stage1" build selfhost/tenonc.tn -o "$tmp/stage2" -O0
"$T" emit selfhost/tenonc.tn > "$tmp/boot.c"
"$tmp/stage1" emit selfhost/tenonc.tn > "$tmp/stage1.c"
"$tmp/stage2" emit selfhost/tenonc.tn > "$tmp/stage2.c"
if ! cmp -s "$tmp/stage1.c" "$tmp/stage2.c"; then
  echo "FAIL fixpoint: stage1 and stage2 emit different C for selfhost/tenonc.tn"; diff "$tmp/stage1.c" "$tmp/stage2.c" | head -5
  exit 1
fi
if ! cmp -s "$tmp/boot.c" "$tmp/stage1.c"; then
  echo "FAIL fixpoint: the bootstrap and stage1 emit different C for selfhost/tenonc.tn"; diff "$tmp/boot.c" "$tmp/stage1.c" | head -5
  exit 1
fi

one() {
  f=$1; tmp=$2
  "$tmp/stage1" check "$f" > /dev/null 2>&1 || return 0
  set +e
  "$tmp/stage1" emit "$f" > "$tmp/$$.1" 2> /dev/null; s1=$?
  "$tmp/stage2" emit "$f" > "$tmp/$$.2" 2> /dev/null; s2=$?
  set -e
  if [ $s1 != $s2 ] || ! cmp -s "$tmp/$$.1" "$tmp/$$.2"; then echo "FAIL stage2 disagrees with stage1 on $f"; else echo "SAME"; fi
  rm -f "$tmp/$$.1" "$tmp/$$.2"
}
export -f one
find bootstrap lib tests programs selfhost bench study -name '*.tn' 2>/dev/null | sort \
  | xargs -P 8 -I{} bash -c 'one "$@"' _ {} "$tmp" > "$tmp/results"
grep '^FAIL' "$tmp/results" || true
fail=$(grep -c '^FAIL' "$tmp/results" || true)
same=$(grep -c '^SAME' "$tmp/results" || true)
echo "fixpoint: stage1 = stage2 = bootstrap on selfhost/tenonc.tn ($(wc -c < "$tmp/boot.c" | tr -d ' ') bytes of C);" \
  "stage2 = stage1 on $same accepted corpus files; $fail disagreements"
[ "$fail" = 0 ]
