#!/usr/bin/env bash
# Scenario test; $RUN is the command that runs the program (interpreter or binary).
# Each session feeds a script on stdin; the script is echoed ("> ") above the output.
set -u
D=$(mktemp -d)
trap 'rm -rf "$D"' EXIT
session() {
  cat > "$D/in"
  echo "## $1"
  sed 's/^/> /' "$D/in"
  echo "--"
  $RUN < "$D/in" 2>&1
  echo "[exit $?]"
}

session "precedence and associativity" <<'EOF'
1 + 2 * 3
(1 + 2) * 3
10 - 4 - 3
100 / 10 / 5
2 * 3 % 4
20 % 7 * 2
1 + 2 * 3 - 4 / 2 % 3
2 * (3 + 4) * 5
EOF

session "unary minus" <<'EOF'
-5
- -5
-(2 + 3)
2 - -3
-2 * 3
-7 / 2
-7 % 2
7 / -2
7 % -2
3 * -(-4)
EOF

session "every operator" <<'EOF'
7 + 5
7 - 5
7 * 5
7 / 2
7 % 4
1 == 1
1 == 2
1 != 2
1 != 1
1 < 2
2 < 2
1 <= 1
2 <= 1
3 > 2
2 > 2
2 >= 2
1 >= 2
1 < 2 == 1
1 + 1 == 2
2 * 3 > 5 != 0
EOF

session "if/then/else" <<'EOF'
if 1 then 10 else 20
if 0 then 10 else 20
if 5 - 5 then 1 else 2
if -3 then 1 else 2
if 2 > 1 then if 1 > 2 then 1 else 2 else 3
1 + if 0 then 1 else 2 + 3
(if 1 then 2 else 3) + 4
if 1 then 1 else 1 / 0
if 0 then 1 / 0 else 7
EOF

session "variables" <<'EOF'
let x = 6
let y = x * 7
y
x + y
let x = x + 1
x
let big = 1000000 * 1000000
big
y_2 + 1
_under
EOF

session "functions" <<'EOF'
fn sq(n) = n * n
sq(7)
sq(sq(3))
fn add3(a, b, c) = a + b * 10 + c * 100
add3(1, 2, 3)
fn zero() = 42
zero()
let k = 10
fn plusk(v) = v + k
plusk(1)
let k = 100
plusk(1)
fn plusk(v) = v - k
plusk(1)
fn shadow(k) = k * 2
shadow(4)
k
fn abs(n) = if n < 0 then -n else n
abs(-9) + abs(9)
EOF

session "recursion" <<'EOF'
fn fib(n) = if n < 2 then n else fib(n - 1) + fib(n - 2)
fib(0)
fib(1)
fib(10)
fib(20)
fn fact(n) = if n <= 1 then 1 else n * fact(n - 1)
fact(1)
fact(5)
fact(20)
fact(21)
fn gcd(a, b) = if b == 0 then a else gcd(b, a % b)
gcd(48, 18)
fn even(n) = if n == 0 then 1 else odd(n - 1)
fn odd(n) = if n == 0 then 0 else even(n - 1)
even(10)
odd(7)
fn pow(b, e) = if e == 0 then 1 else b * pow(b, e - 1)
pow(2, 62)
pow(2, 63)
EOF

session "call depth limit" <<'EOF'
fn down(n) = if n == 0 then 0 else down(n - 1)
down(10)
down(998)
down(999)
down(1000)
down(100000)
fn forever(n) = forever(n + 1)
forever(0)
fn sum(n) = if n == 0 then 0 else n + sum(n - 1)
sum(500)
sum(999)
sum(1000)
down(5)
EOF

session "integer overflow" <<'EOF'
9223372036854775807
9223372036854775807 + 1
-9223372036854775807 - 1
-9223372036854775807 - 2
-(-9223372036854775807 - 1)
let m = -9223372036854775807 - 1
m
m / -1
m % -1
m * -1
-1 * m
m + m
m - 1
0 - m
9223372036854775807 * 2
4611686018427387904 * 2
4611686018427387903 * 2
3037000500 * 3037000500
3037000499 * 3037000499
-3037000500 * 3037000500
-3037000500 * -3037000500
9223372036854775807 - -1
1 - m
9223372036854775808
99999999999999999999
EOF

session "division by zero" <<'EOF'
1 / 0
1 % 0
0 / 0
let z = 0
10 / z
10 % z
fn inv(n) = 100 / n
inv(5)
inv(0)
inv(1 - 1)
5 / (3 - 3) + 1
let q = 1 / 0
q
let q = 4
q
EOF

session "syntax errors" <<'EOF'
(1 + 2
1 +
* 3
1 2
1 + * 2
)
(1))
1 + (2 * ) + 3
let
let 5 = 3
let x
let x =
let x = 1 2
let if = 3
fn
fn f
fn f(
fn f(a
fn f(a,)
fn f(a b) = 1
fn f(1) = 1
fn f(a, a) = a
fn f(a)
fn f(a) =
fn 3(a) = a
if 1 then 2
if 1 2 else 3
if 1 then 2 else
1 = 2
x = 3
f(1,)
f(1 2)
f(1
1 ! 2
1 $ 2
  1 + @
3 # 4
1 <> 2
café + 1
12 + 3 4
12abc
1 + 2 )
EOF

session "unknown names and arity errors" <<'EOF'
nope
nope + 1
nope(1)
fn two(a, b) = a + b
two(1)
two(1, 2, 3)
two()
fn none() = 1
none(1)
fn one(a) = a
one()
one(1, 2)
one(nope)
fn bad(a) = a + b
bad(1)
fn callsmissing(a) = missing(a)
callsmissing(1)
two(1, 2)
let v = 3
v(1)
fn (v) = 1
fn fnname(a) = a
fnname
let fnname = 2
fn v(a) = a
let two = 1
fn param(v) = v(1)
param(2)
v
EOF

session "redefinition" <<'EOF'
let a = 1
let a = 2
a
fn a() = 3
fn f() = 1
fn f() = 2
f()
let f = 5
fn f(x) = x
f(7)
f
let g = f(1)
g
EOF

session "comments, blank lines and spacing" <<'EOF'
// a comment line

   
1+2   // trailing comment
  let   spaced   =   (  4  )
spaced*spaced
fn  id ( x )=x
id(  9 )
	1	+	1
EOF

{
  n=150; printf '%*s' "$n" '' | tr ' ' '('; printf '1'; printf '%*s' "$n" '' | tr ' ' ')'; echo
  n=250; printf '%*s' "$n" '' | tr ' ' '('; printf '1'; printf '%*s' "$n" '' | tr ' ' ')'; echo
  n=250; printf '%*s' "$n" '' | tr ' ' '-'; echo 1
  n=100; printf '%*s' "$n" '' | tr ' ' '-'; echo 1
} > "$D/nest"
echo "## deeply nested input (150 parens, 250 parens, 250 minus signs, 100 minus signs)"
$RUN < "$D/nest" 2>&1
echo "[exit $?]"

echo "## empty input"
$RUN < /dev/null 2>&1
echo "[exit $?]"

session "clean run exits 0" <<'EOF'
let x = 2
fn double(n) = n * 2
double(x) + 1
EOF
