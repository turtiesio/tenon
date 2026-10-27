#!/usr/bin/env bash
set -u
D=$(mktemp -d); trap 'rm -rf "$D"' EXIT
step() { echo "\$ jobq $*"; $RUN "$D" "$@" 2>&1; echo "[exit $?]"; }
step add email hello
step add report flaky
step add broken fail
step add resize big-image
step status
step work --crash-after 1
step status
step work
step status
step work
echo "# torn tail is archived; nothing runs twice"
printf 'add 9 ghost x #1' >> "$D/journal"
step status
step add late done
step work
step status
