"""Private splitbill reference, implemented from tasks5/04-splitbill.md."""
import re
import sys
from common import fail, match, stdin_lines, money
if len(sys.argv) != 1: fail(2)
balances = {}
name = r'[a-z][a-z0-9_]{0,15}'
for line in stdin_lines():
    t = re.findall(r'[^ \t]+',line)
    if not t or t[0].startswith('#'): continue
    if t[0] == 'expense' and len(t) >= 4:
        payer, amount, *people = t[1:]
        names = [payer]+people
        if len(set(people)) != len(people): fail(1)
    elif t[0] == 'transfer' and len(t) == 4:
        sender, recipient, amount = t[1:]
        names = [sender, recipient]
        if sender == recipient: fail(1)
    else: fail(1)
    if not all(match(name,n) for n in names) or not match(r'[0-9]{1,7}\.[0-9]{2}',amount): fail(1)
    cents = int(amount.replace('.',''))
    if cents == 0: fail(1)
    for n in names: balances.setdefault(n,0)
    if t[0] == 'expense':
        balances[payer] += cents
        q,r = divmod(cents,len(people))
        for i,p in enumerate(people): balances[p] -= q+(i < r)
    else:
        balances[sender] += cents
        balances[recipient] -= cents
out = [f'{n} '+('+' if b>0 else '-' if b<0 else '')+money(b) for n,b in sorted(balances.items())]+['--']
while any(b<0 for b in balances.values()):
    debtor = min(balances,key=lambda n:(balances[n],n))
    creditor = min(balances,key=lambda n:(-balances[n],n))
    payment = min(-balances[debtor],balances[creditor])
    out.append(f'{debtor} pays {creditor} {money(payment)}')
    balances[debtor] += payment
    balances[creditor] -= payment
print('\n'.join(out))
