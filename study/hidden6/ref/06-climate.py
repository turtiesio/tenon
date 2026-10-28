from datetime import date
import sys
from common import fail, match, split
if sys.argv[1:] not in ([],['-y']): fail(2)
used={}; skipped=replaced=0
for line in split(sys.stdin.buffer.read().decode('utf-8')):
    if not line: continue
    f=line.split(';')
    valid=len(f)==3
    if valid:
        station,day,temp=f
        valid=1<=len(station)<=40 and not station.startswith(' ') and not station.endswith(' ') and match(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',day) and match(r'-?[0-9]{1,2}\.[0-9]',temp)
    if valid:
        try: date(*map(int,day.split('-')))
        except ValueError: valid=False
    if not valid: skipped+=1; continue
    v=int(temp.replace('.',''))
    key=(station,day)
    if key in used: replaced+=1
    used[key]=v
groups={}
for (station,day),v in used.items(): groups.setdefault((station,day[:4 if sys.argv[1:] else 7]),[]).append(v)
def fmt(v): return ('-' if v<0 else '')+str(abs(v)//10)+'.'+str(abs(v)%10)
for (station,period),values in sorted(groups.items(),key=lambda pair:(pair[0][0].encode('utf-8'),pair[0][1])):
    n=len(values); total=sum(values); mean=(2*abs(total)+n)//(2*n)*(1 if total>=0 else -1)
    print(f'{station} {period} days={n} min={fmt(min(values))} max={fmt(max(values))} mean={fmt(mean)}')
print(f'readings={len(used)} skipped={skipped} replaced={replaced}')
