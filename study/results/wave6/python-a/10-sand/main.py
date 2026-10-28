import re
import sys

MAX_TICKS = 9999
MAX_SIZE = 30
CELLS = set(".#oS")


def parse_grid(text):
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    rows = [line[:-1] if line.endswith("\r") else line for line in lines]
    if not 1 <= len(rows) <= MAX_SIZE:
        return None
    width = len(rows[0])
    if not 1 <= width <= MAX_SIZE:
        return None
    for row in rows:
        if len(row) != width or not set(row) <= CELLS:
            return None
    return [list(row) for row in rows]


def tick(grid):
    """Run one tick; return (changed, number of grains lost)."""
    height, width = len(grid), len(grid[0])
    changed = False
    lost = 0
    for y in range(height - 1, -1, -1):
        for x in range(width):
            if grid[y][x] != "o":
                continue
            if y == height - 1:
                grid[y][x] = "."
                lost += 1
                changed = True
                continue
            for nx in (x, x - 1, x + 1):
                if 0 <= nx < width and grid[y + 1][nx] == ".":
                    grid[y][x] = "."
                    grid[y + 1][nx] = "o"
                    changed = True
                    break
    for y in range(height - 1):
        for x in range(width):
            if grid[y][x] == "S" and grid[y + 1][x] == ".":
                grid[y + 1][x] = "o"
                changed = True
    return changed, lost


def main(argv):
    if len(argv) != 1 or not re.fullmatch(r"[0-9]{1,4}", argv[0]) or int(argv[0]) > MAX_TICKS:
        print("usage: sand TICKS (0-9999)", file=sys.stderr)
        return 2
    ticks = int(argv[0])

    try:
        text = sys.stdin.buffer.read().decode("utf-8")
    except UnicodeDecodeError:
        text = None
    grid = parse_grid(text) if text is not None else None
    if grid is None:
        print("sand: invalid grid", file=sys.stderr)
        return 1

    ran = 0
    lost = 0
    stable = False
    while ran < ticks:
        changed, fell = tick(grid)
        ran += 1
        lost += fell
        if not changed:
            stable = True
            break

    grains = sum(row.count("o") for row in grid)
    out = ["".join(row) + "\n" for row in grid]
    out.append(f"ticks={ran} grains={grains} lost={lost} stable={'yes' if stable else 'no'}\n")
    sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
