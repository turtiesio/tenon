#!/usr/bin/env bash
# Cross-check the self-hosted front end against the bootstrap compiler on the
# whole corpus: every .tn file, plus deliberately malformed inputs (tests/lex).
set -euo pipefail
cd "$(dirname "$0")/.."
T=target/release/tenon
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
"$T" build selfhost/tokens.tn -o "$tmp/tokens"
n=0; fail=0
while IFS= read -r f; do
  n=$((n+1))
  if ! cmp -s <("$T" tokens "$f") <("$tmp/tokens" "$f"); then
    echo "FAIL lexer disagrees on $f"; diff <("$T" tokens "$f") <("$tmp/tokens" "$f") | head -5; fail=1
  fi
done < <(find src std tests programs selfhost bench study -name '*.tn' 2>/dev/null | sort)
echo "selfhost: lexer agrees on $((n - fail)) of $n files"
exit $fail
