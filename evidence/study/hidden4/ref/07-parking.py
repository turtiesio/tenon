"""Private specification reference: monotone clock and lowest free spot."""
import re
import sys

def money(c): return f'{c//100}.{c%100:02d}'
def main():
    args = sys.argv[1:]
    if len(args) != 1 or not re.fullmatch('[0-9]{1,4}', args[0]) or not 1 <= int(args[0]) <= 1000:
        print('usage error', file=sys.stderr); return 2
    capacity = int(args[0])
    parked, clock, revenue = {}, 0, 0
    for raw in sys.stdin.buffer:
        line = raw.removesuffix(b'\n').removesuffix(b'\r').decode('latin1')
        response = 'ERR bad command'
        move = re.fullmatch(r'(IN|OUT) ([A-Z0-9]{1,8}) ([0-9]{1,7})', line)
        where = re.fullmatch(r'WHERE ([A-Z0-9]{1,8})', line)
        if move:
            op, plate, t = move[1], move[2], int(move[3])
            if t < clock: response = 'ERR bad time'
            else:
                clock = t
                if op == 'IN':
                    if plate in parked: response = 'ERR already parked'
                    elif len(parked) == capacity: response = 'FULL'
                    else:
                        used = {x[0] for x in parked.values()}
                        spot = next(i for i in range(1, capacity+1) if i not in used)
                        parked[plate] = (spot, t); response = f'OK {spot}'
                elif plate not in parked: response = 'ERR not parked'
                else:
                    spot, entered = parked.pop(plate)
                    d = t-entered
                    fee = 0 if d <= 15 else (d//1440)*2000 + min(2000, 250*((d%1440+59)//60))
                    revenue += fee; response = 'FEE '+money(fee)
        elif where:
            response = f'SPOT {parked[where[1]][0]}' if where[1] in parked else 'ERR not parked'
        elif line == 'STATUS': response = f'free={capacity-len(parked)} parked={len(parked)} revenue={money(revenue)}'
        print(response, flush=True)
    return 0
if __name__ == '__main__': sys.exit(main())
