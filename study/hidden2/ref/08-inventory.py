"""Private inventory state-machine oracle."""
import re
import sys
T = r'[0-9]{1,12}'
SKU = r'[A-Z0-9-]{1,20}'
Q = r'[0-9]{1,9}'
FORMS = [rf'{T} (?:ADD|REMOVE) {SKU} {Q}', rf'{T} RESERVE {SKU} {Q} {Q}', rf'{T} (?:COMMIT|RELEASE) {Q}', rf'{T} AVAIL {SKU}', rf'{T} STATS']

def main(args):
    if args:
        return 2
    clock = 0; stock = {}; holds = {}; next_id = 1
    for raw in sys.stdin.buffer:
        line = raw.decode('ascii').removesuffix('\n').removesuffix('\r')
        if not any(re.fullmatch(form, line) for form in FORMS):
            print('ERR bad command', flush=True); continue
        v = line.split(' '); t = int(v[0]); cmd = v[1]
        if (cmd in ('ADD','REMOVE','RESERVE') and int(v[3]) == 0) or (cmd == 'RESERVE' and int(v[4]) == 0):
            print('ERR bad command', flush=True); continue
        if t < clock:
            print('ERR time went backwards', flush=True); continue
        clock = t
        for h in holds.values():
            if h['state'] == 'active' and h['expiry'] <= t:
                h['state'] = 'expired'
        if cmd == 'STATS':
            counts = {s:sum(h['state'] == s for h in holds.values()) for s in ('active','committed','expired','released')}
            response = f'holds={counts["active"]} committed={counts["committed"]} expired={counts["expired"]} released={counts["released"]}'
        elif cmd in ('COMMIT','RELEASE'):
            h = holds.get(int(v[2]))
            if h is None or h['state'] in ('committed','released'):
                response = 'ERR no such hold'
            elif h['state'] == 'expired':
                response = 'ERR expired'
            else:
                if cmd == 'COMMIT':
                    stock[h['sku']] -= h['qty']
                h['state'] = 'committed' if cmd == 'COMMIT' else 'released'; response = 'OK'
        else:
            sku = v[2]; on_hand = stock.get(sku,0)
            held = sum(h['qty'] for h in holds.values() if h['sku'] == sku and h['state'] == 'active')
            available = on_hand-held
            if cmd == 'AVAIL':
                response = f'{sku} on_hand={on_hand} held={held} available={available}'
            else:
                qty = int(v[3])
                if cmd != 'ADD' and qty > available:
                    response = f'ERR insufficient {available}'
                elif cmd == 'RESERVE':
                    holds[next_id] = dict(sku=sku, qty=qty, expiry=t+int(v[4]), state='active')
                    response = f'HOLD {next_id}'; next_id += 1
                else:
                    stock[sku] = on_hand + (qty if cmd == 'ADD' else -qty)
                    response = f'OK {stock[sku]}'
        print(response, flush=True)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
