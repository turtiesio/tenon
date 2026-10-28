import re
import sys
from common import fail, emit
if len(sys.argv)!=1: fail(2)
name=r'[a-z0-9]{1,12}'
forms=[r'LOCK ('+name+r') ('+name+r') (S|X)',r'UNLOCK ('+name+r') ('+name+r')',r'DROP ('+name+r')',r'STATUS ('+name+r')',r'HELD ('+name+r')']
resources={}
def state(r): return resources.setdefault(r,({},[]))
def compatible(h,m): return not h or m=='S' and all(v=='S' for v in h.values())
def pump(r):
    h,q=state(r); grants=[]
    while q and compatible(h,q[0][1]):
        c,m=q.pop(0); h[c]=m; grants.append(f'{c}:{r}:{m}')
    return grants
def suffix(grants): return ''.join(' '+g for g in grants)
for raw in sys.stdin.buffer:
    line=raw.decode('ascii').removesuffix('\n').removesuffix('\r')
    m=next((m for p in forms if (m:=re.fullmatch(p,line))),None)
    response='ERR bad command'
    if m:
        a=m.groups(); cmd=line.split(' ')[0]
        if cmd=='LOCK':
            c,r,mode=a; h,q=state(r)
            if c in h: response='ERR already held'
            elif any(x==c for x,_ in q): response='ERR already waiting'
            elif not q and compatible(h,mode): h[c]=mode; response='GRANTED'
            else: q.append((c,mode)); response='WAITING'
        elif cmd=='UNLOCK':
            c,r=a; h,q=state(r)
            if c not in h: response='ERR not held'
            else: del h[c]; response='OK'+suffix(pump(r))
        elif cmd=='DROP':
            c=a[0]; released=cancelled=0; touched=[]
            for r,(h,q) in resources.items():
                count=len(q); q[:]=[(x,v) for x,v in q if x!=c]; count-=len(q)
                held=c in h
                if held: del h[c]
                released+=int(held); cancelled+=count
                if held or count: touched.append(r)
            grants=[]
            for r in sorted(touched): grants.extend(pump(r))
            response=f'OK released={released} cancelled={cancelled}'+suffix(grants)
        elif cmd=='STATUS':
            r=a[0]; h,q=state(r)
            holders=','.join(c+':'+v for c,v in sorted(h.items())) or '-'
            queue=','.join(c+':'+v for c,v in q) or '-'
            response=f'{r} holders={holders} queue={queue}'
        else:
            c=a[0]; response=','.join(r+':'+h[c] for r,(h,q) in sorted(resources.items()) if c in h) or '-'
    emit(response+'\n')
