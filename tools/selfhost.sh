#!/usr/bin/env bash
# Cross-check of the self-hosted compiler (selfhost/tenon.tn) against the
# seed (the frozen bootstrap), and its fixpoint, in one parallel pass over the
# corpus (tools/corpus.py), deliberately malformed inputs (tests/lex,
# tests/parse) and checker cases (tests/reject, tests/selfhost) included:
#   stage0 = the seed building tenon.tn       ($TENON0; ./check: target/tenon0)
#   stage1 = stage0 building tenon.tn         ($TENON;  ./check: target/tenon)
# Every file outside v2/ directories (the seed cannot read those), seed vs
# stage1:
#   lexer:   `$SEED tokens FILE`  vs `tenon tokens FILE`
#   parser:  `$SEED ast FILE`     vs `tenon ast FILE`
#   checker: `$SEED check FILE`   vs `tenon check FILE`: the same exit status
#            and the same first line of the diagnostic
#   emitter: `$SEED emit FILE`    vs `tenon emit FILE`, for every file the
#            seed accepts: byte-identical C and the same exit status
# Fixpoint, every file stage1 accepts (v2 files included): stage0 and stage1
# emit byte-identical C. selfhost/tenon.tn is one of them, so the seed,
# stage0 and stage1 print the same C for the compiler itself.
# Without $TENON0/$TENON both stages are built here with -O0 (building is
# most of the cost, running is cheap).
set -euo pipefail
cd "$(dirname "$0")/.."
S=${SEED:-target/release/tenon-seed}
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
if [ -n "${TENON0:-}" ]; then cp "$TENON0" "$tmp/stage0"; else "$S" build selfhost/tenon.tn -o "$tmp/stage0" -O0; fi
if [ -n "${TENON:-}" ]; then cp "$TENON" "$tmp/stage1"; else TENON_ROOT=$PWD "$tmp/stage0" build selfhost/tenon.tn -o "$tmp/stage1" -O0; fi

# One job per file, run in parallel; each prints FAIL lines and one result line.
one() {
  f=$1; S=$2; tmp=$3; C0=$tmp/stage0; C1=$tmp/stage1; out=""
  a=$(mktemp); b=$(mktemp); e=$(mktemp)
  set +e
  case "$f" in
    */v2/*)
      "$C1" check "$f" > /dev/null 2>&1; s1=$?; kind=v2 ;;
    *)
      for cmd in tokens ast; do
        "$S" "$cmd" "$f" > "$a"; "$C1" "$cmd" "$f" > "$b"
        if ! cmp -s "$a" "$b"; then echo "FAIL self-hosted $cmd disagrees on $f"; diff "$a" "$b" | head -5; out=fail; fi
      done
      "$S" check "$f" > /dev/null 2> "$e"; s0=$?
      want="exit $s0: $(head -n 1 "$e")"
      "$C1" check "$f" > /dev/null 2> "$e"; s1=$?
      got="exit $s1: $(head -n 1 "$e")"
      if [ "$want" != "$got" ]; then
        echo "FAIL self-hosted check disagrees on $f"; echo "  seed:     $want"; echo "  selfhost: $got"; out=fail
      fi
      if [ $s0 = 0 ]; then kind=accepted; else kind=rejected; fi
      if [ $kind = accepted ]; then
        "$S" emit "$f" > "$a" 2> /dev/null; sa=$?
        "$C1" emit "$f" > "$b" 2> /dev/null; sb=$?
        if [ $sa != $sb ] || ! cmp -s "$a" "$b"; then
          echo "FAIL self-hosted emit disagrees on $f (exit $sa vs $sb)"; diff "$a" "$b" | head -5; out=fail
        fi
      fi ;;
  esac
  fix=-
  if [ $s1 = 0 ]; then
    "$C1" emit "$f" > "$b" 2> /dev/null; sb=$?
    "$C0" emit "$f" > "$a" 2> /dev/null; sa=$?
    if [ $sa != $sb ] || ! cmp -s "$a" "$b"; then echo "FAIL fixpoint: stage0 and stage1 emit different C for $f"; diff "$a" "$b" | head -5; out=fail; else fix=same; fi
    [ "$f" = selfhost/tenon.tn ] && echo "SELF $(wc -c < "$b" | tr -d ' ') $fix"
  fi
  set -e
  rm -f "$a" "$b" "$e"
  echo "RESULT $kind ${out:-ok} $fix"
}
export -f one
python3 tools/corpus.py | xargs -P "$(python3 tools/corpus.py --jobs)" -I{} bash -c 'one "$@"' _ {} "$S" "$tmp" > "$tmp/results"
# every builtin of the prelude (and of lib/v2/prelude.tn) is known to the self-hosted interpreter
python3 - >> "$tmp/results" <<'EOF'
import re
prelude = open("lib/prelude.tn").read() + open("lib/v2/prelude.tn").read()
names = re.findall(r"^extern fn ([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?(?:\.[a-z_][A-Za-z0-9_]*)?)", prelude, re.M)
known = open("selfhost/ibuiltin.tn").read() + open("selfhost/icap.tn").read() + open("selfhost/iwork.tn").read()
for n in names:
    n = re.sub(r"\[[^\]]*\]", "", n)
    if n != "decode" and f'"{n}"' not in known:
        print(f"FAIL the self-hosted interpreter has no builtin {n} (selfhost/ibuiltin.tn, icap.tn, iwork.tn)")
EOF
grep -v '^RESULT \|^SELF ' "$tmp/results" || true
count() { grep -c "$1" "$tmp/results" || true; }
n=$(count '^RESULT \(accepted\|rejected\)'); accepted=$(count '^RESULT accepted'); rejected=$(count '^RESULT rejected')
same=$(count '^RESULT .* same$'); fail=$(count '^FAIL ')
self=$(grep '^SELF ' "$tmp/results" || true)
if [ "${self##* }" != same ]; then echo "FAIL fixpoint: selfhost/tenon.tn was not compared (stage1 rejects it?)"; fail=$((fail + 1)); fi
echo "selfhost: lexer, parser and checker agree with the seed on $n files ($accepted accepted, $rejected rejected);" \
  "emitter on the $accepted accepted; fixpoint: stage0 = stage1 on $same accepted files, v2 included" \
  "(selfhost/tenon.tn: $(echo "$self" | cut -d' ' -f2) bytes of C); $fail disagreements"
[ "$fail" = 0 ]
