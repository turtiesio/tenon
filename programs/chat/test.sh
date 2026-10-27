#!/usr/bin/env bash
set -u
D=$(mktemp -d); pid=
trap '[ -n "$pid" ] && kill $pid 2>/dev/null; rm -rf "$D"' EXIT
$RUN 0 > "$D/out" 2>&1 & pid=$!
for _ in $(seq 100); do grep -q listening "$D/out" 2>/dev/null && break; sleep 0.05; done
port=$(sed -n 's/^listening on \([0-9]*\).*/\1/p' "$D/out")
python3 "$(dirname "$0")/client.py" "$port"
wait $pid; echo "[server exit $?]"; pid=
