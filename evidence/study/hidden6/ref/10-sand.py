import sys
from common import fail, match, split
if len(sys.argv)!=2 or not match(r'[0-9]{1,4}',sys.argv[1]): fail(2)
grid=[list(row) for row in split(sys.stdin.buffer.read().decode('utf-8'))]
h=len(grid); w=len(grid[0]) if h else 0
if not 1<=h<=30 or not 1<=w<=30 or any(len(row)!=w or any(c not in '.#oS' for c in row) for row in grid): fail()
lost=ran=0; stable=False
for tick in range(int(sys.argv[1])):
    changed=False; ran+=1
    for y in range(h-1,-1,-1):
        for x in range(w):
            if grid[y][x]!='o': continue
            if y==h-1: grid[y][x]='.'; lost+=1; changed=True
            else:
                for target in (x,x-1,x+1):
                    if 0<=target<w and grid[y+1][target]=='.':
                        grid[y][x]='.'; grid[y+1][target]='o'; changed=True; break
    for y in range(h-1):
        for x in range(w):
            if grid[y][x]=='S' and grid[y+1][x]=='.': grid[y+1][x]='o'; changed=True
    if not changed: stable=True; break
for row in grid: print(''.join(row))
print(f'ticks={ran} grains={sum(row.count("o") for row in grid)} lost={lost} stable={"yes" if stable else "no"}')
