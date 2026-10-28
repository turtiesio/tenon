import sys
from pathlib import Path
from common import fail
selected, paths = set(), []
for a in sys.argv[1:]:
    if a in ('-l','-w','-m','-c'): selected.add(a[1:])
    elif a.startswith('-'): fail(2)
    else: paths.append(a)
selected = selected or set('lwc')
rows, code = [], 0
for path in paths or [None]:
    try: data = sys.stdin.buffer.read() if path is None else Path(path).read_bytes()
    except OSError:
        print('unreadable file', file=sys.stderr)
        code = 1
        continue
    nums = {'l':data.count(b'\n'), 'c':len(data)}
    if 'w' in selected:
        count, inside = 0, False
        for byte in data:
            if byte in b' \t\n\v\f\r': inside = False
            elif not inside: count += 1; inside = True
        nums['w'] = count
    if 'm' in selected: nums['m'] = len(data.decode('utf-8'))
    rows.append(([nums[c] for c in 'lwmc' if c in selected], path))
if len(paths) >= 2:
    rows.append(([sum(row[0][i] for row in rows) for i in range(len(selected))], 'total'))
width = max([1] + [len(str(v)) for ns,_ in rows for v in ns])
for ns, label in rows:
    print(' '.join(str(v).rjust(width) for v in ns) + ('' if label is None else ' '+label))
sys.exit(code)
