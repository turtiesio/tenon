#!/usr/bin/env bash
# Scenario test; $RUN is the command that runs the program (interpreter or binary).
set -u
D=$(mktemp -d)
trap 'rm -rf "$D"' EXIT
cd "$D"
show() { printf '$ csvq'; for a in "$@"; do printf ' %q' "$a"; done; }
step() { show "$@"; echo; $RUN "$@" 2>&1; echo "[exit $?]"; }
# same, with a file on standard input
stdin_step() { local f=$1; shift; show "$@"; echo " < $f"; $RUN "$@" < "$f" 2>&1; echo "[exit $?]"; }

cat > people.csv <<'CSV'
name,city,age,dept,salary
Alice,Paris,30,eng,5000.50
Bob,London,25,ops,3000
"Smith, Jo",Paris,41,eng,7000.25
"Dee ""D"" Day",Rome,25,hr,2500
Eve,London,30,ops,4000.75
Carl,Paris,9,eng,1999.99
Fay,Rome,100,hr,3500
CSV

echo "# plain output and --select"
step people.csv
step people.csv --select name,age
step people.csv --select salary,name,salary
step people.csv --select city

echo "# --where: AND of conditions, exact match, quoted values"
step people.csv --where city=Paris
step people.csv --where city=Paris --where dept=eng --where age=30
step people.csv --where city=Paris --where city=Rome
step people.csv --where city=paris
step people.csv --where 'name=Smith, Jo' --select name,city
step people.csv --where 'name=Dee "D" Day'
step people.csv --where age=25 --select name

echo "# --sort: numeric when both are numbers, stable, :desc"
step people.csv --sort age --select name,age
step people.csv --sort age:desc --select name,age
step people.csv --sort age:asc --select name,age
step people.csv --sort name --select name
step people.csv --sort city --select city,name
step people.csv --sort city:desc --select city,name
step people.csv --sort salary:desc --select name,salary

echo "# --sort on mixed and unusual values"
cat > mixed.csv <<'CSV'
k,v
a,10
b,9
c,abc
d,-5
e,2.5
f,1e3
g,
h,9007199254740993
i,9007199254740992
CSV
step mixed.csv --sort v --select k,v
step mixed.csv --sort v:desc --select k,v

echo "# options in any position, quoted header names"
step --limit 1 people.csv --select name
printf '"first name","a,b"\nx,y\n' > hq.csv
step hq.csv
step hq.csv --select "first name" --where "a,b=y"

echo "# --limit"
step people.csv --limit 2
step people.csv --limit 0
step people.csv --limit 100 --select name --where dept=hr
step people.csv --sort salary:desc --limit 3 --select name,salary

echo "# --group with --count, --sum, --avg"
step people.csv --group city --count
step people.csv --group dept --count
step people.csv --group city --sum salary
step people.csv --group dept --sum age
step people.csv --group city --avg salary
step people.csv --group dept --avg age
step people.csv --group age --count
step people.csv --group city --count --where dept=eng
step people.csv --group city --count --limit 2
step people.csv --group city --count --where dept=nope

echo "# decimals: exact sums, half-up averages"
cat > money.csv <<'CSV'
k,v
a,0.1
a,0.2
b,1
b,2
b,2
c,-2.345
c,-1
d,0.005
d,0.004
f,0.01
f,0.02
g,-0.01
g,-0.02
e,+7.
e,.5
CSV
step money.csv --group k --sum v
step money.csv --group k --avg v

echo "# quoting on output: commas, quotes, newlines, empty single column"
cat > quotes.csv <<'CSV'
id,text,note
1,"a,b","say ""hi"""
2,"line1
line2",plain
3,"",""
4,  spaced  ,"x"
5,eq,a=b
CSV
step quotes.csv
step quotes.csv --select text
step quotes.csv --select note --where id=3
step quotes.csv --where note=a=b --select id,text
step quotes.csv --group text --count
printf 'v\n"a,b"\n""\nc\n' > single.csv
step single.csv
step single.csv --where v=

echo "# CRLF, blank lines, missing final newline"
printf 'a,b\r\n1,2\r\n\r\n3,4' > crlf.csv
step crlf.csv
step crlf.csv --where b=4

echo "# malformed rows are skipped and counted"
printf 'a,b\n1,2\n3\n4,5,6\n7,8\n"9,10\n' > bad1.csv
step bad1.csv
printf 'a,b\n1,2\n"x"y,3\n"p""q",4\nfoo"bar,5\n5,6\n' > bad2.csv
step bad2.csv
step bad2.csv --group a --count
printf 'a,b\n1,2\n3\n' > bad3.csv
step bad3.csv --where a=nope
printf 'a,b\n1,2\n,\n,3\n5,\n' > empties.csv
step empties.csv
step empties.csv --where a=
step empties.csv --sort b:desc

echo "# standard input"
stdin_step people.csv - --where dept=hr --select name
stdin_step people.csv - --group city --count
stdin_step bad1.csv - --select a
: > empty.csv
stdin_step empty.csv -
printf 'a,b\n' > header_only.csv
stdin_step header_only.csv - --sort a
step header_only.csv --group a --sum b

echo "# errors (exit status 2)"
step
step people.csv --where nocolumn=1
step people.csv --where city
step people.csv --select name,bogus
step people.csv --sort bogus
step people.csv --sort bogus:desc
step people.csv --group bogus --count
step people.csv --group city --sum bogus
step people.csv --group city --avg bogus
step people.csv --group city --sum name
step people.csv --group city --avg dept
step people.csv --limit x
step people.csv --limit -1
step people.csv --limit 1.5
step people.csv --limit
step people.csv --where
step people.csv --bogus
step people.csv -x
step people.csv other.csv
step people.csv --group city
step people.csv --count
step people.csv --sum salary
step people.csv --group city --count --sum salary
step people.csv --group city --sum salary --avg salary
step people.csv --group city --count --select name
step people.csv --group city --count --sort city
step people.csv --select a --select b
step people.csv --sort a --sort b
step people.csv --limit 1 --limit 2
step --count
step missing.csv
echo "# errors in the data"
printf 'g,v\na,1\na,\n' > emptyval.csv
step emptyval.csv --group g --sum v
printf 'g,v\na,9223372036854775807\na,1\n' > big.csv
step big.csv --group g --sum v
printf 'g,v\na,99999999999999999999\n' > huge.csv
step huge.csv --group g --avg v
printf '"a,b\n1,2\n' > bad_header.csv
step bad_header.csv
