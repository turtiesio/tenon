#!/usr/bin/env bash
# The build cache of `tenon build` (selfhost/tenon.tn): a hit reuses the
# cached executable only when the cached C text is exactly the new one;
# TENON_CACHE=off and TENON_KEEP_C bypass it. Uses $TENON (default target/tenon).
set -u
cd "$(dirname "$0")/.."
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
C=${TENON:-$PWD/target/tenon}
export TENON_ROOT=$PWD TENON_CACHE=$tmp/cache
unset TENON_KEEP_C
printf 'fn main(sys: Sys) { sys.console.println("fresh") }\n' > "$tmp/p.tn"
fail=0
expect() { # expect WANT description
  got=$("$tmp/p" 2>&1)
  if [ "$got" != "$1" ]; then echo "cache_test: FAIL: $2 (got '$got')"; fail=1; fi
}
"$C" build "$tmp/p.tn" -o "$tmp/p" -O0; expect fresh "a first build compiles"
entry=$(ls "$tmp/cache" | grep -v '\.c$')
[ -f "$tmp/cache/$entry.c" ] || { echo "cache_test: FAIL: no cache entry"; fail=1; }
# a planted executable proves that a hit takes the cached one ...
printf '#!/bin/sh\necho cached\n' > "$tmp/cache/$entry"; chmod +x "$tmp/cache/$entry"
rm -f "$tmp/p"; "$C" build "$tmp/p.tn" -o "$tmp/p" -O0; expect cached "a hit copies the cached executable"
# ... but only while the cached C text is exactly the program's
echo "/* changed */" >> "$tmp/cache/$entry.c"
"$C" build "$tmp/p.tn" -o "$tmp/p" -O0; expect fresh "a different cached C text is not a hit"
printf '#!/bin/sh\necho cached\n' > "$tmp/cache/$entry"
TENON_CACHE=off "$C" build "$tmp/p.tn" -o "$tmp/p" -O0; expect fresh "TENON_CACHE=off compiles"
TENON_KEEP_C=1 "$C" build "$tmp/p.tn" -o "$tmp/p" -O0; expect fresh "TENON_KEEP_C compiles"
[ -f "$tmp/p.c" ] || { echo "cache_test: FAIL: TENON_KEEP_C did not keep p.c"; fail=1; }
[ $fail = 0 ] && echo "cache_test: tenon build cache hits only on identical C (5 scenarios)"
exit $fail
