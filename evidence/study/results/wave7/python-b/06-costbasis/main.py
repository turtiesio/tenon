from collections import defaultdict, deque
import re
import sys


def money(value):
    return f'{"-" if value < 0 else ""}{abs(value)//100}.{abs(value)%100:02d}'


def main():
    if len(sys.argv) != 1:
        print('no arguments allowed', file=sys.stderr)
        return 2
    lots = defaultdict(deque)
    total = 0
    failed = False
    trade_pattern = r'(BUY|SELL) ([A-Z]{1,5}) ([1-9][0-9]{0,5}) ((?:0|[1-9][0-9]{0,5})\.[0-9]{2})'
    for number, line in enumerate(sys.stdin.buffer.read().decode('ascii').split('\n'), 1):
        line = line.removesuffix('\r')
        if not line or line.startswith('#'):
            continue
        trade = re.fullmatch(trade_pattern, line)
        split = re.fullmatch(r'SPLIT ([A-Z]{1,5}) ([2-9]|10)', line)
        if not trade and not split:
            print(f'{number}: ERR bad line')
            failed = True
            continue
        if split:
            symbol, ratio = split.groups()
            if not lots[symbol]:
                print(f'{number}: ERR not held {symbol}')
                failed = True
            else:
                for lot in lots[symbol]:
                    lot[0] *= int(ratio)
                held = sum(q for q, _ in lots[symbol])
                print(f'{number}: SPLIT {symbol} {ratio} held={held}')
            continue
        action, symbol, quantity, price = trade.groups()
        quantity, price = int(quantity), int(price.replace('.', ''))
        if action == 'BUY':
            lots[symbol].append([quantity, quantity*price])
            continue
        held = sum(q for q, _ in lots[symbol])
        if quantity > held:
            print(f'{number}: ERR insufficient {symbol} held={held}')
            failed = True
            continue
        needed, cost = quantity, 0
        while needed:
            q, c = lots[symbol][0]
            if needed >= q:
                cost += c
                needed -= q
                lots[symbol].popleft()
            else:
                part = (2*c*needed + q) // (2*q)
                lots[symbol][0] = [q-needed, c-part]
                cost += part
                needed = 0
        proceeds = quantity*price
        gain = proceeds-cost
        total += gain
        print(f'{number}: SELL {symbol} {quantity} proceeds={money(proceeds)} cost={money(cost)} gain={money(gain)}')
    for symbol in sorted(lots):
        if lots[symbol]:
            held = sum(q for q, _ in lots[symbol])
            cost = sum(c for _, c in lots[symbol])
            print(f'HOLD {symbol} {held} cost={money(cost)} lots={len(lots[symbol])}')
    print(f'TOTAL gain={money(total)}')
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
