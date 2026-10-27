import re
import sys


def simulate(requests, floors):
    waiting = [[] for _ in range(floors)]
    riding = [[] for _ in range(floors)]
    waiting_floors = set()
    destinations = set()
    boarded = [None] * len(requests)
    arrived = [None] * len(requests)
    next_request = completed = 0
    floor = tick = direction = 0
    moves = stops = total_wait = 0
    while completed < len(requests):
        while next_request < len(requests) and requests[next_request][0] == tick:
            _, origin, _ = requests[next_request]
            waiting[origin].append(next_request)
            waiting_floors.add(origin)
            next_request += 1
        if riding[floor] or waiting[floor]:
            stops += 1
            for passenger in riding[floor]:
                arrived[passenger] = tick
                completed += 1
            riding[floor].clear()
            destinations.discard(floor)
            for passenger in waiting[floor]:
                appeared, _, destination = requests[passenger]
                boarded[passenger] = tick
                total_wait += tick - appeared
                riding[destination].append(passenger)
                destinations.add(destination)
            waiting[floor].clear()
            waiting_floors.discard(floor)
            if completed == len(requests):
                break
        else:
            targets = waiting_floors | destinations
            if not targets:
                direction = 0
                # No state changes during idle ticks before the next request.
                tick = requests[next_request][0]
                continue
            if direction == 1:
                if not any(target > floor for target in targets):
                    direction = -1
            elif direction == -1:
                if not any(target < floor for target in targets):
                    direction = 1
            else:
                nearest = min(targets, key=lambda target: (abs(target - floor), -target))
                direction = 1 if nearest > floor else -1
            floor += direction
            moves += 1
        tick += 1
    for passenger, (board, arrival) in enumerate(zip(boarded, arrived), 1):
        print(f'{passenger} board={board} arrive={arrival}')
    print(f'moves={moves} stops={stops} finish={tick} total_wait={total_wait}')


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r'[0-9]{1,3}', sys.argv[1]) or not 2 <= int(sys.argv[1]) <= 100:
        print('Invalid floor count', file=sys.stderr)
        return 2
    floors = int(sys.argv[1])
    requests = []
    for raw in sys.stdin.buffer:
        line = raw.decode('utf-8', errors='replace').removesuffix('\n').removesuffix('\r')
        if not line.strip(' '):
            continue
        if not re.fullmatch(r'[0-9]{1,6} [0-9]{1,3} [0-9]{1,3}', line):
            print('Invalid request', file=sys.stderr)
            return 1
        time, origin, destination = map(int, line.split(' '))
        if origin >= floors or destination >= floors or origin == destination or requests and time < requests[-1][0]:
            print('Invalid request', file=sys.stderr)
            return 1
        requests.append((time, origin, destination))
    simulate(requests, floors)
    return 0


if __name__ == '__main__':
    sys.exit(main())
