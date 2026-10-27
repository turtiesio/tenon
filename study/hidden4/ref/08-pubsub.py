"""Private specification reference: pattern matching and bounded queues."""
import re
import sys
from collections import deque
CLIENT = r'[a-z][a-z0-9]{0,15}'
NORMAL = r'[a-z0-9]{1,16}'
TOPIC = NORMAL+r'(?:\.'+NORMAL+r'){0,7}'
TEXT = r'[A-Za-z0-9_.!?-]{1,32}'

def pattern_ok(p):
    parts = p.split('.')
    return 1 <= len(parts) <= 8 and all(re.fullmatch(NORMAL, s) or s == '*' or (s == '#' and i == len(parts)-1) for i,s in enumerate(parts))

def matches(p, topic):
    ps, ts = p.split('.'), topic.split('.')
    if ps[-1] == '#':
        ps = ps[:-1]
        if len(ts) < len(ps): return False
    elif len(ps) != len(ts): return False
    return all(a == '*' or a == b for a,b in zip(ps,ts))

def main():
    if len(sys.argv) != 1:
        print('usage error', file=sys.stderr); return 2
    clients = {}
    def get(name):
        if name not in clients: clients[name] = [set(), deque(), 0]
        return clients[name]
    for raw in sys.stdin.buffer:
        line = raw.removesuffix(b'\n').removesuffix(b'\r').decode('latin1')
        parts = line.split(' ')
        response = 'ERR bad command'
        op = parts[0]
        if len(parts) == 3 and op in ('SUB', 'UNSUB') and re.fullmatch(CLIENT, parts[1]) and pattern_ok(parts[2]):
            patterns, queue, drop = get(parts[1])
            p = parts[2]
            if op == 'SUB':
                if p in patterns: response = 'ERR already subscribed'
                else: patterns.add(p); response = 'OK'
            else:
                if p not in patterns: response = 'ERR not subscribed'
                else: patterns.remove(p); response = 'OK'
        elif len(parts) == 3 and op == 'PUB' and re.fullmatch(TOPIC, parts[1]) and re.fullmatch(TEXT, parts[2]):
            n = 0
            for client in clients.values():
                patterns, queue, _ = client
                if any(matches(p, parts[1]) for p in patterns):
                    n += 1
                    if len(queue) == 3: queue.popleft(); client[2] += 1
                    queue.append(parts[1]+'='+parts[2])
            response = f'DELIVERED {n}'
        elif len(parts) == 3 and op == 'POLL' and re.fullmatch(CLIENT, parts[1]) and re.fullmatch('[1-9][0-9]{0,2}', parts[2]):
            queue = get(parts[1])[1]
            n = min(int(parts[2]), len(queue))
            response = f'MSGS {n}'+''.join(' '+queue.popleft() for _ in range(n))
        elif len(parts) == 2 and op == 'STATS' and re.fullmatch(CLIENT, parts[1]):
            subs, queue, drop = get(parts[1])
            response = f'subs={len(subs)} queued={len(queue)} dropped={drop}'
        print(response, flush=True)
    return 0
if __name__ == '__main__': sys.exit(main())
