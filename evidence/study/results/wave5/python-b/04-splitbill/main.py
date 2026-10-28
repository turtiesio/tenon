import re
import sys
from collections import defaultdict


def money(cents, signed=False):
    sign = ('+' if cents > 0 else '-') if signed and cents else ''
    cents = abs(cents)
    return f'{sign}{cents // 100}.{cents % 100:02d}'


def report(data):
    balances = defaultdict(int)
    for line in data.split('\n'):
        line = line.removesuffix('\r')
        tokens = re.findall(r'[^ \t]+', line)
        if not tokens or tokens[0].startswith('#'):
            continue
        kind = tokens[0]
        if kind == 'expense' and len(tokens) >= 4:
            names = [tokens[1]] + tokens[3:]
            amount_text = tokens[2]
            if len(set(tokens[3:])) != len(tokens[3:]):
                raise ValueError('duplicate participant')
        elif kind == 'transfer' and len(tokens) == 4:
            names = tokens[1:3]
            amount_text = tokens[3]
            if names[0] == names[1]:
                raise ValueError('self transfer')
        else:
            raise ValueError('invalid record')
        if any(not re.fullmatch(r'[a-z][a-z0-9_]{0,15}', name) for name in names):
            raise ValueError('invalid name')
        if not re.fullmatch(r'[0-9]{1,7}\.[0-9]{2}', amount_text):
            raise ValueError('invalid amount')
        amount = int(amount_text.replace('.', ''))
        if not amount:
            raise ValueError('zero amount')
        if kind == 'expense':
            balances[names[0]] += amount
            share, remainder = divmod(amount, len(names) - 1)
            for index, name in enumerate(names[1:]):
                balances[name] -= share + (index < remainder)
        else:
            balances[names[0]] += amount
            balances[names[1]] -= amount
    lines = [f'{name} {money(balances[name], True)}' for name in sorted(balances)]
    lines.append('--')
    remaining = dict(balances)
    while remaining:
        debtor = min(remaining, key=lambda name: (remaining[name], name))
        if remaining[debtor] >= 0:
            break
        creditor = min(remaining, key=lambda name: (-remaining[name], name))
        amount = min(-remaining[debtor], remaining[creditor])
        lines.append(f'{debtor} pays {creditor} {money(amount)}')
        remaining[debtor] += amount
        remaining[creditor] -= amount
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    if len(sys.argv) != 1:
        print('no arguments allowed', file=sys.stderr)
        sys.exit(2)
    try:
        result = report(sys.stdin.read())
    except ValueError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
    sys.stdout.write(result)
