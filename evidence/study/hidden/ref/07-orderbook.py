"""Private spec-only reference."""
import re
import sys

def main():
    if len(sys.argv)>1: return 2
    seen=set(); orders={}; sequence=0
    ident=r'[A-Za-z0-9_-]{1,16}'; number=r'[1-9][0-9]{0,8}'
    for raw in sys.stdin.buffer:
        s=raw.decode().removesuffix('\n').removesuffix('\r')
        m=re.fullmatch('(BUY|SELL) ('+ident+') ('+number+') ('+number+')',s)
        cancel=re.fullmatch('CANCEL ('+ident+')',s)
        if m:
            side,oid,q,p=m.groups(); qty=int(q); price=int(p)
            if oid in seen: answer='ERR duplicate id'
            else:
                seen.add(oid); sequence+=1; remaining=qty; trades=[]
                candidates=[(k,v) for k,v in orders.items() if v[0]!=side and (v[2]<=price if side=='BUY' else v[2]>=price)]
                candidates.sort(key=lambda kv: ((kv[1][2] if side=='BUY' else -kv[1][2]),kv[1][3]))
                for maker,v in candidates:
                    if not remaining: break
                    amount=min(remaining,v[1]); remaining-=amount; v[1]-=amount
                    trades.append('%s:%d@%d'%(maker,amount,v[2]))
                    if not v[1]: del orders[maker]
                if remaining: orders[oid]=[side,remaining,price,sequence]
                answer='OK %s filled=%d resting=%d trades=%s'%(oid,qty-remaining,remaining,','.join(trades) or '-')
        elif cancel:
            oid=cancel[1]
            if oid in orders: answer='CANCELED %s %d'%(oid,orders.pop(oid)[1])
            else: answer='ERR unknown order'
        elif s=='BOOK':
            levels=[]
            for side in ('BUY','SELL'):
                totals={}
                for v in orders.values():
                    if v[0]==side: totals[v[2]]=totals.get(v[2],0)+v[1]
                levels.append(','.join('%d:%d'%(p,totals[p]) for p in sorted(totals,reverse=side=='BUY')) or '-')
            answer='BOOK bids=%s asks=%s'%tuple(levels)
        else: answer='ERR bad command'
        print(answer,flush=True)
    return 0
sys.exit(main())
