#!/usr/bin/env bash
# Cross-check the self-hosted compiler against the bootstrap compiler on the
# whole corpus: every .tn file, plus deliberately malformed inputs
# (tests/lex, tests/parse) and checker cases (tests/reject, tests/selfhost).
#   lexer:   `tenon tokens FILE`  vs `tenonc tokens FILE`
#   parser:  `tenon ast FILE`     vs `tenonc ast FILE`
#   checker: `tenon check FILE`   vs `tenonc check FILE` (selfhost/tenonc.tn):
#            the same exit status and the same first line of the diagnostic
#   emitter: `tenon emit FILE`    vs `tenonc emit FILE`, for every file the
#            bootstrap accepts: byte-identical C and the same exit status
# tenonc is $TENONC when set (./check builds it once), else built here with
# -O0 (building is most of the cost, running is cheap).
# Files under a v2/ directory (lib/v2, tests/v2) use syntax only tenonc has
# (traits): they are skipped here and checked by `tenonc test tests/v2`.
set -euo pipefail
cd "$(dirname "$0")/.."
T=target/release/tenon
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
if [ -n "${TENONC:-}" ]; then cp "$TENONC" "$tmp/tenonc"; else "$T" build selfhost/tenonc.tn -o "$tmp/tenonc" -O0; fi

# One job per file, run in parallel; each prints FAIL lines and one result word.
one() {
  f=$1; T=$2; tmp=$3; out=""
  for cmd in tokens ast; do
    if ! cmp -s <("$T" "$cmd" "$f") <("$tmp/tenonc" "$cmd" "$f"); then
      echo "FAIL self-hosted $cmd disagrees on $f"; diff <("$T" "$cmd" "$f") <("$tmp/tenonc" "$cmd" "$f") | head -5; out=fail
    fi
  done
  e=$(mktemp)
  set +e
  "$T" check "$f" > /dev/null 2> "$e"; sa=$?
  want="exit $sa: $(head -n 1 "$e")"
  "$tmp/tenonc" check "$f" > /dev/null 2> "$e"; sb=$?
  got="exit $sb: $(head -n 1 "$e")"
  set -e
  rm -f "$e"
  if [ $sa = 0 ]; then kind=accepted; else kind=rejected; fi
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
find bootstrap lib tests programs selfhost bench study -name '*.tn' -not -path '*/v2/*' 2>/dev/null | sort \
  | xargs -P 8 -I{} bash -c 'one "$@"' _ {} "$T" "$tmp" > "$tmp/results"
# every builtin of the prelude is known to the self-hosted interpreter
python3 - >> "$tmp/results" <<'EOF'
import re
names = re.findall(r"^extern fn ([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?(?:\.[a-z_][A-Za-z0-9_]*)?)", open("lib/prelude.tn").read(), re.M)
known = open("selfhost/ibuiltin.tn").read() + open("selfhost/icap.tn").read()
for n in names:
    n = re.sub(r"\[[^\]]*\]", "", n)
    if n != "decode" and f'"{n}"' not in known:
        print(f"FAIL the self-hosted interpreter has no builtin {n} (selfhost/ibuiltin.tn, icap.tn)")
EOF
grep -v '^RESULT ' "$tmp/results" || true
n=$(grep -c '^RESULT ' "$tmp/results")
accepted=$(grep -c '^RESULT accepted' "$tmp/results" || true)
rejected=$(grep -c '^RESULT rejected' "$tmp/results" || true)
fail=$(grep -c '^FAIL ' "$tmp/results" || true)
echo "selfhost: lexer and parser agree with the bootstrap on $n files;" \
  "checker on $n ($accepted accepted, $rejected rejected); emitter on the $accepted accepted; $fail disagreements"
[ "$fail" = 0 ]
