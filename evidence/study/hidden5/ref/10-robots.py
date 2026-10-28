"""Private robots reference, implemented from tasks5/10-robots.md."""
import re
import sys
from common import fail, match, stdin_lines
if len(sys.argv) != 2 or not match(r'[0-9]{1,5}',sys.argv[1]): fail(2)
ticks = int(sys.argv[1])
world = stdin_lines()
try: split = world.index('')
except ValueError: split = len(world)
rows,program_lines = world[:split],world[split+1:]
if not rows or not 1 <= len(rows) <= 50 or not 1 <= len(rows[0]) <= 50: fail(1)
w,h = len(rows[0]),len(rows)
if any(len(row) != w or not match(r'[.#*A-Z]+',row) for row in rows): fail(1)
positions,programs,stats = {},{},{}
grid = [list(row) for row in rows]
for y,row in enumerate(rows):
    for x,c in enumerate(row):
        if 'A' <= c <= 'Z':
            if c in positions: fail(1)
            positions[c] = (x,y)
            stats[c] = [0,0,0]
            grid[y][x] = '.'
for line in program_lines:
    if not match(r'[A-Z]:[NESW.]{0,100}',line): fail(1)
    robot,moves = line.split(':')
    if robot not in positions or robot in programs: fail(1)
    programs[robot] = moves
deltas = {'N':(0,-1),'S':(0,1),'E':(1,0),'W':(-1,0)}
occupied = set(positions.values())
for t in range(ticks):
    for c in sorted(positions):
        program = programs.get(c,'')
        instruction = program[t%len(program)] if program else '.'
        if instruction == '.': continue
        x,y = positions[c]
        dx,dy = deltas[instruction]
        target = (x+dx,y+dy)
        xx,yy = target
        if not (0 <= xx < w and 0 <= yy < h) or grid[yy][xx] == '#' or target in occupied:
            stats[c][1] += 1
        else:
            occupied.remove((x,y))
            occupied.add(target)
            positions[c] = target
            stats[c][0] += 1
            if grid[yy][xx] == '*':
                stats[c][2] += 1
                grid[yy][xx] = '.'
for c,(x,y) in positions.items(): grid[y][x] = c
for row in grid: print(''.join(row))
for c in sorted(positions):
    x,y = positions[c]
    m,b,coins = stats[c]
    print(f'{c} {x} {y} moves={m} bumps={b} coins={coins}')
