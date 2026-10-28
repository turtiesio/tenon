from collections import defaultdict, deque
from datetime import date
import re
import sys


def money(cents):
    return f'{"-" if cents < 0 else ""}{abs(cents)//100}.{abs(cents)%100:02d}'


def read_rows(filename):
    with open(filename, 'rb') as source:
        data = source.read().decode('ascii')
    rows = []
    pattern = r'([0-9]{4}-[0-9]{2}-[0-9]{2}),(-?(?:0|[1-9][0-9]{0,8})\.[0-9]{2}),([\x20-\x7e]{1,40})'
    for number, line in enumerate(data.split('\n'), 1):
        line = line.removesuffix('\r')
        if not line:
            continue
        match = re.fullmatch(pattern, line)
        if not match:
            raise ValueError(f'invalid line {number}')
        day, amount, text = match.groups()
        parsed_date = date.fromisoformat(day)
        if not 1970 <= parsed_date.year <= 2099 or ',' in text or text.startswith(' ') or text.endswith(' '):
            raise ValueError(f'invalid line {number}')
        cents = int(amount.replace('.', ''))
        rows.append((number, day, cents, text, parsed_date.toordinal()))
    return rows


def main():
    days, files = 3, []
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg == '-d':
                value = next(args)
                if not re.fullmatch(r'0|[1-9][0-9]{0,2}', value) or int(value) > 365:
                    raise ValueError('invalid days')
                days = int(value)
            elif arg.startswith('-'):
                raise ValueError('unknown argument')
            else:
                files.append(arg)
        if len(files) != 2:
            raise ValueError('expected two files')
    except (ValueError, StopIteration) as exc:
        print('usage error:', exc, file=sys.stderr)
        return 2
    try:
        bank, ledger = map(read_rows, files)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    available = defaultdict(lambda: defaultdict(deque))
    for row in ledger:
        available[row[2]][row[4]].append(row[0])
    matched_ledger = set()
    unmatched_bank = []
    matches = []
    for row in bank:
        number, day, amount, text, ordinal = row
        candidates = []
        for ledger_day, numbers in available[amount].items():
            distance = abs(ledger_day-ordinal)
            if numbers and distance <= days:
                candidates.append((distance, numbers[0], ledger_day))
        if candidates:
            distance, other, ledger_day = min(candidates)
            available[amount][ledger_day].popleft()
            matched_ledger.add(other)
            matches.append(f'M {number} {other} {money(amount)} {distance}')
        else:
            unmatched_bank.append(row)
    unmatched_ledger = [row for row in ledger if row[0] not in matched_ledger]
    for line in matches:
        print(line)
    for label, rows in [('B', unmatched_bank), ('L', unmatched_ledger)]:
        for number, day, amount, text, _ in rows:
            print(f'{label} {number} {day} {money(amount)} {text}')
    diff = sum(row[2] for row in unmatched_bank) - sum(row[2] for row in unmatched_ledger)
    print(f'matched={len(matches)} bank_only={len(unmatched_bank)} ledger_only={len(unmatched_ledger)} diff={money(diff)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
