"""Private spec-only reference."""
import re
import sys

def main(a):
    files=[]; sort='count'; minimum=1
    for x in a:
        if x.startswith('--sort='):
            sort=x.split('=',1)[1]
            if sort not in ('count','p99','name'): return 2
        elif x.startswith('--min-count='):
            v=x.split('=',1)[1]
            if not re.fullmatch('[0-9]+',v) or not 1<=int(v)<=1000000000: return 2
            minimum=int(v)
        elif x.startswith('-'): return 2
        else: files.append(x)
    if len(files)>1: return 2
    try: data=open(files[0],encoding='utf-8',newline='').read() if files else sys.stdin.read()
    except OSError: return 1
    groups={}; total=bad=0
    for line in data.split('\n'):
        if line.endswith('\r'): line=line[:-1]
        if not line.strip(' \t'): continue
        tokens=re.split('[ \t]+',line.strip(' \t'))
        if len(tokens)!=5:
            bad+=1; continue
        stamp,method,path,status,ms=tokens
        if not (re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z',stamp) and re.fullmatch('[A-Z]{1,10}',method) and re.fullmatch(r'/\S*',path) and re.fullmatch('[1-5][0-9]{2}',status) and re.fullmatch('[0-9]{1,9}',ms)):
            bad+=1; continue
        path='/'.join(':id' if re.fullmatch('[0-9]+',s) else s for s in path.split('?',1)[0].split('/'))
        name=method+' '+path
        g=groups.setdefault(name,[[],0]); g[0].append(int(ms)); g[1]+=int(status)>=500; total+=1
    rows=[]
    for name,(values,errors) in groups.items():
        n=len(values)
        if n<minimum: continue
        values.sort(); p=[values[(p*n+99)//100-1] for p in (50,90,99)]
        pct=(2000*errors+n)//(2*n)
        line='%s count=%d errors=%d err_pct=%d.%d p50=%d p90=%d p99=%d max=%d'%(name,n,errors,pct//10,pct%10,*p,values[-1])
        rows.append((name,n,p[2],line))
    rows.sort(key=lambda r: (r[0].encode(),) if sort=='name' else (-(r[1] if sort=='count' else r[2]),r[0].encode()))
    for r in rows: print(r[3])
    print('total=%d malformed=%d'%(total,bad))
    return 0
sys.exit(main(sys.argv[1:]))
