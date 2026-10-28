import re
import sys
from pathlib import Path

NUMBER = r'[0-9]{1,6}'
BOOK_ID = r'[A-Za-z0-9-]{1,12}'


def records(path):
    for line in Path(path).read_bytes().decode('utf-8').split('\n'):
        line = line.removesuffix('\r')
        if line and not line.startswith('#'):
            yield line.split('|')


def money(cents):
    return f'{cents // 100}.{cents % 100:02d}'


def report(books_path, loans_path, today):
    books = {}
    for fields in records(books_path):
        if len(fields) != 4:
            raise ValueError('invalid book record')
        book_id, title, rate, cap = fields
        if (not re.fullmatch(BOOK_ID, book_id) or not title
                or not re.fullmatch(NUMBER, rate) or not re.fullmatch(NUMBER, cap)
                or book_id in books):
            raise ValueError('invalid book')
        books[book_id] = title, int(rate), int(cap)
    members = {}
    skipped = 0
    for fields in records(loans_path):
        if len(fields) != 5:
            raise ValueError('invalid loan record')
        member, book_id, out, due, returned = fields
        if (not re.fullmatch(r'[a-z][a-z0-9]{0,11}', member)
                or not re.fullmatch(BOOK_ID, book_id)
                or not re.fullmatch(NUMBER, out) or not re.fullmatch(NUMBER, due)
                or (returned != '-' and not re.fullmatch(NUMBER, returned))):
            raise ValueError('invalid loan')
        out, due = int(out), int(due)
        if due < out or (returned != '-' and int(returned) < out):
            raise ValueError('invalid day order')
        if book_id not in books:
            skipped += 1
            continue
        title, rate, cap = books[book_id]
        days = max(0, (today if returned == '-' else int(returned)) - due)
        fine = min(days * rate, cap)
        stats = members.setdefault(member, {'loans': 0, 'fine': 0, 'late': []})
        stats['loans'] += 1
        stats['fine'] += fine
        if days:
            stats['late'].append(f'  {book_id} {title} days={days} fine={money(fine)}')
    lines = []
    for member in sorted(members, key=lambda name: (-members[name]['fine'], name)):
        stats = members[member]
        lines.append(f"{member} loans={stats['loans']} late={len(stats['late'])} fine={money(stats['fine'])}")
        lines.extend(stats['late'])
    total = sum(stats['fine'] for stats in members.values())
    lines.append(f'total={money(total)} skipped={skipped}')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    if len(sys.argv) != 4 or not re.fullmatch(NUMBER, sys.argv[3]):
        print('expected BOOKS LOANS TODAY', file=sys.stderr)
        sys.exit(2)
    try:
        output = report(sys.argv[1], sys.argv[2], int(sys.argv[3]))
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
    sys.stdout.write(output)
