#!/usr/bin/env bash
# Cross-check the self-hosted front end against the bootstrap compiler on the
# whole corpus: every .tn file, plus deliberately malformed inputs
# (tests/lex, tests/parse). Lexer: `tenon tokens`; parser: `tenon ast`.
set -euo pipefail
cd "$(dirname "$0")/.."
T=target/release/tenon
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
"$T" build selfhost/tokens.tn -o "$tmp/tokens"
"$T" build selfhost/astdump.tn -o "$tmp/astdump"
n=0; fail=0
while IFS= read -r f; do
  n=$((n+1))
  for pair in "tokens:tokens" "ast:astdump"; do
    cmd=${pair%%:*}; exe=${pair##*:}
    if ! cmp -s <("$T" "$cmd" "$f") <("$tmp/$exe" "$f"); then
      echo "FAIL self-hosted $exe disagrees on $f"; diff <("$T" "$cmd" "$f") <("$tmp/$exe" "$f") | head -5; fail=$((fail+1))
    fi
  done
done < <(find src std tests programs selfhost bench study -name '*.tn' 2>/dev/null | sort)
echo "selfhost: lexer and parser agree with the bootstrap on $n files ($fail disagreements)"
[ "$fail" = 0 ]
