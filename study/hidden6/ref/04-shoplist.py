import sys
from common import fail, match, read, split
if len(sys.argv)!=3: fail(2)
name = r'[a-z][a-z0-9_-]{0,29}'
recipes, current = {}, None
for line in split(read(sys.argv[1])):
    if not line.strip(' ') or line.startswith('#'): continue
    if match(r'\[('+name+r')\] [1-9][0-9]{0,2}',line):
        nm, serves = line[1:].split('] ')
        if nm in recipes: fail()
        current = (int(serves),{})
        recipes[nm] = current
    else:
        if current is None or not match(name+r' [1-9][0-9]{0,5}( (g|kg|ml|l))?',line): fail()
        fields=line.split(' '); nm=fields[0]; q=int(fields[1]); unit=fields[2] if len(fields)==3 else ''
        if nm in current[1]: fail()
        kind = 'mass' if unit in ('g','kg') else 'volume' if unit in ('ml','l') else 'count'
        current[1][nm] = (q*(1000 if unit in ('kg','l') else 1),kind)
totals = {}
for line in split(read(sys.argv[2])):
    if not line.strip(' ') or line.startswith('#'): continue
    if not match(name+r' [1-9][0-9]{0,2}',line): fail()
    nm, count=line.split(' ')
    if nm not in recipes: fail()
    serves, ingredients=recipes[nm]
    for ing,(qty,kind) in ingredients.items():
        old,prev=totals.get(ing,(0,kind))
        if prev!=kind: fail()
        totals[ing]=(old+(qty*int(count)+serves-1)//serves,kind)
for nm,(qty,kind) in sorted(totals.items()):
    if kind=='count': text=str(qty)
    elif qty<1000: text=str(qty)+(' g' if kind=='mass' else ' ml')
    else:
        text=str(qty//1000)
        if qty%1000: text+='.'+str(qty%1000).zfill(3).rstrip('0')
        text+= ' kg' if kind=='mass' else ' l'
    print(nm+' '+text)
