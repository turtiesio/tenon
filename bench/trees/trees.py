def make(d): return (make(d - 1), make(d - 1)) if d else (None, None)
def check(t): return 1 + check(t[0]) + check(t[1]) if t[0] else 1
maxd = 18
ll = make(maxd)
for d in range(4, maxd + 1, 2):
    iters = 1 << (maxd - d + 4)
    total = sum(check(make(d)) for _ in range(iters))
    print("%d trees of depth %d check: %d" % (iters, d, total))
print("long lived tree of depth %d check: %d" % (maxd, check(ll)))
