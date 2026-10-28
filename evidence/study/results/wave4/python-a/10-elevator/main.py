import re
import sys
from collections import namedtuple

FLOORS_RE = re.compile(r"[0-9]{1,3}")
REQUEST_RE = re.compile(r"([0-9]{1,6}) ([0-9]{1,3}) ([0-9]{1,3})")

Request = namedtuple("Request", "time origin dest")

UP, DOWN, IDLE = 1, -1, 0


def parse_requests(text, floors):
    """Return the requests, or None if the input is invalid."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    requests = []
    for line in lines:
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip(" ") == "":
            continue
        m = REQUEST_RE.fullmatch(line)
        if not m:
            return None
        req = Request(*(int(g) for g in m.groups()))
        if req.origin >= floors or req.dest >= floors or req.origin == req.dest:
            return None
        if requests and req.time < requests[-1].time:
            return None
        requests.append(req)
    return requests


def nearest_direction(mask, floor, floors):
    """Direction towards the nearest target floor; a tie goes up."""
    for dist in range(1, floors):
        if floor + dist < floors and mask >> (floor + dist) & 1:
            return UP
        if floor - dist >= 0 and mask >> (floor - dist) & 1:
            return DOWN
    return IDLE


def choose_direction(mask, floor, direction, floors):
    above = mask >> (floor + 1) != 0
    below = mask & ((1 << floor) - 1) != 0
    if direction == UP:
        return UP if above else DOWN
    if direction == DOWN:
        return DOWN if below else UP
    return nearest_direction(mask, floor, floors)


def simulate(requests, floors):
    n = len(requests)
    board = [0] * n
    arrive = [0] * n
    waiting = [[] for _ in range(floors)]  # passenger indexes per floor
    riding = [[] for _ in range(floors)]   # passengers on board, per destination
    mask = 0  # bit f set when floor f is a target (someone waits or rides to it)
    floor, direction = 0, IDLE
    moves = stops = arrived = 0
    next_req = 0
    t = 0
    finish = 0

    while arrived < n:
        while next_req < n and requests[next_req].time == t:
            origin = requests[next_req].origin
            waiting[origin].append(next_req)
            mask |= 1 << origin
            next_req += 1

        if waiting[floor] or riding[floor]:
            for p in riding[floor]:
                arrive[p] = t
                arrived += 1
            riding[floor] = []
            for p in waiting[floor]:
                board[p] = t
                dest = requests[p].dest
                riding[dest].append(p)
                mask |= 1 << dest
            waiting[floor] = []
            mask &= ~(1 << floor)
            stops += 1
            finish = t
            t += 1
            continue

        if mask == 0:
            direction = IDLE
            t = requests[next_req].time  # nothing to do until the next arrival
            continue

        direction = choose_direction(mask, floor, direction, floors)
        floor += direction
        moves += 1
        t += 1

    return board, arrive, moves, stops, finish


def main():
    argv = sys.argv[1:]
    if len(argv) != 1 or not FLOORS_RE.fullmatch(argv[0]) or not 2 <= int(argv[0]) <= 100:
        print("elevator: usage: elevator FLOORS (2-100)", file=sys.stderr)
        sys.exit(2)
    floors = int(argv[0])

    text = sys.stdin.buffer.read().decode("latin-1")
    requests = parse_requests(text, floors)
    if requests is None:
        print("elevator: invalid input", file=sys.stderr)
        sys.exit(1)

    board, arrive, moves, stops, finish = simulate(requests, floors)
    total_wait = sum(b - r.time for b, r in zip(board, requests))
    out = [f"{i} board={b} arrive={a}\n" for i, (b, a) in enumerate(zip(board, arrive), 1)]
    out.append(f"moves={moves} stops={stops} finish={finish} total_wait={total_wait}\n")
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
