#!/usr/bin/env bash
# Scenario test; $RUN is the command that runs the program (interpreter or binary).
set -u
D=$(mktemp -d)
trap 'rm -rf "$D"' EXIT
step() { echo "\$ ledger $*"; $RUN "$D" "$@" 2>&1; echo "[exit $?]"; }
step open alice
step open bob
step open alice
step transfer t1 mint alice 100
step transfer t2 alice bob 30
step transfer t2 alice bob 30
step transfer t3 bob alice 999
step transfer t4 bob carol 1
step transfer t5 alice bob -5
step transfer t6 alice bob x
step balance alice
step balance nobody
step bogus
echo "# crash: torn final record"
printf 'transfer t7 mint bob 5 #12' >> "$D/journal"
step report
step transfer t8 mint bob 1
step report
echo "# crash: corrupted record in the middle is skipped, never misapplied"
sed -i.bak 's/transfer t2 alice bob 30/transfer t2 alice bob 99/' "$D/journal"
step report
echo "# archived records:"
cat "$D/journal.rejected"
