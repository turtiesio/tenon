#!/usr/bin/env bash
# Cross-check the self-hosted front end against the bootstrap compiler on the
# whole corpus: every .tn file, plus deliberately malformed inputs
# (tests/lex, tests/parse) and checker cases (tests/reject, tests/selfhost).
#   lexer:   `tenon tokens FILE`  vs selfhost/tokens.tn
#   parser:  `tenon ast FILE`     vs selfhost/astdump.tn
#   checker: `tenon check FILE`   vs selfhost/check.tn: `ok` when the bootstrap
#            accepts the program, else the first line of its diagnostic
set -euo pipefail
cd "$(dirname "$0")/.."
T=target/release/tenon
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
"$T" build selfhost/tokens.tn -o "$tmp/tokens"
"$T" build selfhost/astdump.tn -o "$tmp/astdump"
"$T" build selfhost/check.tn -o "$tmp/check"

# Files where exact checker agreement is unreasonable because of a bootstrap
# quirk; each entry points to a note in selfhost/CHECKER_NOTES.md.
skip_check=" "

n=0; fail=0; checked=0; accepted=0; rejected=0
while IFS= read -r f; do
  n=$((n+1))
  for pair in "tokens:tokens" "ast:astdump"; do
    cmd=${pair%%:*}; exe=${pair##*:}
    if ! cmp -s <("$T" "$cmd" "$f") <("$tmp/$exe" "$f"); then
      echo "FAIL self-hosted $exe disagrees on $f"; diff <("$T" "$cmd" "$f") <("$tmp/$exe" "$f") | head -5; fail=$((fail+1))
    fi
  done
  case "$skip_check" in *" $f "*) continue ;; esac
  if "$T" check "$f" > /dev/null 2> "$tmp/err"; then
    want=ok; accepted=$((accepted+1))
  else
    want=$(head -n 1 "$tmp/err"); rejected=$((rejected+1))
  fi
  got=$("$tmp/check" "$f" 2>&1 | head -n 1 || true)
  checked=$((checked+1))
  if [ "$want" != "$got" ]; then
    echo "FAIL self-hosted check disagrees on $f"; echo "  bootstrap: $want"; echo "  selfhost:  $got"; fail=$((fail+1))
  fi
done < <(find src std tests programs selfhost bench study -name '*.tn' 2>/dev/null | grep -v '^tests/pending-reject/' | sort)
echo "selfhost: lexer and parser agree with the bootstrap on $n files;" \
  "checker on $checked ($accepted accepted, $rejected rejected); $fail disagreements"
[ "$fail" = 0 ]
