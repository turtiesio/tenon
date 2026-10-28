import re
import sys
from dataclasses import dataclass

TICKS_RE = re.compile(r"[0-9]{1,5}")
PROGRAM_RE = re.compile(r"([A-Z]):([NESW.]{0,100})")
DELTAS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
MAX_SIZE = 50


class InputError(Exception):
    pass


@dataclass
class Robot:
    letter: str
    x: int
    y: int
    program: str = ""
    moves: int = 0
    bumps: int = 0
    coins: int = 0


def read_lines():
    text = sys.stdin.buffer.read().decode("utf-8")
    if not text:
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def parse_world(lines):
    """Return (grid as a list of lists, robots by letter)."""
    blank = lines.index("") if "" in lines else len(lines)
    rows, program_lines = lines[:blank], lines[blank + 1:]

    if not rows:
        raise InputError("missing grid")
    width = len(rows[0])
    if len(rows) > MAX_SIZE or not 1 <= width <= MAX_SIZE:
        raise InputError("grid must have 1 to 50 rows of 1 to 50 characters")
    grid = []
    robots = {}
    for y, row in enumerate(rows):
        if len(row) != width:
            raise InputError(f"grid row {y + 1} has a different length")
        cells = []
        for x, ch in enumerate(row):
            if "A" <= ch <= "Z":
                if ch in robots:
                    raise InputError(f"robot {ch} appears twice")
                robots[ch] = Robot(ch, x, y)
                cells.append(".")
            elif ch in ".#*":
                cells.append(ch)
            else:
                raise InputError(f"unknown grid character {ch!r}")
        grid.append(cells)

    seen = set()
    for line in program_lines:
        match = PROGRAM_RE.fullmatch(line)
        if not match:
            raise InputError(f"malformed program line {line!r}")
        letter, moves = match.groups()
        if letter not in robots:
            raise InputError(f"program for unknown robot {letter}")
        if letter in seen:
            raise InputError(f"two programs for robot {letter}")
        seen.add(letter)
        robots[letter].program = moves
    return grid, robots


def simulate(grid, robots, ticks):
    height, width = len(grid), len(grid[0])
    occupied = {(r.x, r.y) for r in robots.values()}
    active = [r for _, r in sorted(robots.items()) if r.program]
    for t in range(ticks):
        for robot in active:
            move = robot.program[t % len(robot.program)]
            if move == ".":
                continue
            dx, dy = DELTAS[move]
            nx, ny = robot.x + dx, robot.y + dy
            if (not (0 <= nx < width and 0 <= ny < height)
                    or grid[ny][nx] == "#" or (nx, ny) in occupied):
                robot.bumps += 1
                continue
            occupied.remove((robot.x, robot.y))
            occupied.add((nx, ny))
            robot.x, robot.y = nx, ny
            robot.moves += 1
            if grid[ny][nx] == "*":
                robot.coins += 1
                grid[ny][nx] = "."


def main():
    args = sys.argv[1:]
    if len(args) != 1 or not TICKS_RE.fullmatch(args[0]):
        print("usage: robots TICKS", file=sys.stderr)
        sys.exit(2)

    try:
        grid, robots = parse_world(read_lines())
    except InputError as e:
        print(f"robots: {e}", file=sys.stderr)
        sys.exit(1)

    simulate(grid, robots, int(args[0]))

    for robot in robots.values():
        grid[robot.y][robot.x] = robot.letter
    out = ["".join(row) + "\n" for row in grid]
    for letter in sorted(robots):
        r = robots[letter]
        out.append(f"{letter} {r.x} {r.y} moves={r.moves} bumps={r.bumps} coins={r.coins}\n")
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
