#!/usr/bin/env bash
# The proof gate (tenon.md §6, formal/README.md): `lake build` of formal/
# (the core, its evaluator, the translator and every proof) must succeed;
# no file it builds may contain `sorry`, `admit` or a new `axiom`; and every
# theorem of formal/TenonCore/Theorems.lean (the guarded statements) may depend
# only on Lean's standard axioms. The Lean toolchain is formal/lean-toolchain
# (elan installs it: formal/README.md, "How to run"). Unfinished statements
# go to the Todo library (formal/Todo.lean), which is not built here.
set -euo pipefail
cd "$(dirname "$0")/../../formal"
lake=$(command -v lake || true)
[ -n "$lake" ] || lake="$HOME/.elan/bin/lake"
if [ ! -x "$lake" ]; then
  echo "formal_check: no Lean toolchain (lake); install elan: formal/README.md, \"How to run\""
  exit 1
fi
if ! "$lake" build > ../target/formal_build.log 2>&1; then
  tail -40 ../target/formal_build.log
  echo "formal_check: lake build failed (whole log: target/formal_build.log)"
  exit 1
fi
if grep -q "declaration uses 'sorry'\|declaration uses \`sorry\`" ../target/formal_build.log; then
  grep "sorry" ../target/formal_build.log | head
  echo "formal_check: a proof uses sorry"
  exit 1
fi
# the sources the build checks: the core, the translator, the runner
srcs=$(find TenonCore Front -name '*.lean'; echo TenonCore.lean Front.lean Main.lean)
if grep -nE '(^|[^A-Za-z_.])(sorry|admit)([^A-Za-z_]|$)|^[[:space:]]*(axiom|unsafe axiom)[[:space:]]' $srcs; then
  echo "formal_check: sorry, admit or axiom in a built file (unfinished statements go to the Todo library, formal/Todo.lean)"
  exit 1
fi
out=$("$lake" env lean Axioms.lean 2>&1)
n=$(printf "%s\n" "$out" | grep -cE "depends on axioms|does not depend on any axioms" || true)
bad=$(printf '%s\n' "$out" | grep "depends on axioms" | grep -vE "depends on axioms: \[(propext|Classical.choice|Quot.sound)(, (propext|Classical.choice|Quot.sound))*\]$" || true)
if [ "$n" -lt 27 ] || [ -n "$bad" ] || printf '%s\n' "$out" | grep -q "error"; then
  printf '%s\n' "$out"
  echo "formal_check: a guarded theorem depends on a non-standard axiom (or did not check)"
  exit 1
fi
echo "formal_check: formal/ builds; no sorry; $n guarded theorems use only propext, Classical.choice, Quot.sound"
