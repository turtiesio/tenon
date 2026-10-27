"""Private CSV join oracle with rational ordering and integer rounding."""
from functools import cmp_to_key
from pathlib import Path
import re
import sys

def lines(path):
    s = Path(path).read_bytes().decode('ascii').split('\n')
    if s[-1] == '':
        s.pop()
    return [v[:-1] if v.endswith('\r') else v for v in s]

def main(args):
    if len(args) != 2:
        return 2
    try:
        roster, scores = map(lines, args)
    except OSError:
        return 1
    if not roster or roster[0] != 'id,name,section' or not scores or scores[0] != 'id,assignment,points,max':
        return 1
    students = {}; bs = bp = orphans = 0
    ident = r'[A-Za-z0-9]{1,16}'
    for line in roster[1:]:
        if not line:
            continue
        a = line.split(',')
        if len(a) != 3 or not re.fullmatch(ident, a[0]) or not 1 <= len(a[1]) <= 40 or not re.fullmatch('[A-Z]', a[2]) or a[0] in students:
            bs += 1; continue
        students[a[0]] = (a[1], a[2], {})
    for line in scores[1:]:
        if not line:
            continue
        a = line.split(',')
        if len(a) != 4 or not re.fullmatch(ident, a[0]) or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', a[1]) or not all(re.fullmatch(r'[0-9]{1,6}', v) for v in a[2:]) or int(a[3]) < 1 or int(a[2]) > int(a[3]):
            bp += 1; continue
        if a[0] not in students:
            orphans += 1; continue
        students[a[0]][2][a[1]] = (int(a[2]), int(a[3]))
    rows = []
    for ident, (name, section, assignments) in students.items():
        p = sum(v[0] for v in assignments.values()); m = sum(v[1] for v in assignments.values())
        rows.append((section, ident, name, p, m))
    def compare(a, b):
        if a[0] != b[0]:
            return (a[0] > b[0]) - (a[0] < b[0])
        if bool(a[4]) != bool(b[4]):
            return -1 if a[4] else 1
        cross = a[3]*b[4] - b[3]*a[4]
        if cross:
            return -1 if cross > 0 else 1
        return (a[1] > b[1]) - (a[1] < b[1])
    summary = {}
    for s, ident, name, p, m in sorted(rows, key=cmp_to_key(compare)):
        counts = summary.setdefault(s, dict.fromkeys(['students','A','B','C','D','F','none'],0))
        counts['students'] += 1
        if not m:
            counts['none'] += 1; print(f'{s} {ident} {name} 0/0 - -'); continue
        letter = next((g for g, threshold in zip('ABCD', (90,80,70,60)) if 100*p >= threshold*m), 'F')
        counts[letter] += 1
        tenth = (2000*p + m)//(2*m)
        print(f'{s} {ident} {name} {p}/{m} {tenth//10}.{tenth%10}% {letter}')
    for s, counts in sorted(summary.items()):
        print(f'section {s}: ' + ' '.join(f'{k}={v}' for k, v in counts.items()))
    print(f'bad_students={bs} bad_scores={bp} orphans={orphans}')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
