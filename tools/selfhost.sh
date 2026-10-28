#!/usr/bin/env bash
# Cross-check the self-hosted compiler against the bootstrap compiler on the
# whole corpus: every .tn file, plus deliberately malformed inputs
# (tests/lex, tests/parse) and checker cases (tests/reject, tests/selfhost).
#   lexer:   `tenon tokens FILE`  vs selfhost/tokens.tn
#   parser:  `tenon ast FILE`     vs selfhost/astdump.tn
#   checker: `tenon check FILE`   vs `tenonc check FILE` (selfhost/tenonc.tn):
#            `ok` when the bootstrap accepts the program, else the first line
#            of its diagnostic
#   emitter: `tenon emit FILE`    vs `tenonc emit FILE`, for every file the
#            bootstrap accepts: byte-identical C and the same exit status
# The tools are built with -O0: building is most of the cost, running is cheap.
set -euo pipefail
cd "$(dirname "$0")/.."
T=target/release/tenon
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
"$T" build selfhost/tokens.tn -o "$tmp/tokens" -O0 & p1=$!
"$T" build selfhost/astdump.tn -o "$tmp/astdump" -O0 & p2=$!
"$T" build selfhost/tenonc.tn -o "$tmp/tenonc" -O0 & p3=$!
wait $p1; wait $p2; wait $p3

# One job per file, run in parallel; each prints FAIL lines and one result word.
one() {
  f=$1; T=$2; tmp=$3; out=""
  for pair in "tokens:tokens" "ast:astdump"; do
    cmd=${pair%%:*}; exe=${pair##*:}
    if ! cmp -s <("$T" "$cmd" "$f") <("$tmp/$exe" "$f"); then
      echo "FAIL self-hosted $exe disagrees on $f"; diff <("$T" "$cmd" "$f") <("$tmp/$exe" "$f") | head -5; out=fail
    fi
  done
  e=$(mktemp)
  if "$T" check "$f" > /dev/null 2> "$e"; then want=ok; kind=accepted; else want=$(head -n 1 "$e"); kind=rejected; fi
  rm -f "$e"
  got=$("$tmp/tenonc" check "$f" 2>&1 | head -n 1 || true)
  if [ "$want" != "$got" ]; then
    echo "FAIL self-hosted check disagrees on $f"; echo "  bootstrap: $want"; echo "  selfhost:  $got"; out=fail
  fi
  if [ $kind = accepted ]; then
    a=$(mktemp); b=$(mktemp)
    set +e
    "$T" emit "$f" > "$a" 2> /dev/null; sa=$?
    "$tmp/tenonc" emit "$f" > "$b" 2> /dev/null; sb=$?
    set -e
    if [ $sa != $sb ] || ! cmp -s "$a" "$b"; then
      echo "FAIL self-hosted emit disagrees on $f (exit $sa vs $sb)"; diff "$a" "$b" | head -5; out=fail
    fi
    rm -f "$a" "$b"
  fi
  echo "RESULT $kind ${out:-ok}"
}
export -f one
find bootstrap lib tests programs selfhost bench study -name '*.tn' 2>/dev/null | sort \
  | xargs -P 8 -I{} bash -c 'one "$@"' _ {} "$T" "$tmp" > "$tmp/results"
grep -v '^RESULT ' "$tmp/results" || true
n=$(grep -c '^RESULT ' "$tmp/results")
accepted=$(grep -c '^RESULT accepted' "$tmp/results" || true)
rejected=$(grep -c '^RESULT rejected' "$tmp/results" || true)
fail=$(grep -c '^FAIL ' "$tmp/results" || true)
echo "selfhost: lexer and parser agree with the bootstrap on $n files;" \
  "checker on $n ($accepted accepted, $rejected rejected); emitter on the $accepted accepted; $fail disagreements"
[ "$fail" = 0 ]
