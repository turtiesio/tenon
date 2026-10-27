"""Private standings reference (stdlib only)."""
import re
import sys

def main():
    args = sys.argv[1:]; points = [3,1,0]
    if args:
        if len(args)!=2 or args[0]!='-p' or not re.fullmatch(r'[0-9]{1,2},[0-9]{1,2},[0-9]{1,2}',args[1]): return 2
        points = list(map(int,args[1].split(',')))
    teams = {}
    for line_no, raw in enumerate(sys.stdin.buffer.read().split(b'\n'),1):
        if raw.endswith(b'\r'): raw = raw[:-1]
        s = raw.decode('ascii')
        if not s.strip(' ') or s.startswith('#'): continue
        tokens = s.split(' ')
        scores = [i for i,t in enumerate(tokens) if re.fullmatch('[0-9]{1,2}-[0-9]{1,2}',t)]
        if len(scores)!=1:
            print('line',line_no,file=sys.stderr); return 1
        i = scores[0]
        if i==0 or i==len(tokens)-1 or any(not re.fullmatch("[A-Za-z0-9.&']+",t) for j,t in enumerate(tokens) if j!=i):
            print('line',line_no,file=sys.stderr); return 1
        home, away = ' '.join(tokens[:i]),' '.join(tokens[i+1:])
        if home==away: print('line',line_no,file=sys.stderr); return 1
        hg,ag = map(int,tokens[i].split('-'))
        for name,gf,ga in ((home,hg,ag),(away,ag,hg)):
            if name not in teams: teams[name] = [0,0,0,0,0,0,0,'']
            t = teams[name]; t[0] += 1; t[4] += gf; t[5] += ga
            result = 0 if gf>ga else 1 if gf==ga else 2
            t[1+result] += 1; t[6] += points[result]; t[7] = (t[7]+'WDL'[result])[-5:]
    if not teams: return 0
    def key(name):
        t = teams[name]; return (-t[6],-(t[4]-t[5]),-t[4],-t[1],name)
    width = max(map(len,teams)); previous = None; position = 0
    for i,name in enumerate(sorted(teams,key=key),1):
        rank = key(name)[:4]
        if rank != previous: position = i
        previous = rank
        p,w,d,l,gf,ga,pts,form = teams[name]
        gd = gf-ga; signed = str(gd) if gd<=0 else '+'+str(gd)
        print(f'{position:2}. {name:<{width}}{p:3}{w:3}{d:3}{l:3}{str(gf)+":"+str(ga):>7}{signed:>4}{pts:4} {form}')
    return 0

if __name__ == '__main__':
    status = main()
    if status==2: print('standings: usage',file=sys.stderr)
    sys.exit(status)
