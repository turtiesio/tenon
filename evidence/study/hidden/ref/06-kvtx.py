"""Private spec-only reference."""
import re
import sys

def integer(s):
    if s=='-0' or not re.fullmatch(r'-?(0|[1-9][0-9]*)',s) or abs(int(s))>10**15: raise ValueError()
    return int(s)

def main():
    if len(sys.argv)>1: return 2
    views=[{}]
    for raw in sys.stdin.buffer:
        s=raw.decode('utf-8').removesuffix('\n').removesuffix('\r')
        t=s.strip(' ').split(' '); t=[x for x in t if x]
        valid=all(re.fullmatch('[!-~]+',x) for x in t)
        op=t[0] if t else ''; args=t[1:]; d=views[-1]; answer='ERR bad command'
        if valid and op=='SET' and len(args)==2: d[args[0]]=args[1]; answer='OK'
        elif valid and op=='GET' and len(args)==1: answer=d.get(args[0],'NULL')
        elif valid and op=='DEL' and len(args)==1:
            answer=str(int(args[0] in d)); d.pop(args[0],None)
        elif valid and op=='INCR' and len(args) in (1,2):
            try:
                v=integer(d.get(args[0],'0'))+integer(args[1] if len(args)==2 else '1')
                if abs(v)>10**15: answer='ERR overflow'
                else: answer=str(v); d[args[0]]=answer
            except ValueError: answer='ERR not an integer'
        elif valid and op=='COUNT' and len(args)==1: answer=str(sum(v==args[0] for v in d.values()))
        elif valid and op=='KEYS' and not args: answer=' '.join(sorted(d)) or '(empty)'
        elif valid and op=='BEGIN' and not args: views.append(d.copy()); answer='OK'
        elif valid and op in ('COMMIT','ROLLBACK') and not args:
            if len(views)==1: answer='ERR no transaction'
            else:
                d=views.pop()
                if op=='COMMIT': views[-1]=d
                answer='OK'
        print(answer,flush=True)
    return 0
sys.exit(main())
