#!/usr/bin/env bash
set -u
D=$(mktemp -d); pid=
trap '[ -n "$pid" ] && kill $pid 2>/dev/null; rm -rf "$D"' EXIT
start() {
  $RUN "$D/data" 0 > "$D/out" 2>&1 & pid=$!
  for _ in $(seq 100); do grep -q listening "$D/out" 2>/dev/null && break; sleep 0.05; done
  port=$(sed -n 's/^listening on \([0-9]*\).*/\1/p' "$D/out")
  sed 's/on [0-9]*/on PORT/' "$D/out"
}
req() { echo "\$ $*" | sed "s/:$port/:PORT/"; curl -s -o "$D/body" -w "%{http_code}" "$@" | sed 's/$/ /'; cat "$D/body"; echo; }
start
req -X PUT --data-binary 'hello world' "http://127.0.0.1:$port/kv/greeting"
req "http://127.0.0.1:$port/kv/greeting"
req -X PUT --data-binary 'two' "http://127.0.0.1:$port/kv/greeting"
req -X PUT --data-binary $'multi\nline {x} "q"' "http://127.0.0.1:$port/kv/odd"
req "http://127.0.0.1:$port/kv/missing"
req -X DELETE "http://127.0.0.1:$port/kv/missing"
req -X PATCH "http://127.0.0.1:$port/kv/greeting"
req "http://127.0.0.1:$port/stats"
echo "# crash: kill -9, then restart; acknowledged writes survive"
kill -9 $pid; wait $pid 2>/dev/null; pid=
start
req "http://127.0.0.1:$port/kv/greeting"
req "http://127.0.0.1:$port/kv/odd"
req -X DELETE "http://127.0.0.1:$port/kv/greeting"
req "http://127.0.0.1:$port/kv/greeting"
req -X POST "http://127.0.0.1:$port/shutdown"
wait $pid; echo "[server exit $?]"; pid=
