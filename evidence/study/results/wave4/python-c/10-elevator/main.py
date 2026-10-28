"""elevator: tick-by-tick simulation of a single elevator."""
import re
import sys
from collections import defaultdict
from dataclasses import dataclass

REQUEST_RE = re.compile(r"([0-9]{1,6}) ([0-9]{1,3}) ([0-9]{1,3})")
UP, DOWN, IDLE = 1, -1, 0


class InputError(Exception):
    pass


@dataclass
class Passenger:
    time: int
    src: int
    dst: int
    board: int = -1
    arrive: int = -1


def read_lines(data):
    text = data.decode("latin-1")
    if not text:
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def parse_requests(lines, floors):
    passengers = []
    for number, line in enumerate(lines, 1):
        if not line.strip(" "):
            continue
        m = REQUEST_RE.fullmatch(line)
        if not m:
            raise InputError(f"line {number}: malformed request {line!r}")
        time, src, dst = map(int, m.groups())
        if src >= floors or dst >= floors:
            raise InputError(f"line {number}: no such floor")
        if src == dst:
            raise InputError(f"line {number}: from equals to")
        if passengers and time < passengers[-1].time:
            raise InputError(f"line {number}: time goes backwards")
        passengers.append(Passenger(time, src, dst))
    return passengers


def choose_direction(direction, floor, targets):
    if direction == UP and max(targets) > floor:
        return UP
    if direction == DOWN and min(targets) < floor:
        return DOWN
    if direction == UP:
        return DOWN
    if direction == DOWN:
        return UP
    nearest = min(abs(t - floor) for t in targets)
    return UP if floor + nearest in targets else DOWN


def simulate(passengers):
    """Run the simulation, filling in board/arrive ticks; return (moves, stops, finish)."""
    waiting = defaultdict(list)   # floor -> passengers waiting there
    riding = defaultdict(list)    # destination floor -> passengers on board
    targets = set()               # floors with someone waiting or someone riding to them
    moves = stops = finish = 0
    floor, direction, tick = 0, IDLE, 0
    upcoming, remaining = 0, len(passengers)

    while remaining:
        while upcoming < len(passengers) and passengers[upcoming].time == tick:
            p = passengers[upcoming]
            waiting[p.src].append(p)
            targets.add(p.src)
            upcoming += 1

        if floor in targets:
            stops += 1
            for p in riding.pop(floor, []):
                p.arrive = tick
                remaining -= 1
            for p in waiting.pop(floor, []):
                p.board = tick
                riding[p.dst].append(p)
                targets.add(p.dst)
            targets.discard(floor)  # boarders never ride to the floor they board on
            if not remaining:
                finish = tick
        elif not targets:
            # Nothing to do until the next passenger appears: skip the idle ticks.
            direction = IDLE
            tick = passengers[upcoming].time
            continue
        else:
            direction = choose_direction(direction, floor, targets)
            floor += direction
            moves += 1
        tick += 1
    return moves, stops, finish


def main(argv):
    if len(argv) != 1 or not re.fullmatch(r"[0-9]{1,3}", argv[0]) or not 2 <= int(argv[0]) <= 100:
        print("usage: elevator FLOORS  (2-100)", file=sys.stderr)
        return 2
    try:
        passengers = parse_requests(read_lines(sys.stdin.buffer.read()), int(argv[0]))
    except InputError as e:
        print(f"elevator: {e}", file=sys.stderr)
        return 1

    moves, stops, finish = simulate(passengers)
    out = [f"{i} board={p.board} arrive={p.arrive}\n" for i, p in enumerate(passengers, 1)]
    total_wait = sum(p.board - p.time for p in passengers)
    out.append(f"moves={moves} stops={stops} finish={finish} total_wait={total_wait}\n")
    sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
