import re
import sys

TICKS_RE = re.compile(r"[0-9]{1,5}")
PROGRAM_RE = re.compile(r"([A-Z]):([NESW.]{0,100})")
GRID_CHARS = set(".#*") | set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
DIRECTIONS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}


class InvalidInput(Exception):
    pass


class Robot:
    def __init__(self, letter, x, y):
        self.letter = letter
        self.x = x
        self.y = y
        self.program = ""
        self.moves = 0
        self.bumps = 0
        self.coins = 0


def parse_world(lines):
    try:
        blank = lines.index("")
        grid_lines, program_lines = lines[:blank], lines[blank + 1:]
    except ValueError:
        grid_lines, program_lines = lines, []

    if not grid_lines:
        raise InvalidInput("missing grid")
    if len(grid_lines) > 50:
        raise InvalidInput("too many rows")
    width = len(grid_lines[0])
    if not 1 <= width <= 50:
        raise InvalidInput("bad row length")

    cells = []
    robots = {}
    for y, row in enumerate(grid_lines):
        if len(row) != width:
            raise InvalidInput("rows have different lengths")
        cell_row = []
        for x, ch in enumerate(row):
            if ch not in GRID_CHARS:
                raise InvalidInput("unknown grid character %r" % ch)
            if ch.isalpha():
                if ch in robots:
                    raise InvalidInput("robot %s appears twice" % ch)
                robots[ch] = Robot(ch, x, y)
                ch = "."
            cell_row.append(ch)
        cells.append(cell_row)

    seen = set()
    for line in program_lines:
        m = PROGRAM_RE.fullmatch(line)
        if not m:
            raise InvalidInput("malformed program line: %r" % line)
        letter, moves = m.groups()
        if letter not in robots:
            raise InvalidInput("no robot %s on the grid" % letter)
        if letter in seen:
            raise InvalidInput("two programs for robot %s" % letter)
        seen.add(letter)
        robots[letter].program = moves
    return cells, robots


def simulate(cells, robots, ticks):
    height, width = len(cells), len(cells[0])
    occupied = {(r.x, r.y) for r in robots.values()}
    order = [robots[letter] for letter in sorted(robots) if robots[letter].program]
    for t in range(ticks):
        for robot in order:
            program = robot.program
            move = program[t % len(program)]
            if move == ".":
                continue
            dx, dy = DIRECTIONS[move]
            nx, ny = robot.x + dx, robot.y + dy
            if (not (0 <= nx < width and 0 <= ny < height)
                    or cells[ny][nx] == "#"
                    or (nx, ny) in occupied):
                robot.bumps += 1
                continue
            occupied.remove((robot.x, robot.y))
            occupied.add((nx, ny))
            robot.x, robot.y = nx, ny
            robot.moves += 1
            if cells[ny][nx] == "*":
                cells[ny][nx] = "."
                robot.coins += 1


def main():
    args = sys.argv[1:]
    if len(args) != 1 or not TICKS_RE.fullmatch(args[0]):
        print("usage: robots TICKS", file=sys.stderr)
        return 2
    ticks = int(args[0])

    text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    lines = [line[:-1] if line.endswith("\r") else line for line in lines]

    try:
        cells, robots = parse_world(lines)
    except InvalidInput as e:
        print("robots: " + str(e), file=sys.stderr)
        return 1

    simulate(cells, robots, ticks)

    out = []
    final = [row[:] for row in cells]
    for robot in robots.values():
        final[robot.y][robot.x] = robot.letter
    out.extend("".join(row) for row in final)
    for letter in sorted(robots):
        r = robots[letter]
        out.append("%s %d %d moves=%d bumps=%d coins=%d"
                   % (letter, r.x, r.y, r.moves, r.bumps, r.coins))
    sys.stdout.write("\n".join(out) + "\n")
    return 0


sys.exit(main())
