"""Private colalign reference, implemented from tasks5/03-colalign.md."""
import re
import sys
from common import fail, match, stdin_lines
args = sys.argv[1:]
sep, outsep, right = None, '  ', set()
i = 0
while i < len(args):
    if args[i] not in ('-s','-o','-r') or i+1 == len(args): fail(2)
    a,v = args[i:i+2]
    if a == '-s':
        if len(v) != 1: fail(2)
        sep = v
    elif a == '-o': outsep = v
    else:
        if not match(r'[1-9][0-9]{0,2}(,[1-9][0-9]{0,2})*',v): fail(2)
        right = {int(x)-1 for x in v.split(',')}
    i += 2
rows = []
for line in stdin_lines():
    rows.append((re.findall(r'[^ \t]+',line) if sep is None else line.split(sep)) if line else [])
widths = [0]*max((len(r) for r in rows),default=0)
for row in rows:
    for i,field in enumerate(row): widths[i] = max(widths[i],len(field))
for row in rows:
    result = []
    for i,f in enumerate(row):
        result.append(f.rjust(widths[i]) if i in right else f.ljust(widths[i]) if i < len(row)-1 else f)
    print(outsep.join(result))
