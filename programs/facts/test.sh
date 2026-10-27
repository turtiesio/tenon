#!/usr/bin/env bash
set -u
D=$(mktemp -d); trap 'rm -rf "$D"' EXIT
step() { echo "\$ facts $*"; $RUN "$D" "$@" 2>&1; echo "[exit $?]"; }
step query pluto planet
step assert pluto class planet textbook-1990 80
step assert pluto class dwarf-planet iau-2006 95
step query pluto class
step deny pluto class planet iau-2006 90
step query pluto class
step assert pluto moons 5 nasa 90
step assert pluto moons 4 old-survey 40
step query pluto moons
step retract pluto moons 4 old-survey
step query pluto moons
step deny pluto atmosphere none probe 60
step query pluto atmosphere
step retract pluto moons 4 old-survey
step assert pluto class planet fan-site 500
step history pluto class
