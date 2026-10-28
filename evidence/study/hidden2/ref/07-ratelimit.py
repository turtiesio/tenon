"""Private logical-clock token bucket oracle."""
import re
import sys
NAME = r'[a-z0-9_.-]{1,32}'
POS = r'[0-9]{1,9}'
FORMS = [rf'POLICY ({NAME}) ({POS}) ({POS})', rf'HIT ([0-9]{{1,15}}) ({NAME}) ({NAME})(?: ({POS}))?', rf'PEEK ([0-9]{{1,15}}) ({NAME}) ({NAME})', rf'RESET ({NAME}) ({NAME})', rf'STATS ({NAME})']

def main(args):
    if args:
        return 2
    policies = {}; clock = 0
    for raw in sys.stdin.buffer:
        line = raw.decode('ascii').removesuffix('\n').removesuffix('\r')
        m = next((m for form in FORMS if (m := re.fullmatch(form, line))), None)
        if not m:
            print('ERR bad command', flush=True); continue
        v = line.split(' '); cmd = v[0]
        if (cmd == 'POLICY' and (int(v[2]) == 0 or int(v[3]) == 0)) or (cmd == 'HIT' and len(v) == 5 and int(v[4]) == 0):
            print('ERR bad command', flush=True); continue
        if cmd in ('HIT','PEEK'):
            t = int(v[1])
            if t < clock:
                print('ERR time went backwards', flush=True); continue
            clock = t; p = v[2]
        else:
            p = v[1]
        if cmd == 'POLICY':
            if p in policies:
                response = 'ERR policy exists'
            else:
                policies[p] = dict(cap=int(v[2]), interval=int(v[3]), buckets={}, allowed=0, denied=0)
                response = 'OK'
        elif p not in policies:
            response = 'ERR no such policy'
        else:
            state = policies[p]; buckets = state['buckets']; cap = state['cap']; interval = state['interval']
            cost = int(v[4]) if cmd == 'HIT' and len(v) == 5 else 1
            if cmd == 'STATS':
                response = f'allowed={state["allowed"]} denied={state["denied"]} clients={len(buckets)}'
            elif cmd == 'RESET':
                response = 'OK' if buckets.pop(v[2], None) is not None else 'ERR no such client'
            elif cmd == 'HIT' and cost > cap:
                response = 'ERR cost exceeds capacity'
            else:
                client = v[3]
                tokens, anchor = buckets.get(client, (cap, t))
                if tokens == cap:
                    anchor = t
                else:
                    k = (t-anchor)//interval; tokens = min(cap, tokens+k)
                    anchor = t if tokens == cap else anchor+k*interval
                if cmd == 'PEEK':
                    response = f'TOKENS {tokens}'
                elif tokens >= cost:
                    tokens -= cost; state['allowed'] += 1; response = f'ALLOW {tokens}'
                else:
                    state['denied'] += 1; response = f'DENY {anchor+(cost-tokens)*interval-t}'
                buckets[client] = (tokens, anchor)
        print(response, flush=True)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
