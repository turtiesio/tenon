import sys
from common import fail, match, split
if len(sys.argv)>2: fail(2)
rows=split(sys.stdin.buffer.read().decode('utf-8'))
if not rows or rows[0]!='id,name,manager,salary': fail()
people={}
for line in rows[1:]:
    if line=='': continue
    f=line.split(',')
    if len(f)!=4: fail()
    ident,name,manager,salary=f
    if not match(r'[a-z0-9]{1,8}',ident) or ident in people or not name or name.startswith(' ') or name.endswith(' ') or (manager and not match(r'[a-z0-9]{1,8}',manager)) or not match(r'[0-9]{1,9}',salary): fail()
    people[ident]=(name,manager,int(salary))
children={k:[] for k in people}; roots=[]
for ident,(_,manager,_) in people.items():
    if manager:
        if manager not in people: fail()
        children[manager].append(ident)
    else: roots.append(ident)
key=lambda ident:(people[ident][0].encode('utf-8'),ident)
roots.sort(key=key)
for group in children.values(): group.sort(key=key)
# Iterative postorder avoids the host Python recursion limit at depth 500.
stats={}; stack=[(r,False) for r in roots]
while stack:
    ident,done=stack.pop()
    if done:
        stats[ident]=(sum(stats[c][0]+1 for c in children[ident]),people[ident][2]+sum(stats[c][1] for c in children[ident]))
    else:
        stack.append((ident,True)); stack.extend((c,False) for c in children[ident])
if len(stats)!=len(people): fail()
if len(sys.argv)==2:
    if sys.argv[1] not in people: fail()
    roots=[sys.argv[1]]
stack=[(r,0) for r in reversed(roots)]
while stack:
    ident,depth=stack.pop(); reports,cost=stats[ident]
    print('  '*depth+f'{people[ident][0]} [{ident}] reports={reports} cost={cost:,}')
    stack.extend((c,depth+1) for c in reversed(children[ident]))
