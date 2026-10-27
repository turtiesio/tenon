#!/usr/bin/env bash
# Scenario test; $RUN is the command that runs the program (interpreter or binary).
set -u
D=$(mktemp -d)
trap 'rm -rf "$D"' EXIT
cd "$D"
step() { echo "\$ mkplan $*"; $RUN "$@" 2>&1; echo "[exit $?]"; }
mk() { cat > "$1"; }

echo "# nothing exists yet: everything is built, dependencies first"
mk fresh.mk <<'X'
# a small C project
app: main.o util.o | cc -o app main.o util.o
main.o: main.c util.h | cc -c main.c
util.o: util.c util.h | cc -c util.c
---
main.c 5
util.c 5
util.h 5
X
step fresh.mk

echo "# all up to date"
mk uptodate.mk <<'X'
app: main.o util.o | cc -o app main.o util.o
main.o: main.c util.h | cc -c main.c
util.o: util.c util.h | cc -c util.c
---
main.c 5
util.c 5
util.h 5
main.o 10
util.o 10
app 20
X
step uptodate.mk

echo "# one source is newer: rebuilds propagate transitively"
mk newer.mk <<'X'
app: main.o util.o | cc -o app main.o util.o
main.o: main.c util.h | cc -c main.c
util.o: util.c util.h | cc -c util.c

---
# mtimes
main.c 5
util.c 15
util.h 5
main.o 10
util.o 10
app 20
X
step newer.mk

echo "# equal mtime is not newer"
mk equal.mk <<'X'
out: in | make out
---
in 7
out 7
X
step equal.mk

echo "# a target with no mtime is rebuilt even if its deps are old"
mk nomtime.mk <<'X'
out: in | make out
---
in 1
X
step nomtime.mk

echo "# TARGET argument selects a sub-plan; the rest is ignored"
step newer.mk util.o
step newer.mk main.o
step newer.mk app
step newer.mk main.c
step newer.mk nothing

echo "# ties broken by order of appearance, not by dependency order"
mk order.mk <<'X'
all: c b a | echo all
c: | echo c
b: a | echo b
a: | echo a
X
step order.mk

echo "# diamond: the shared dependency is planned once"
mk diamond.mk <<'X'
top: left right | echo top
left: base | echo left
right: base | echo right
base: src | echo base
---
src 3
base 2
left 9
right 9
top 10
X
step diamond.mk

echo "# commands may contain ':' and '|'"
mk cmd.mk <<'X'
t: | echo a:b | tee out
X
step cmd.mk

echo "# the empty file, and one with only comments"
: > empty.mk
step empty.mk
step empty.mk anything
printf '# nothing\n\n' > comments.mk
step comments.mk

echo "# errors"
mk cycle.mk <<'X'
a: b | echo a
b: c | echo b
c: a | echo c
X
step cycle.mk
mk cycle2.mk <<'X'
top: x | echo top
x: y | echo x
y: z | echo y
z: y | echo z
X
step cycle2.mk
mk self.mk <<'X'
a: a | echo a
X
step self.mk
echo "# a cycle outside the requested target is not reached"
mk offpath.mk <<'X'
good: | echo good
bad1: bad2 | echo bad1
bad2: bad1 | echo bad2
X
step offpath.mk
step offpath.mk good
step offpath.mk bad2
step cycle2.mk top
mk missing.mk <<'X'
app: main.o | link
main.o: main.c | cc
---
main.o 1
X
step missing.mk
mk dup.mk <<'X'
a: | echo one
b: | echo two
a: b | echo three
X
step dup.mk
mk bad1.mk <<'X'
# comment
a: b | echo a

just some words
X
step bad1.mk
mk bad2.mk <<'X'
a: b echo a
X
step bad2.mk
mk bad3.mk <<'X'
: b | echo a
X
step bad3.mk
mk bad4.mk <<'X'
a b: | echo a
X
step bad4.mk
mk bad5.mk <<'X'
a: | 
X
step bad5.mk
mk bad6.mk <<'X'
a: | echo a
---
a ten
X
step bad6.mk
mk bad7.mk <<'X'
a: | echo a
---
a 1 2
X
step bad7.mk
mk bad8.mk <<'X'
a: | echo a
---
a 1
a 2
X
step bad8.mk
mk bad9.mk <<'X'
a: | echo a
---
a 1
---
X
step bad9.mk
step nosuchfile.mk

echo "# usage"
step
step a b c
