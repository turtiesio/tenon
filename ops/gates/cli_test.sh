#!/usr/bin/env bash
# The command line (compiler/tenon.tn, docs/tools.md) through $TENON (default
# target/tenon): usage and exit statuses, flags in any position, unknown
# flags and extra arguments refused, `run` passing its program's flags
# through; and ops/repo/install.sh into a scratch prefix, whose `tenon` (found
# on PATH, run elsewhere, without $TENON_ROOT) finds its root from its own
# path and runs `tenon test` on a small suite (it runs itself).
set -u
cd "$(dirname "$0")/../.."
REPO=$PWD
C=${TENON:-$REPO/target/tenon}
case $C in /*) ;; *) C=$REPO/$C ;; esac
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
fail=0; n=0
expect() { # expect STATUS TEXT COMMAND...: the status, and TEXT in its output (stdout + stderr)
  local want=$1 text=$2 out status; shift 2
  n=$((n + 1))
  out=$("$@" 2>&1); status=$?
  if [ "$status" != "$want" ] || [[ "$out" != *"$text"* ]]; then
    echo "cli_test: FAIL: $* (exit $status, want $want and \"$text\"):"; echo "$out" | head -5; fail=1
  fi
}
printf 'fn main(sys: Sys) { sys.console.println("args {sys.args}") }\n' > "$tmp/p.tn"
printf 'fn main(sys: Sys) -> Int { "x" }\n' > "$tmp/bad.tn"
export TENON_ROOT=$REPO
expect 2 "usage: tenon COMMAND" "$C"
expect 0 "usage: tenon COMMAND" "$C" help
expect 0 "tenon fmt [--check]" "$C" --help
expect 0 "usage: tenon COMMAND" "$C" build --help
expect 0 "tenon 0." "$C" --version
n=$((n + 1))
"$C" help > "$tmp/usage.txt"
grep -qxF -f "$tmp/usage.txt" docs/tools.md && [ "$(grep -cxF -f "$tmp/usage.txt" docs/tools.md)" = "$(wc -l < "$tmp/usage.txt" | tr -d ' ')" ] ||
  { echo "cli_test: FAIL: docs/tools.md does not show the usage text of \`tenon help\` verbatim"; fail=1; }
expect 2 "tenon: unknown command 'frob'" "$C" frob
expect 2 "tenon: unknown flag --bless for \`tenon build\`" "$C" build "$tmp/p.tn" --bless
expect 2 "tenon: unknown flag -x for \`tenon check\`" "$C" check -x "$tmp/p.tn"
expect 2 "tenon: -o needs a value" "$C" build "$tmp/p.tn" -o
expect 2 "tenon: \`tenon check\` takes one FILE.tn" "$C" check "$tmp/p.tn" "$REPO"
expect 2 "tenon: \`tenon lsp\` takes no arguments" "$C" lsp extra
expect 2 "tenon: \`tenon test\` takes one or more DIRs" "$C" test --bless
expect 1 "error" "$C" check "$tmp/bad.tn"
expect 0 "" "$C" check --root "$REPO" "$tmp/p.tn"
expect 0 "" "$C" check "$tmp/p.tn" --root "$REPO"
expect 0 "" "$C" --root "$REPO" check "$tmp/p.tn"
expect 2 "cannot read the prelude" "$C" check "$tmp/p.tn" --root "$tmp"
expect 0 'args ["-o", "x", "--root", "y"]' "$C" run --root "$REPO" "$tmp/p.tn" -o x --root y
expect 0 'args ["a"]' "$C" --root "$REPO" run "$tmp/p.tn" a
expect 0 "" "$C" build -O0 "$tmp/p.tn" --root "$REPO" -o "$tmp/p1"
expect 0 'args ["z"]' "$tmp/p1" z
expect 0 "" "$C" build -o "$tmp/p2" "$tmp/p.tn"
expect 0 'args []' "$tmp/p2"
expect 0 "main" "$C" tokens "$tmp/p.tn" --root "$REPO"
printf 'fn main(sys:Sys){sys.console.println("x")}\n' > "$tmp/u.tn"
expect 1 "$tmp/u.tn" "$C" fmt "$tmp/u.tn" --check
expect 0 "" "$C" fmt "$tmp/u.tn"
expect 0 "" "$C" fmt --check "$tmp/u.tn"
expect 2 "formats standard input alone" "$C" fmt - "$tmp/u.tn"
# installed: tenon on PATH, run from elsewhere, no TENON_ROOT
unset TENON_ROOT
ops/repo/install.sh "$tmp/prefix" > "$tmp/install.log" 2>&1 || { echo "cli_test: FAIL: ops/repo/install.sh"; cat "$tmp/install.log"; fail=1; }
mkdir -p "$tmp/suite/run" "$tmp/suite/reject" "$tmp/work"
printf 'import regex\nfn main(sys: Sys) {\n    let ok = regex.compile("a+").is_ok()\n    sys.console.println("abab {ok}")\n}\n' > "$tmp/suite/run/hello.tn"
printf 'abab true\nexit: 0\n' > "$tmp/suite/run/hello.out"
printf '// error: expected Int\nfn main(sys: Sys) -> Int { "x" }\n' > "$tmp/suite/reject/bad.tn"
cp "$tmp/p.tn" "$tmp/work/p.tn"
( cd "$tmp/work" && PATH=$tmp/prefix/bin:$PATH
  expect 0 "abab true" tenon run ../suite/run/hello.tn
  expect 0 "tests: 1 run (x2 backends), 1 reject, 0 failed" tenon test ../suite
  expect 0 'args []' sh -c 'tenon build p.tn && ./p'
  exit $fail ) || fail=1
n=$((n + 3))
[ $fail = 0 ] && echo "cli_test: ok ($n checks: usage, exit statuses, flags in any position, unknown flags, run's own flags, fmt, install.sh and an installed tenon run, build and test without TENON_ROOT)"
exit $fail
