"""Private specification reference: ordered tick transitions with floor buckets."""
import re
import sys

def main():
    args = sys.argv[1:]
    if len(args) != 1 or not re.fullmatch('[0-9]{1,3}', args[0]) or not 2 <= int(args[0]) <= 100:
        print('usage error', file=sys.stderr); return 2
    floors = int(args[0])
    requests, previous = [], -1
    for raw in sys.stdin.buffer:
        line = raw.removesuffix(b'\n').removesuffix(b'\r').decode('latin1')
        if not line.strip(' '): continue
        if not re.fullmatch('[0-9]{1,6} [0-9]{1,3} [0-9]{1,3}', line):
            print('invalid request', file=sys.stderr); return 1
        time, start, end = map(int, line.split(' '))
        if time < previous or max(start,end) >= floors or start == end:
            print('invalid request', file=sys.stderr); return 1
        previous = time; requests.append((time,start,end))
    waiting, riding = {}, {}
    boarded, arrived = [None]*len(requests), [None]*len(requests)
    tick = floor = direction = moves = stops = completed = cursor = 0
    while completed < len(requests):
        while cursor < len(requests) and requests[cursor][0] == tick:
            waiting.setdefault(requests[cursor][1], []).append(cursor); cursor += 1
        if floor in riding or floor in waiting:
            stops += 1
            for i in riding.pop(floor, []): arrived[i] = tick; completed += 1
            for i in waiting.pop(floor, []):
                boarded[i] = tick; riding.setdefault(requests[i][2], []).append(i)
        else:
            targets = set(waiting) | set(riding)
            if not targets:
                direction = 0
                if cursor < len(requests): tick = requests[cursor][0]-1
            else:
                if direction == 1 and not any(x > floor for x in targets): direction = -1
                elif direction == -1 and not any(x < floor for x in targets): direction = 1
                elif direction == 0:
                    nearest = min(targets, key=lambda x: (abs(x-floor), -x))
                    direction = 1 if nearest > floor else -1
                floor += direction; moves += 1
        if completed == len(requests): break
        tick += 1
    for i in range(len(requests)): print(f'{i+1} board={boarded[i]} arrive={arrived[i]}')
    wait = sum(boarded[i]-r[0] for i,r in enumerate(requests))
    print(f'moves={moves} stops={stops} finish={tick} total_wait={wait}')
    return 0
if __name__ == '__main__': sys.exit(main())
