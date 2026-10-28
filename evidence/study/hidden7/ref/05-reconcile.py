import sys
from datetime import date
from common import match, fail, lf_lines, money
args=sys.argv[1:]; paths=[]; days=3; i=0
while i<len(args):
    arg=args[i]; i+=1
    if arg=='-d':
        if i==len(args) or not match('0|[1-9][0-9]{0,2}',args[i]) or int(args[i])>365: fail(2)
        days=int(args[i]); i+=1
    elif arg.startswith('-'): fail(2)
    else: paths.append(arg)
if len(paths)!=2: fail(2)
def read(path):
    rows=[]
    for n,s in enumerate(lf_lines(open(path,'rb').read().decode('ascii')),1):
        if not s: continue
        if s.count(',')!=2: raise ValueError()
        d,a,t=s.split(',')
        if not match('[0-9]{4}-[0-9]{2}-[0-9]{2}',d) or not match(r'-?(0|[1-9][0-9]{0,8})\.[0-9]{2}',a): raise ValueError()
        dt=date.fromisoformat(d)
        if not 1970<=dt.year<=2099 or not 1<=len(t)<=40 or t[0]==' ' or t[-1]==' ' or any(not 32<=ord(c)<=126 for c in t): raise ValueError()
        amount=int(a.replace('.',''))
        rows.append((n,d,dt.toordinal(),amount,t))
    return rows
try: bank,ledger=map(read,paths)
except (OSError,ValueError,UnicodeError): fail(1)
used=set(); matches=[]; bs=[]
for b in bank:
    candidates=[(abs(b[2]-l[2]),l[0],l) for l in ledger if l[0] not in used and b[3]==l[3] and abs(b[2]-l[2])<=days]
    if candidates:
        dist,ln,l=min(candidates); used.add(ln); matches.append(f'M {b[0]} {ln} {money(b[3])} {dist}')
    else: bs.append(b)
ls=[l for l in ledger if l[0] not in used]
for s in matches: print(s)
for prefix,rows in [('B',bs),('L',ls)]:
    for n,d,_,a,t in rows: print(f'{prefix} {n} {d} {money(a)} {t}')
print(f'matched={len(matches)} bank_only={len(bs)} ledger_only={len(ls)} diff={money(sum(b[3] for b in bs)-sum(l[3] for l in ls))}')
