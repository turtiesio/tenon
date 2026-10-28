import sys
from common import match, fail, lf_lines, money
if sys.argv[1:]: fail(2)
lots={}; gain=0; code=0
for n,s in enumerate(lf_lines(sys.stdin.buffer.read().decode('ascii')),1):
    if not s or s.startswith('#'): continue
    t=s.split(' ')
    trade=match(r'(BUY|SELL) [A-Z]{1,5} [1-9][0-9]{0,5} (0|[1-9][0-9]{0,5})\.[0-9]{2}',s)
    split=match(r'SPLIT [A-Z]{1,5} ([2-9]|10)',s)
    if not (trade or split): print(f'{n}: ERR bad line'); code=1; continue
    op,sym=t[:2]; q=int(t[2]); held=sum(a for a,c in lots.get(sym,[]))
    if op=='BUY': lots.setdefault(sym,[]).append([q,q*int(t[3].replace('.',''))])
    elif op=='SPLIT':
        if not held: print(f'{n}: ERR not held {sym}'); code=1
        else:
            for lot in lots[sym]: lot[0]*=q
            print(f'{n}: SPLIT {sym} {q} held={held*q}')
    elif q>held: print(f'{n}: ERR insufficient {sym} held={held}'); code=1
    else:
        need=q; cost=0
        while need:
            qty,c=lots[sym][0]; j=min(need,qty)
            p=c if j==qty else (2*c*j+qty)//(2*qty)
            cost+=p; need-=j
            if j==qty: lots[sym].pop(0)
            else: lots[sym][0]=[qty-j,c-p]
        proceeds=q*int(t[3].replace('.','')); g=proceeds-cost; gain+=g
        print(f'{n}: SELL {sym} {q} proceeds={money(proceeds)} cost={money(cost)} gain={money(g)}')
for sym in sorted(lots):
    if lots[sym]: print(f'HOLD {sym} {sum(q for q,c in lots[sym])} cost={money(sum(c for q,c in lots[sym]))} lots={len(lots[sym])}')
print(f'TOTAL gain={money(gain)}'); sys.exit(code)
