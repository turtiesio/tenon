#!/usr/bin/env bash
# Packages (docs/packages.md): a fixture workspace in a temporary directory
# with an app, a path dependency and two git dependencies (local repositories
# under file:// URLs, one of them transitive; no network is used), checked
# through $TENON (default target/tenon):
#   fetch and the lock's contents (stable across runs), offline run, build,
#   check and test (also with the repositories gone), a path dependency is
#   live, a stale lock after a manifest change, a missing lock, a tampered
#   cache (detected, repaired by fetch), and the errors for a version
#   conflict, a cycle, a std-name collision, a module-name collision and a
#   malformed manifest.
set -euo pipefail
cd "$(dirname "$0")/../.."
REPO=$PWD
TC=${TENON:-$REPO/target/tenon}
case $TC in /*) ;; *) TC=$REPO/$TC ;; esac
export TENON_ROOT=$REPO TENON=$TC
T=$(mktemp -d)
trap '[ -n "${PKG_KEEP:-}" ] && echo "kept $T" || rm -rf "$T"' EXIT
T=$(cd "$T" && pwd -P)
export TENON_HOME=$T/home TENON_CACHE=off
fails=0
n=0
fail() { echo "FAIL pkg: $*"; fails=$((fails + 1)); }

# expect STATUS PATTERN CMD...: CMD exits with STATUS and its output contains PATTERN
expect() {
    local want=$1 pat=$2
    shift 2
    n=$((n + 1))
    local out st=0
    out=$("$@" 2>&1) || st=$?
    if [ "$st" != "$want" ]; then fail "$* -> status $st, want $want:"$'\n'"$out"; return; fi
    case $out in *"$pat"*) ;; *) fail "$* -> output lacks '$pat':"$'\n'"$out" ;; esac
}

g() { git -c user.name=t -c user.email=t@example.com -c commit.gpgsign=false -c tag.gpgsign=false "$@"; }
repo() { # repo DIR: commit everything and tag it with $2
    (cd "$1" && { [ -d .git ] || g init -q; } && g add -A && g commit -q -m "$2" && g tag "$2")
}
mkpkg() { # mkpkg DIR NAME VERSION [DEPS...]
    local dir=$1 name=$2 version=$3
    shift 3
    mkdir -p "$dir/src"
    {
        printf '# fixture\n[package]\nname = "%s"\nversion = "%s"\n' "$name" "$version"
        if [ $# -gt 0 ]; then printf '\n[dependencies]\n'; printf '%s\n' "$@"; fi
    } > "$dir/tenon.toml"
}

# pad: a git package with two tags
mkpkg "$T/repos/pad" pad 0.1.0
printf 'pub fn left(s: Str, n: Int) -> Str { s.pad_left(n, ".") }\n' > "$T/repos/pad/src/pad.tn"
repo "$T/repos/pad" v0.1.0
mkpkg "$T/repos/pad" pad 0.2.0
printf 'pub fn left(s: Str, n: Int) -> Str { s.pad_left(n, "*") }\n' > "$T/repos/pad/src/pad.tn"
repo "$T/repos/pad" v0.2.0
# fmtx: a git package that depends on pad (transitive for the app)
mkpkg "$T/repos/fmtx" fmtx 1.0.0 "pad = { git = \"file://$T/repos/pad\", tag = \"v0.2.0\" }"
printf 'import pad\n\npub fn show(n: Int) -> Str { "[" + pad.left("{n}", 5) + "]" }\n' > "$T/repos/fmtx/src/fmtx.tn"
repo "$T/repos/fmtx" v1.0.0
printf 'import pad\n\npub fn show(n: Int) -> Str { "<" + pad.left("{n}", 5) + ">" }\n' > "$T/repos/fmtx/src/fmtx.tn"
repo "$T/repos/fmtx" v1.1.0
# util: a path package with an internal module
mkpkg "$T/ws/util" util 0.3.0
printf 'import helper\n\npub fn double(n: Int) -> Int { helper.twice(n) }\n' > "$T/ws/util/src/util.tn"
printf 'pub fn twice(n: Int) -> Int { n * 2 }\n' > "$T/ws/util/src/helper.tn"
# app
APP=$T/ws/app
mkpkg "$APP" app 0.1.0 'util = { path = "../util" }  # live' "fmtx = { git = \"file://$T/repos/fmtx\", tag = \"v1.0.0\" }"
cat > "$APP/src/main.tn" <<'EOF'
import util
import fmtx
import words

fn main(sys: Sys) {
    sys.console.println(fmtx.show(util.double(21)) + " " + words.hello())
}
EOF
printf 'pub fn hello() -> Str { "hi" }\n' > "$APP/src/words.tn"
mkdir -p "$APP/tests/run"
printf 'import util\n\nfn main(sys: Sys) { sys.console.println("{util.double(4)}") }\n' > "$APP/tests/run/double.tn"
printf '8\nexit: 0\n' > "$APP/tests/run/double.out"
cd "$APP"

# fetch, the lock, and stability
expect 0 "tenon.lock: 3 packages" "$TC" fetch
cp tenon.lock "$T/lock1"
pad2=$(git -C "$T/repos/pad" rev-parse v0.2.0)
for want in '[package.fmtx]' '[package.pad]' '[package.util]' 'source = "path"' 'path = "../util"' \
    "git = \"file://$T/repos/pad\"" 'tag = "v0.2.0"' "commit = \"$pad2\"" 'version = "0.3.0"'; do
    n=$((n + 1))
    grep -qF "$want" tenon.lock || fail "tenon.lock lacks $want"
done
n=$((n + 1))
[ "$(grep -c '^hash = "[0-9a-f]\{32\}"$' tenon.lock)" = 3 ] || fail "tenon.lock: want 3 content hashes"
expect 0 "(unchanged)" "$TC" fetch
n=$((n + 1))
cmp -s tenon.lock "$T/lock1" || fail "tenon.lock changed on a second fetch"
rm -rf "$TENON_HOME"
expect 0 "(unchanged)" "$TC" fetch # a fresh cache: same commits, same hashes

# offline: run, build, check, test, also from a subdirectory and with the repositories gone
mv "$T/repos" "$T/repos.away"
expect 0 "[***42] hi" "$TC" run src/main.tn
expect 0 "" "$TC" build src/main.tn -o "$T/app" -O0
expect 0 "[***42] hi" "$T/app"
expect 0 "" "$TC" check src/main.tn
expect 0 "[***42] hi" sh -c "cd src && '$TC' run main.tn"
expect 0 "1 run (x2 backends), 0 reject, 0 failed" "$TC" test tests
mv "$T/repos.away" "$T/repos"

# a path dependency is live: no fetch needed after an edit; fetch refreshes its hash
printf 'pub fn twice(n: Int) -> Int { n * 2 + 1 }\n' > "$T/ws/util/src/helper.tn"
expect 0 "[***43] hi" "$TC" run src/main.tn
expect 0 "tenon.lock: 3 packages" "$TC" fetch
n=$((n + 1))
cmp -s tenon.lock "$T/lock1" && fail "fetch did not refresh the hash of the edited path package"
printf 'pub fn twice(n: Int) -> Int { n * 2 }\n' > "$T/ws/util/src/helper.tn"
"$TC" fetch > /dev/null

# a missing lock, a stale lock
mv tenon.lock "$T/lock.saved"
expect 1 "no tenon.lock for tenon.toml; run \`tenon fetch\`" "$TC" run src/main.tn
mv "$T/lock.saved" tenon.lock
sed -i.bak 's/v1.0.0/v1.1.0/' tenon.toml
expect 1 "tenon.lock is out of date with tenon.toml (fmtx: git file://$T/repos/fmtx tag v1.1.0); run \`tenon fetch\`" "$TC" check src/main.tn
expect 0 "fmtx 1.0.0 (git file://$T/repos/fmtx tag v1.1.0" "$TC" fetch
expect 0 "<***42> hi" "$TC" run src/main.tn
mv tenon.toml.bak tenon.toml
"$TC" fetch > /dev/null
n=$((n + 1))
cmp -s tenon.lock "$T/lock1" || fail "tenon.lock differs after going back to v1.0.0"
grep -v fmtx tenon.toml > "$T/m" && cp "$T/m" tenon.toml
expect 1 "tenon.lock lists 'fmtx', which is no longer a dependency" "$TC" check src/words.tn
mkpkg "$APP" app 0.1.0 'util = { path = "../util" }  # live' "fmtx = { git = \"file://$T/repos/fmtx\", tag = \"v1.0.0\" }"

# a tampered cache entry is refused; fetch repairs it
cached=$(dirname "$(dirname "$(grep -rl 'pad_left(n, "\*")' "$TENON_HOME/cache/git" | head -1)")")
printf 'pub fn left(s: Str, n: Int) -> Str { s }\n' > "$cached/src/pad.tn"
expect 1 "package 'pad' in the cache ($cached) does not match tenon.lock" "$TC" run src/main.tn
expect 0 "tenon.lock: 3 packages (unchanged)" "$TC" fetch
expect 0 "[***42] hi" "$TC" run src/main.tn

# errors: a version conflict, a cycle, a std-name collision, a module-name collision, malformed manifests
mkpkg "$T/ws/conflict" conflict 0.1.0 "fmtx = { git = \"file://$T/repos/fmtx\", tag = \"v1.0.0\" }" \
    "pad = { git = \"file://$T/repos/pad\", tag = \"v0.1.0\" }"
expect 1 "package 'pad' is required from two sources: git file://$T/repos/pad tag v0.2.0 (by $TENON_HOME/cache/git/" "$TC" fetch "$T/ws/conflict"
expect 1 "and git file://$T/repos/pad tag v0.1.0 (by $T/ws/conflict/tenon.toml:8)" "$TC" fetch "$T/ws/conflict"
mkpkg "$T/ws/c1" c1 0.1.0 'c2 = { path = "../c2" }'
mkpkg "$T/ws/c2" c2 0.1.0 'c3 = { path = "../c3" }'
mkpkg "$T/ws/c3" c3 0.1.0 'c2 = { path = "../c2" }'
mkpkg "$T/ws/top" top 0.1.0 'c1 = { path = "../c1" }'
touch "$T/ws/c1/src/c1.tn" "$T/ws/c2/src/c2.tn" "$T/ws/c3/src/c3.tn"
expect 1 "dependency cycle: c2 -> c3 -> c2 (at $T/ws/c3/tenon.toml:7)" "$TC" fetch "$T/ws/top"
mkpkg "$T/ws/selfdep" selfdep 0.1.0 'c9 = { path = "../c9" }'
mkpkg "$T/ws/c9" c9 0.1.0 'selfdep = { path = "../selfdep" }'
touch "$T/ws/c9/src/c9.tn"
expect 1 "dependency cycle: selfdep -> c9 -> selfdep" "$TC" fetch "$T/ws/selfdep"
mkpkg "$T/ws/stdname" stdname 0.1.0 'regex = { path = "../util" }'
expect 1 "tenon.toml:7: dependency 'regex' has the name of a standard library module" "$TC" fetch "$T/ws/stdname"
mkpkg "$T/ws/clash" clash 0.1.0 'util = { path = "../util" }'
printf 'import helper\nimport util\n\nfn main() { let _ = util.double(helper.n()) }\n' > "$T/ws/clash/src/main.tn"
printf 'pub fn n() -> Int { 1 }\n' > "$T/ws/clash/src/helper.tn"
"$TC" fetch "$T/ws/clash" > /dev/null
expect 1 "module 'helper' is both" "$TC" check "$T/ws/clash/src/main.tn"
mkdir -p "$T/ws/bad"
bad() { printf "$1" > "$T/ws/bad/tenon.toml"; expect 1 "$2" "$TC" fetch "$T/ws/bad"; }
bad '[package]\nname = "bad"\nversion = 1\n' "bad/tenon.toml:3: expected a string in double quotes"
bad '[package]\nname = "bad"\nversion = "1" extra\n' "bad/tenon.toml:3: unexpected text 'extra'"
bad '[package]\nname = "bad"\n' "bad/tenon.toml:1: [package] needs version"
bad '[package]\nname = "bad"\nversion = "1"\n[dependencies]\nx = { path = "../x", tag = "v1" }\n' \
    "bad/tenon.toml:5: dependency 'x' must have either path, or git and tag"
bad '[package]\nname = "bad"\nversion = "1"\n[deps]\n' "bad/tenon.toml:4: unknown table [deps]"
bad '[package]\nname = "bad"\nname = "b"\n' "bad/tenon.toml:3: key 'name' given twice in [package]"
bad '[package]\nname = "Bad-1"\nversion = "1"\n' "bad/tenon.toml:2: package name 'Bad-1' must be a module name"
bad '[package]\nname = "bad"\nversion = "1"\n[dependencies]\nx = { path = "../x",\n' \
    "bad/tenon.toml:5: expected a key"
bad '[package]\nname = "bad"\nversion = "1"\n[dependencies]\nx = { git = "u" }\n' \
    "bad/tenon.toml:5: dependency 'x' must have either path, or git and tag"
# tests/pkg/NAME.toml (guarded): a manifest `tenon fetch` rejects; its first line is
# `# error: TEXT`, a substring of the diagnostic
for f in "$REPO"/tests/pkg/*.toml; do
    mkdir -p "$T/ws/fixture"
    cp "$f" "$T/ws/fixture/tenon.toml"
    expect 1 "$(head -1 "$f" | sed 's/^# error: //')" "$TC" fetch "$T/ws/fixture"
done

if [ $fails -gt 0 ]; then
    echo "pkg: $fails of $n checks failed"
    exit 1
fi
echo "pkg: ok ($n checks: fetch, lock, offline run/build/check/test, live path dependency, stale/missing lock, tampered cache, conflict, cycle, std and module name collisions, malformed manifests)"
