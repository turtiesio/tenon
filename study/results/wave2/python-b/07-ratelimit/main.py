import re
import sys

NAME = r'[a-z0-9_.-]{1,32}'
NUMBER = r'[0-9]{1,9}'
TIME = r'[0-9]{1,15}'
PATTERNS = [re.compile(p) for p in [f'POLICY ({NAME}) ({NUMBER}) ({NUMBER})', f'HIT ({TIME}) ({NAME}) ({NAME})(?: ({NUMBER}))?', f'PEEK ({TIME}) ({NAME}) ({NAME})', f'RESET ({NAME}) ({NAME})', f'STATS ({NAME})']]

def main():
    if len(sys.argv) != 1:
        return 2
    policies = {}
    clock = 0
    def process(line):
        nonlocal clock
        match = next((m for pattern in PATTERNS if (m := pattern.fullmatch(line))), None)
        if match is None:
            return 'ERR bad command'
        command = line.split(' ', 1)[0]
        values = match.groups()
        if command == 'POLICY':
            name, capacity, interval = values
            capacity, interval = int(capacity), int(interval)
            if not capacity or not interval:
                return 'ERR bad command'
            if name in policies:
                return 'ERR policy exists'
            policies[name] = {'capacity': capacity, 'interval': interval, 'buckets': {}, 'allowed': 0, 'denied': 0}
            return 'OK'
        if command in ('HIT', 'PEEK'):
            now, name, client = int(values[0]), values[1], values[2]
            cost = int(values[3] or '1') if command == 'HIT' else 1
            if not cost:
                return 'ERR bad command'
            if now < clock:
                return 'ERR time went backwards'
            clock = now
        else:
            name = values[0]
        if name not in policies:
            return 'ERR no such policy'
        policy = policies[name]
        buckets = policy['buckets']
        if command == 'STATS':
            return f"allowed={policy['allowed']} denied={policy['denied']} clients={len(buckets)}"
        if command == 'RESET':
            client = values[1]
            if client not in buckets:
                return 'ERR no such client'
            del buckets[client]
            return 'OK'
        capacity, interval = policy['capacity'], policy['interval']
        if command == 'HIT' and cost > capacity:
            return 'ERR cost exceeds capacity'
        tokens, anchor = buckets.get(client, (capacity, now))
        if tokens == capacity:
            anchor = now
        else:
            refill = (now - anchor) // interval
            tokens = min(capacity, tokens + refill)
            anchor = now if tokens == capacity else anchor + refill * interval
        if command == 'PEEK':
            response = f'TOKENS {tokens}'
        elif tokens >= cost:
            tokens -= cost
            policy['allowed'] += 1
            response = f'ALLOW {tokens}'
        else:
            policy['denied'] += 1
            response = f'DENY {anchor + (cost - tokens) * interval - now}'
        buckets[client] = tokens, anchor
        return response
    for line in sys.stdin:
        print(process(line.removesuffix('\n').removesuffix('\r')), flush=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
