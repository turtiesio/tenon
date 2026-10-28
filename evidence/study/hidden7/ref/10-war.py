from collections import deque
import sys
from common import match, fail, lf_lines
args=sys.argv[1:]; limit=1000; quiet=False; i=0
while i<len(args):
    op=args[i]; i+=1
    if op=='-q': quiet=True
    elif op=='-n':
        if i==len(args) or not match('[1-9][0-9]{0,5}',args[i]): fail(2)
        limit=int(args[i]); i+=1
    else: fail(2)
rows=lf_lines(sys.stdin.buffer.read().decode('ascii'))
if len(rows)!=2 or any(not match('[2-9TJQKA]{1,52}',s) for s in rows): fail(1)
a,b=map(deque,rows); rank='23456789TJQKA'
for k in range(1,limit+1):
    pile=[]; upa=[]; upb=[]; incomplete=False
    x=a.popleft(); y=b.popleft(); pile.extend((x,y)); upa.append(x); upb.append(y)
    while x==y:
        if min(len(a),len(b))<4: incomplete=True; break
        for _ in range(4): x=a.popleft(); pile.append(x)
        for _ in range(4): y=b.popleft(); pile.append(y)
        upa.append(x); upb.append(y)
    if incomplete:
        winner='-'; result=('A wins' if len(a)>len(b) else 'B wins' if len(b)>len(a) else 'draw')+f' in round {k}'
    else:
        winner='A' if rank.index(x)>rank.index(y) else 'B'
        (a if winner=='A' else b).extend(pile)
        result=(winner+f' wins in round {k}') if not a or not b else None
    if not quiet: print(f'{k} {"/".join(upa)} {"/".join(upb)} {winner} {len(a)} {len(b)}')
    if result: print(result); break
else: print(f'stopped at round {limit}')
