#!/usr/bin/env bash
# Exercise the package as an external consumer. An ancestor dependency would
# make tests belong to that dependency under Tenon's longest-prefix resolver.
set -euo pipefail
app=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$app/../.." && pwd)
tenon=${TENON:-$repo/target/tenon}
"$tenon" fmt --check "$app/src/"*.tn "$app/tests/run/"*.tn "$app/tests/reject/"*.tn "$app/tests/math.tn"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/domain" "$tmp/math/run"
cp "$app/tenon.toml" "$tmp/domain/"
cp -R "$app/src" "$tmp/domain/"
cp -R "$app/tests/run" "$app/tests/reject" "$tmp/"
cp "$app/tests/math.tn" "$app/tests/math.out" "$tmp/math/run/"
{ echo '// module'; cat "$app/src/fple_math.tn"; } > "$tmp/math/run/fple_math.tn"
cat > "$tmp/tenon.toml" <<'EOF'
[package]
name = "fple_tests"
version = "0.1.0"
[dependencies]
fple = { path = "domain" }
EOF
"$tenon" fetch "$tmp"
"$tenon" test "$tmp" "$tmp/math" "$@"
if [ "${1:-}" = "--bless" ]; then
    cp "$tmp/run/"*.out "$app/tests/run/"
    cp "$tmp/math/run/math.out" "$app/tests/math.out"
fi
