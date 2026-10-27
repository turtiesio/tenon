import re
import sys
from fractions import Fraction
from collections import Counter

def read(path, header):
    with open(path, encoding='ascii', newline='') as f:
        data = f.read().split('\n')
    if data[-1] == '':
        data.pop()
    data = [line.removesuffix('\r') for line in data]
    if not data or data[0] != header:
        raise ValueError
    return data[1:]

def matches(pattern, value):
    return re.fullmatch(pattern, value) is not None

def main():
    if len(sys.argv) != 3:
        return 2
    try:
        roster = read(sys.argv[1], 'id,name,section')
        scores = read(sys.argv[2], 'id,assignment,points,max')
    except (OSError, ValueError, UnicodeError):
        return 1
    students = {}
    bad_students = bad_scores = orphans = 0
    for line in roster:
        if not line:
            continue
        fields = line.split(',')
        if len(fields) != 3 or not matches(r'[A-Za-z0-9]{1,16}', fields[0]) or not 1 <= len(fields[1]) <= 40 or not matches(r'[A-Z]', fields[2]) or fields[0] in students:
            bad_students += 1
            continue
        ident, name, section = fields
        students[ident] = (name, section, {})
    for line in scores:
        if not line:
            continue
        fields = line.split(',')
        if len(fields) != 4 or not matches(r'[A-Za-z0-9]{1,16}', fields[0]) or not matches(r'[A-Za-z0-9_-]{1,32}', fields[1]) or any(not matches(r'[0-9]{1,6}', f) for f in fields[2:]) or not 1 <= int(fields[3]) or int(fields[2]) > int(fields[3]):
            bad_scores += 1
            continue
        ident, assignment, points, maximum = fields
        if ident not in students:
            orphans += 1
        else:
            students[ident][2][assignment] = (int(points), int(maximum))
    rows = []
    sections = {}
    for ident, (name, section, assignments) in students.items():
        points = sum(p for p, m in assignments.values())
        maximum = sum(m for p, m in assignments.values())
        letter = next((letter for threshold, letter in [(90, 'A'), (80, 'B'), (70, 'C'), (60, 'D')] if 100 * points >= threshold * maximum), 'F') if maximum else 'none'
        sections.setdefault(section, Counter())[letter] += 1
        rows.append((section, maximum == 0, -Fraction(points, maximum) if maximum else 0, ident, name, points, maximum, letter))
    for section, _, _, ident, name, points, maximum, letter in sorted(rows):
        if maximum:
            tenths = (2000 * points + maximum) // (2 * maximum)
            print(f'{section} {ident} {name} {points}/{maximum} {tenths // 10}.{tenths % 10}% {letter}')
        else:
            print(f'{section} {ident} {name} 0/0 - -')
    for section, counts in sorted(sections.items()):
        print(f'section {section}: students={sum(counts.values())} ' + ' '.join(f'{letter}={counts[letter]}' for letter in ['A', 'B', 'C', 'D', 'F', 'none']))
    print(f'bad_students={bad_students} bad_scores={bad_scores} orphans={orphans}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
