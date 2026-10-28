"""Private libfines reference, implemented from tasks5/06-libfines.md."""
from pathlib import Path
import sys
from common import fail, match, lines, money
if len(sys.argv) != 4 or not match(r'[0-9]{1,6}',sys.argv[3]): fail(2)
today = int(sys.argv[3])
def records(path):
    try: return [x.split('|') for x in lines(Path(path).read_bytes().decode('utf-8')) if x and not x.startswith('#')]
    except (OSError,UnicodeError): fail(1)
books = {}
bid = r'[A-Za-z0-9-]{1,12}'
num = r'[0-9]{1,6}'
for row in records(sys.argv[1]):
    if len(row) != 4: fail(1)
    b,title,rate,cap = row
    if not match(bid,b) or not title or not match(num,rate) or not match(num,cap) or b in books: fail(1)
    books[b] = (title,int(rate),int(cap))
loans = records(sys.argv[2])
members = {}
skipped = 0
for row in loans:
    if len(row) != 5: fail(1)
    member,b,out,due,returned = row
    if not match(r'[a-z][a-z0-9]{0,11}',member) or not match(bid,b) or not match(num,out) or not match(num,due) or (returned != '-' and not match(num,returned)): fail(1)
    out,due = int(out),int(due)
    returned = today if returned == '-' else int(returned)
    if due < out or (row[4] != '-' and returned < out): fail(1)
    if b not in books:
        skipped += 1
        continue
    title,rate,cap = books[b]
    days = max(0,returned-due)
    fine = min(days*rate,cap)
    data = members.setdefault(member,{'loans':0,'fine':0,'late':[]})
    data['loans'] += 1
    data['fine'] += fine
    if days: data['late'].append((b,title,days,fine))
out = []
for member in sorted(members,key=lambda n:(-members[n]['fine'],n)):
    data = members[member]
    out.append(f"{member} loans={data['loans']} late={len(data['late'])} fine={money(data['fine'])}")
    for b,title,days,fine in data['late']: out.append(f'  {b} {title} days={days} fine={money(fine)}')
out.append(f"total={money(sum(d['fine'] for d in members.values()))} skipped={skipped}")
print('\n'.join(out))
