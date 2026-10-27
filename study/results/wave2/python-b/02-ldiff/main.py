import sys
from array import array

def read_lines(path):
    with open(path, 'rb') as f:
        data = f.read()
    return data.split(b'\n')[:-1] if data.endswith(b'\n') else (data.split(b'\n') if data else [])

def main():
    args = sys.argv[1:]
    paths = [a for a in args if not a.startswith('-')]
    if len(paths) != 2 or any(a.startswith('-') and a not in ('-i', '-b', '-q', '-s') for a in args) or ('-q' in args and '-s' in args):
        return 2
    try:
        a, b = map(read_lines, paths)
    except OSError:
        return 2
    def key(line):
        if '-b' in args:
            line = line.rstrip(b' \t')
        return line.lower() if '-i' in args else line
    ak, bk = list(map(key, a)), list(map(key, b))
    n, m = len(a), len(b)
    table = [array('H', [0]) * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        row, below = table[i], table[i + 1]
        for j in range(m - 1, -1, -1):
            row[j] = 1 + below[j + 1] if ak[i] == bk[j] else max(below[j], row[j + 1])
    i = j = 0
    counts = {'+': 0, '-': 0, ' ': 0}
    output = []
    while i < n or j < m:
        if i == n:
            mark, line = '+', b[j]
            j += 1
        elif j == m:
            mark, line = '-', a[i]
            i += 1
        elif ak[i] == bk[j]:
            mark, line = ' ', a[i]
            i += 1
            j += 1
        elif table[i + 1][j] >= table[i][j + 1]:
            mark, line = '-', a[i]
            i += 1
        else:
            mark, line = '+', b[j]
            j += 1
        counts[mark] += 1
        if '-q' not in args and '-s' not in args:
            output.append(mark.encode() + b' ' + line + b'\n')
    if '-s' in args:
        print(f"+{counts['+']} -{counts['-']} ={counts[' ']}")
    elif '-q' not in args:
        sys.stdout.buffer.write(b''.join(output))
    return int(counts['+'] + counts['-'] > 0)

if __name__ == '__main__':
    sys.exit(main())
