import re
import sys


def checksum(scheme, digits):
    if scheme == 'luhn':
        return sum((2*d - 9 if 2*d > 9 else 2*d) if i % 2 else d
                   for i, d in enumerate(reversed(digits))) % 10
    if scheme == 'isbn10':
        return sum((10-i)*d for i, d in enumerate(digits)) % 11
    return sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits)) % 10


def main():
    args = sys.argv[1:]
    if len(args) < 3 or args[0] not in ('luhn', 'isbn10', 'isbn13') or args[1] not in ('check', 'make'):
        print('invalid usage', file=sys.stderr)
        return 2
    scheme, mode = args[:2]
    failed = False
    for value in args[2:]:
        raw = value.replace('-', '')
        valid = re.fullmatch(r'[0-9X]+(-[0-9X]+)*', value) is not None
        if 'X' in raw:
            valid = valid and scheme == 'isbn10' and mode == 'check' and raw.count('X') == 1 and raw.endswith('X')
        if scheme == 'luhn':
            valid = valid and (2 <= len(raw) <= 19 if mode == 'check' else 1 <= len(raw) <= 18)
        else:
            valid = valid and len(raw) == (10 if scheme == 'isbn10' else 13) - (mode == 'make')
        if scheme == 'isbn13':
            valid = valid and raw.startswith(('978', '979'))
        if not valid:
            print(value + ' invalid')
            failed = True
            continue
        digits = [10 if c == 'X' else int(c) for c in raw]
        if mode == 'check':
            correct = checksum(scheme, digits) == 0
            print(value + (' ok' if correct else ' bad'))
            failed |= not correct
        else:
            check = next(c for c in range(11 if scheme == 'isbn10' else 10) if checksum(scheme, digits + [c]) == 0)
            print(value + ('-' if '-' in value else '') + ('X' if check == 10 else str(check)))
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
