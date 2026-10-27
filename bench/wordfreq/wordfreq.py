import sys
counts = {}
for w in sys.stdin.read().lower().split():
    counts[w] = counts.get(w, 0) + 1
for w, n in sorted(counts.items(), key=lambda e: (-e[1], e[0]))[:10]:
    print(n, w)
