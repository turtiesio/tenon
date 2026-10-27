"""Private spec-only reference; deterministic discrete event simulation."""
import re
import sys

def main(a):
    files=[]; workers=1; i=0
    while i<len(a):
        x=a[i]
        if x in ('-w','--workers') or x.startswith('--workers='):
            if '=' in x: v=x.split('=',1)[1]
            else:
                i+=1
                if i==len(a): return 2
                v=a[i]
            if not re.fullmatch('[0-9]+',v) or not 1<=int(v)<=1000: return 2
            workers=int(v)
        elif x.startswith('-') and x!='-': return 2
        else: files.append(x)
        i+=1
    if len(files)!=1: return 2
    try: data=sys.stdin.read() if files[0]=='-' else open(files[0],encoding='utf-8',newline='').read()
    except OSError: return 1
    jobs={}; name=r'[A-Za-z0-9_.-]{1,32}'
    for line in data.split('\n'):
        if line.endswith('\r'): line=line[:-1]
        if not line.strip() or line.lstrip().startswith('#'): continue
        t=re.split('[ \t]+',line.strip(' \t'))
        if len(t)!=4: return 1
        n,d,p,deps=t
        if not re.fullmatch(name,n) or n in jobs or not re.fullmatch('[0-9]+',d) or not 1<=int(d)<=1000000 or not re.fullmatch('[0-9]+',p) or not 0<=int(p)<=1000: return 1
        ds=[] if deps=='-' else deps.split(',')
        if any(not re.fullmatch(name,s) for s in ds): return 1
        jobs[n]=(int(d),int(p),set(ds))
    # Validate the entire graph before producing any trace.
    done=set()
    while len(done)<len(jobs):
        ready={n for n,j in jobs.items() if n not in done and j[2]<=done}
        if not ready: return 1
        done.update(ready)
    done=set(); started=set(); active={}; free=set(range(1,workers+1)); time=0
    while len(done)<len(jobs):
        finishing=sorted(n for n,(end,w) in active.items() if end==time)
        for n in finishing:
            end,w=active.pop(n); free.add(w); done.add(n); print(time,'finish',n,'w'+str(w))
        ready=sorted((n for n,j in jobs.items() if n not in started and j[2]<=done),key=lambda n:(-jobs[n][1],n))
        for n in ready:
            if not free: break
            w=min(free); free.remove(w); started.add(n); active[n]=(time+jobs[n][0],w)
            print(time,'start',n,'w'+str(w))
        if active: time=min(end for end,w in active.values())
    print('done',time)
    return 0
sys.exit(main(sys.argv[1:]))
