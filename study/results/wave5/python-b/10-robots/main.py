import re
import sys

DIRECTIONS = {'N': (0, -1), 'E': (1, 0), 'S': (0, 1), 'W': (-1, 0)}


def simulate(data, ticks):
    lines = data.split('\n') if data else []
    if data.endswith('\n'):
        lines.pop()
    lines = [line.removesuffix('\r') for line in lines]
    separator = lines.index('') if '' in lines else len(lines)
    rows = lines[:separator]
    if not rows or not 1 <= len(rows) <= 50 or not 1 <= len(rows[0]) <= 50:
        raise ValueError('invalid grid size')
    width, height = len(rows[0]), len(rows)
    grid = [list(row) for row in rows]
    robots = {}
    for y, row in enumerate(grid):
        if len(row) != width:
            raise ValueError('inconsistent row width')
        for x, char in enumerate(row):
            if 'A' <= char <= 'Z':
                if char in robots:
                    raise ValueError('duplicate robot')
                robots[char] = {'x': x, 'y': y, 'moves': 0, 'bumps': 0, 'coins': 0, 'program': ''}
                row[x] = '.'
            elif char not in '.#*':
                raise ValueError('unknown grid character')
    programmed = set()
    for line in lines[separator + 1:]:
        if not re.fullmatch(r'[A-Z]:[NESW.]{0,100}', line):
            raise ValueError('invalid program')
        letter = line[0]
        if letter not in robots or letter in programmed:
            raise ValueError('unknown or repeated robot program')
        programmed.add(letter)
        robots[letter]['program'] = line[2:]
    occupied = {(robot['x'], robot['y']) for robot in robots.values()}
    for tick in range(ticks):
        for letter in sorted(robots):
            robot = robots[letter]
            program = robot['program']
            move = program[tick % len(program)] if program else '.'
            if move == '.':
                continue
            dx, dy = DIRECTIONS[move]
            x, y = robot['x'] + dx, robot['y'] + dy
            if not (0 <= x < width and 0 <= y < height) or grid[y][x] == '#' or (x, y) in occupied:
                robot['bumps'] += 1
                continue
            occupied.remove((robot['x'], robot['y']))
            occupied.add((x, y))
            robot['x'], robot['y'] = x, y
            robot['moves'] += 1
            if grid[y][x] == '*':
                robot['coins'] += 1
                grid[y][x] = '.'
    for letter, robot in robots.items():
        grid[robot['y']][robot['x']] = letter
    output = [''.join(row) for row in grid]
    for letter in sorted(robots):
        robot = robots[letter]
        output.append(f"{letter} {robot['x']} {robot['y']} moves={robot['moves']} bumps={robot['bumps']} coins={robot['coins']}")
    return '\n'.join(output) + '\n'


if __name__ == '__main__':
    if len(sys.argv) != 2 or not re.fullmatch(r'[0-9]{1,5}', sys.argv[1]):
        print('expected tick count', file=sys.stderr)
        sys.exit(2)
    try:
        output = simulate(sys.stdin.buffer.read().decode('utf-8'), int(sys.argv[1]))
    except ValueError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
    sys.stdout.write(output)
