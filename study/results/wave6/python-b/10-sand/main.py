import re
import sys


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r'[0-9]{1,4}', sys.argv[1]):
        print('expected TICKS (0-9999)', file=sys.stderr)
        return 2
    data = sys.stdin.buffer.read().decode('utf-8')
    rows = data.split('\n') if data else []
    if rows and data.endswith('\n'):
        rows.pop()
    rows = [row[:-1] if row.endswith('\r') else row for row in rows]
    if (not 1 <= len(rows) <= 30 or not 1 <= len(rows[0]) <= 30
            or any(len(row) != len(rows[0]) or any(cell not in '.#oS' for cell in row) for row in rows)):
        print('invalid grid', file=sys.stderr)
        return 1
    grid = [list(row) for row in rows]
    height, width = len(grid), len(grid[0])
    sources = [(x, y) for y in range(height - 1) for x in range(width) if grid[y][x] == 'S']
    lost = ticks = 0
    stable = False
    for ticks in range(1, int(sys.argv[1]) + 1):
        changed = False
        for y in range(height - 1, -1, -1):
            for x in range(width):
                if grid[y][x] != 'o':
                    continue
                if y == height - 1:
                    grid[y][x] = '.'
                    lost += 1
                    changed = True
                else:
                    for target in (x, x - 1, x + 1):
                        if 0 <= target < width and grid[y + 1][target] == '.':
                            grid[y][x] = '.'
                            grid[y + 1][target] = 'o'
                            changed = True
                            break
        for x, y in sources:
            if grid[y + 1][x] == '.':
                grid[y + 1][x] = 'o'
                changed = True
        if not changed:
            stable = True
            break
    for row in grid:
        print(''.join(row))
    grains = sum(row.count('o') for row in grid)
    print(f'ticks={ticks} grains={grains} lost={lost} stable={"yes" if stable else "no"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
