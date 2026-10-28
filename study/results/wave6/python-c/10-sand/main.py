"""sand: deterministic falling-sand simulation."""
import re
import sys

TICKS_RE = re.compile(r"[0-9]{1,4}")
EMPTY, ROCK, GRAIN, SOURCE = ".", "#", "o", "S"
CELLS = {EMPTY, ROCK, GRAIN, SOURCE}
MAX_SIZE = 30


class GridError(Exception):
    pass


def parse_grid(data: bytes) -> list[list[str]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise GridError("input is not UTF-8")
    lines = text.split("\n")
    if text.endswith("\n") or text == "":
        lines.pop()
    rows = [line[:-1] if line.endswith("\r") else line for line in lines]
    if not 1 <= len(rows) <= MAX_SIZE:
        raise GridError(f"need 1 to {MAX_SIZE} rows, got {len(rows)}")
    width = len(rows[0])
    if not 1 <= width <= MAX_SIZE:
        raise GridError(f"need 1 to {MAX_SIZE} columns, got {width}")
    for y, row in enumerate(rows):
        if len(row) != width:
            raise GridError(f"row {y + 1} has length {len(row)}, expected {width}")
        if bad := set(row) - CELLS:
            raise GridError(f"row {y + 1} has an invalid character {min(bad)!r}")
    return [list(row) for row in rows]


class Sand:
    def __init__(self, grid: list[list[str]]) -> None:
        self.grid = grid
        self.height = len(grid)
        self.width = len(grid[0])
        self.lost = 0

    def is_empty(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height and self.grid[y][x] == EMPTY

    def tick(self) -> bool:
        """Run one tick; return True if anything changed."""
        grid = self.grid
        changed = False
        bottom = self.height - 1
        for y in range(bottom, -1, -1):
            for x in range(self.width):
                if grid[y][x] != GRAIN:
                    continue
                if y == bottom:
                    grid[y][x] = EMPTY
                    self.lost += 1
                    changed = True
                    continue
                for tx in (x, x - 1, x + 1):
                    if self.is_empty(tx, y + 1):
                        grid[y][x] = EMPTY
                        grid[y + 1][tx] = GRAIN
                        changed = True
                        break
        for y in range(bottom):
            for x in range(self.width):
                if grid[y][x] == SOURCE and grid[y + 1][x] == EMPTY:
                    grid[y + 1][x] = GRAIN
                    changed = True
        return changed

    def grains(self) -> int:
        return sum(row.count(GRAIN) for row in self.grid)

    def render(self) -> str:
        return "".join("".join(row) + "\n" for row in self.grid)


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not TICKS_RE.fullmatch(argv[0]):
        print("usage: sand TICKS (0-9999)", file=sys.stderr)
        return 2
    max_ticks = int(argv[0])
    try:
        sand = Sand(parse_grid(sys.stdin.buffer.read()))
    except GridError as e:
        print(f"sand: invalid grid: {e}", file=sys.stderr)
        return 1

    ticks = 0
    stable = False
    while ticks < max_ticks:
        ticks += 1
        if not sand.tick():
            stable = True
            break
    sys.stdout.write(sand.render())
    print(f"ticks={ticks} grains={sand.grains()} lost={sand.lost} "
          f"stable={'yes' if stable else 'no'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
