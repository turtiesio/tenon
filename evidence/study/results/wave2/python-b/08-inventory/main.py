import heapq
import re
import sys
from collections import Counter

TIME = r'[0-9]{1,12}'
SKU = r'[A-Z0-9-]{1,20}'
NUM = r'[0-9]{1,9}'
PATTERNS = [re.compile(p) for p in [f'({TIME}) (ADD|REMOVE) ({SKU}) ({NUM})', f'({TIME}) (RESERVE) ({SKU}) ({NUM}) ({NUM})', f'({TIME}) (COMMIT|RELEASE) ({NUM})', f'({TIME}) (AVAIL) ({SKU})', f'({TIME}) (STATS)']]

def main():
    if len(sys.argv) != 1:
        return 2
    stock = {}
    holds = {}
    expiry = []
    counts = Counter()
    clock = 0
    next_id = 1
    def finish(ident, state):
        hold = holds[ident]
        stock[hold[0]][1] -= hold[1]
        hold[2] = state
        counts['holds'] -= 1
        counts[state] += 1
    def process(line):
        nonlocal clock, next_id
        match = next((m for pattern in PATTERNS if (m := pattern.fullmatch(line))), None)
        if match is None:
            return 'ERR bad command'
        values = match.groups()
        time, command = int(values[0]), values[1]
        if command in ('ADD', 'REMOVE', 'RESERVE') and (int(values[3]) == 0 or (command == 'RESERVE' and int(values[4]) == 0)):
            return 'ERR bad command'
        if time < clock:
            return 'ERR time went backwards'
        clock = time
        while expiry and expiry[0][0] <= time:
            _, ident = heapq.heappop(expiry)
            if holds[ident][2] == 'active':
                finish(ident, 'expired')
        if command == 'STATS':
            return ' '.join(f'{key}={counts[key]}' for key in ('holds', 'committed', 'expired', 'released'))
        if command in ('COMMIT', 'RELEASE'):
            ident = int(values[2])
            if ident not in holds or holds[ident][2] in ('committed', 'released'):
                return 'ERR no such hold'
            if holds[ident][2] == 'expired':
                return 'ERR expired'
            if command == 'COMMIT':
                sku, qty, _ = holds[ident]
                stock[sku][0] -= qty
            finish(ident, 'committed' if command == 'COMMIT' else 'released')
            return 'OK'
        sku = values[2]
        quantities = stock.setdefault(sku, [0, 0])
        available = quantities[0] - quantities[1]
        if command == 'AVAIL':
            return f'{sku} on_hand={quantities[0]} held={quantities[1]} available={available}'
        qty = int(values[3])
        if command == 'ADD':
            quantities[0] += qty
            return f'OK {quantities[0]}'
        if qty > available:
            return f'ERR insufficient {available}'
        if command == 'REMOVE':
            quantities[0] -= qty
            return f'OK {quantities[0]}'
        ident = next_id
        next_id += 1
        holds[ident] = [sku, qty, 'active']
        quantities[1] += qty
        counts['holds'] += 1
        heapq.heappush(expiry, (time + int(values[4]), ident))
        return f'HOLD {ident}'
    for line in sys.stdin:
        print(process(line.removesuffix('\n').removesuffix('\r')), flush=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
