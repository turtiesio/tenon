#!/usr/bin/env bash
# Install `tenon` (docs/tools.md): builds the seed, stage0 and stage1 as
# ./check does, then copies
#   PREFIX/bin/tenon                       the self-hosted command line (stage1)
#   PREFIX/lib/tenon/lib/                  prelude.tn, std/, v2/
#   PREFIX/lib/tenon/runtime/tenon.h       the C runtime
# PREFIX defaults to ~/.local (put ~/.local/bin on PATH). `tenon` finds its
# root (PREFIX/lib/tenon) from its own path, so TENON_ROOT is not needed.
# Reinstalling replaces the previous files. Needs cargo and a C compiler.
# Usage: tools/install.sh [PREFIX]
set -euo pipefail
cd "$(dirname "$0")/.."
prefix=${1:-$HOME/.local}
case $prefix in /*) ;; *) prefix=$PWD/$prefix ;; esac
cargo build --release --quiet
export TENON_ROOT=$PWD
target/release/tenon-seed build selfhost/tenon.tn -o target/tenon0 -O0
target/tenon0 build selfhost/tenon.tn -o target/tenon
mkdir -p "$prefix/bin" "$prefix/lib/tenon"
rm -rf "$prefix/lib/tenon/lib" "$prefix/lib/tenon/runtime"
cp -R lib "$prefix/lib/tenon/lib"
mkdir -p "$prefix/lib/tenon/runtime"
cp runtime/tenon.h "$prefix/lib/tenon/runtime/tenon.h"
# copy, then rename: a running tenon is not overwritten in place
cp target/tenon "$prefix/bin/.tenon.tmp"
mv -f "$prefix/bin/.tenon.tmp" "$prefix/bin/tenon"
echo "installed $prefix/bin/tenon ($("$prefix/bin/tenon" --version)), root $prefix/lib/tenon"
case ":$PATH:" in *":$prefix/bin:"*) ;; *) echo "add $prefix/bin to PATH to run it as \`tenon\`" ;; esac
