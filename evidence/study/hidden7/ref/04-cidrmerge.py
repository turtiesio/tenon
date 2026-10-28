import sys
from common import match, fail, lf_lines
if sys.argv[1:] not in ([],['-r']): fail(2)
ranges=[]; code=0
for s in lf_lines(sys.stdin.buffer.read().decode('ascii')):
    if not s or s.startswith('#'): continue
    try:
        if not match(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(/(0|[1-9][0-9]*))?',s): raise ValueError()
        addr,*prefix=s.split('/'); octets=list(map(int,addr.split('.'))); p=int(prefix[0]) if prefix else 32
        if max(octets)>255 or p>32: raise ValueError()
        n=0
        for d in octets: n=n*256+d
        size=1<<(32-p)
        if n%size: raise ValueError()
        ranges.append((n,n+size-1))
    except ValueError: code=1; print('bad line',file=sys.stderr)
merged=[]
for a,b in sorted(ranges):
    if merged and a<=merged[-1][1]+1: merged[-1][1]=max(b,merged[-1][1])
    else: merged.append([a,b])
def dotted(n): return '.'.join(str((n>>k)&255) for k in (24,16,8,0))
for a,b in merged:
    if sys.argv[1:]: print(f'{dotted(a)}-{dotted(b)} {b-a+1}')
    else:
        while a<=b:
            k=min((a&-a).bit_length()-1 if a else 32,(b-a+1).bit_length()-1)
            print(f'{dotted(a)}/{32-k}'); a+=1<<k
sys.exit(code)
