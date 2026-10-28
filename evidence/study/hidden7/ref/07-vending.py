import sys
from common import match, fail, incoming, say
if sys.argv[1:]: fail(2)
denoms=(5,10,20,50,100,200); tubes=dict.fromkeys(denoms,0); escrow=[]; slots={}
patterns=[r'LOAD [A-F][1-9] [a-z]{1,12} [1-9][0-9]{0,3} (0|[1-9][0-9]?)',r'FILL (5|10|20|50|100|200) [1-9][0-9]{0,2}',r'INSERT [1-9][0-9]{0,5}',r'(SELECT|STOCK) [A-F][1-9]',r'REFUND|COINS']
def coins(counts): return ' '.join(f'{d}x{counts[d]}' for d in reversed(denoms) if counts.get(d,0)) or '-'
def command(s):
    if not any(match(p,s) for p in patterns): return 'ERR bad command'
    t=s.split(' '); op=t[0]
    if op=='LOAD':
        if int(t[3])%5: return 'ERR bad command'
        slots[t[1]]=[t[2],int(t[3]),int(t[4])]; return 'OK'
    if op=='FILL': tubes[int(t[1])]+=int(t[2]); return 'OK'
    if op=='INSERT':
        d=int(t[1])
        if d not in denoms: return f'REJECT {d}'
        escrow.append(d); return f'CREDIT {sum(escrow)}'
    if op=='COINS': return ' '.join(f'{d}x{tubes[d]}' for d in denoms)
    if op=='REFUND':
        credit=sum(escrow); listing=coins({d:escrow.count(d) for d in denoms}); escrow.clear()
        return f'REFUND {credit} {listing}'
    if t[1] not in slots: return 'ERR no such slot'
    name,price,count=slots[t[1]]
    if op=='STOCK': return f'{t[1]} {name} {price} {count}'
    if not count: return 'ERR sold out'
    credit=sum(escrow)
    if credit<price: return f'ERR need {price-credit}'
    trial={d:tubes[d]+escrow.count(d) for d in denoms}; paid={}; owed=credit-price
    for d in reversed(denoms):
        paid[d]=min(trial[d],owed//d); trial[d]-=paid[d]; owed-=paid[d]*d
    if owed: return 'ERR no change'
    tubes.update(trial); escrow.clear(); slots[t[1]][2]-=1
    return f'VEND {name} {credit-price} {coins(paid)}'
for s in incoming(): say(command(s))
