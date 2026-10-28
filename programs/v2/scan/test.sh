#!/usr/bin/env bash
# Scenario test; $RUN is the command that runs the program (interpreter or binary).
set -u
D=$(mktemp -d)
trap 'rm -rf "$D"' EXIT
cd "$D"
show() { printf '$ scan'; for a in "$@"; do printf ' %q' "$a"; done; }
step() { show "$@"; echo; $RUN "$@" 2>&1; echo "[exit $?]"; }

mkdir -p tree/docs/deep tree/src tree/.git empty
cat > tree/README.md <<'EOF'
# Tenon
Tenon joins pieces of wood: a tenon fits a mortise.
The mortise and tenon joint is old, strong and simple.
EOF
cat > tree/docs/guide.txt <<'EOF'
Cut the mortise first, then the tenon.
A loose tenon is a separate piece.

Glue the joint; clamp it; wait.
EOF
cat > tree/docs/deep/notes.txt <<'EOF'
dovetail, finger joint, mortise and tenon
EOF
printf 'fn main() {\n    // TODO: tenon\n}\n' > tree/src/main.tn
printf 'no final newline: Tenon' > tree/src/tail.txt
printf 'secret tenon\n' > tree/.git/config
printf 'bad \377 byte\n' > tree/docs/binary.dat
# a larger file, so that several workers have work
for i in $(seq 1 300); do if [ $((i % 50)) = 0 ]; then echo "line $i: alpha beta, tenon"; else echo "line $i: alpha beta gamma"; fi; done > tree/src/gen.txt

echo "# stats"
step stats tree
step -j 1 stats tree
step -j 3 stats tree/docs
step stats empty

echo "# grep"
step grep tenon tree
step -j 2 grep -i TENON tree/docs
step -j 4 grep "line 15" tree
step grep nothing-matches tree

echo "# top"
step top 5 tree
step -j 2 top 3 tree/docs

echo "# errors"
step
step stats
step -j 0 stats tree
step -j x stats tree
step top 0 tree
step grep -x a tree
step stats missing
