"""Private byte-string LCS oracle."""
import sys
from pathlib import Path

def main(args):
    flags = {a for a in args if a.startswith('-')}
    files = [a for a in args if not a.startswith('-')]
    if flags - {'-i', '-b', '-q', '-s'} or {'-q', '-s'} <= flags or len(files) != 2:
        return 2
    try:
        raw = [Path(p).read_bytes() for p in files]
    except OSError:
        return 2
    def lines(b):
        return b.split(b'\n')[:-1] if b.endswith(b'\n') else b.split(b'\n') if b else []
    a, b = map(lines, raw)
    def key(x):
        if '-b' in flags:
            x = x.rstrip(b' \t')
        return x.lower() if '-i' in flags else x
    ka, kb = list(map(key, a)), list(map(key, b))
    n, m = len(a), len(b)
    table = [[0] * (m+1) for _ in range(n+1)]
    for i in range(n-1, -1, -1):
        for j in range(m-1, -1, -1):
            table[i][j] = 1 + table[i+1][j+1] if ka[i] == kb[j] else max(table[i+1][j], table[i][j+1])
    i = j = ins = delete = common = 0
    out = []
    while i < n or j < m:
        if i < n and j < m and ka[i] == kb[j]:
            out.append(b'  ' + a[i] + b'\n'); common += 1; i += 1; j += 1
        elif i < n and (j == m or table[i+1][j] >= table[i][j+1]):
            out.append(b'- ' + a[i] + b'\n'); delete += 1; i += 1
        else:
            out.append(b'+ ' + b[j] + b'\n'); ins += 1; j += 1
    if '-q' not in flags:
        sys.stdout.buffer.write(f'+{ins} -{delete} ={common}\n'.encode() if '-s' in flags else b''.join(out))
    return int(ins + delete > 0)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
