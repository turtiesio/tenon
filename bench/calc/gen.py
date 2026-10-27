# Deterministic input: function definitions, a few heavy recursive calls, and
# many arithmetic lines. No errors.
import random
r = random.Random(7)
L = []
L.append("// calc benchmark input")
L.append("fn fib(n) = if n < 2 then n else fib(n - 1) + fib(n - 2)")
L.append("fn gcd(a, b) = if b == 0 then a else gcd(b, a % b)")
L.append("fn collatz(n, steps) = if n == 1 then steps else collatz(if n % 2 == 0 then n / 2 else 3 * n + 1, steps + 1)")
L.append("fn sumsq(n, acc) = if n == 0 then acc else sumsq(n - 1, (acc + n * n) % 1000003)")
L.append("fn divisible(n, d) = if d * d > n then 1 else if n % d == 0 then 0 else divisible(n, d + 1)")
L.append("fn isprime(n) = if n < 2 then 0 else divisible(n, 2)")
L.append("fn countprimes(n, acc) = if n < 2 then acc else countprimes(n - 1, acc + isprime(n))")
L.append("fn poly(x) = (3 * x * x * x - 5 * x * x + 7 * x - 11) % 10007")
L.append("fn clamp(x, lo, hi) = if x < lo then lo else if x > hi then hi else x")
L.append("fn tri(n) = n * (n + 1) / 2")
for k in range(30):
    L.append("fib(%d)" % (24 + k % 2))
for k in range(30):
    L.append("collatz(%d, 0)" % r.randint(1000, 9000))
for k in range(10):
    L.append("gcd(%d, %d)" % (r.randint(10**6, 10**9), r.randint(10**6, 10**9)))
for k in range(6):
    L.append("countprimes(%d, 0)" % (700 + 25 * k))
for k in range(6):
    L.append("sumsq(900, %d)" % k)
for i in range(40):
    L.append("let v%d = %d" % (i, r.randint(1, 1000)))
ops = ["+", "-", "*", "%", "<", "==", ">="]
for i in range(8000):
    a, b, c = r.sample(range(40), 3)
    form = r.randrange(5)
    if form == 0:
        L.append("let v%d = (v%d * %d + v%d) %% 100003" % (a, b, r.randint(2, 99), c))
    elif form == 1:
        L.append("poly(v%d) + poly(v%d) * %d - clamp(v%d, 10, 500)" % (a, b, r.randint(1, 9), c))
    elif form == 2:
        L.append("if v%d %s v%d then tri(v%d %% 1000) else -tri(v%d %% 100) // note" % (
            a, r.choice(["<", ">", "==", "!=", "<=", ">="]), b, c, c))
    elif form == 3:
        L.append("(v%d + %d) * (v%d - %d) / %d %% 977" % (a, r.randint(1, 50), b, r.randint(1, 50), r.randint(1, 20)))
    else:
        L.append("gcd(v%d + 1, v%d + 1) + %d * -v%d" % (a, b, r.randint(1, 5), c))
open("input.txt", "w").write("\n".join(L) + "\n")
