"""Private trx reference, implemented from tasks5/02-trx.md."""
import sys
from common import fail

def expand(s):
    tokens = []
    i = 0
    escapes = {'n': '\n', 't': '\t', '\\': '\\', '-': '-'}
    while i < len(s):
        if s[i] == '\\':
            i += 1
            if i == len(s) or s[i] not in escapes: fail(2)
            tokens.append((escapes[s[i]], True))
        else: tokens.append((s[i], False))
        i += 1
    result = []
    i = 0
    while i < len(tokens):
        if i+2 < len(tokens) and tokens[i+1] == ('-', False):
            lo, hi = ord(tokens[i][0]), ord(tokens[i+2][0])
            if lo > hi: fail(2)
            result.extend(chr(x) for x in range(lo, hi+1))
            i += 3
        else:
            result.append(tokens[i][0])
            i += 1
    return result

args = sys.argv[1:]
delete = squeeze = False
i = 0
while i < len(args):
    if args[i] == '-d': delete = True
    elif args[i] == '-s': squeeze = True
    elif args[i] == '--':
        i += 1
        break
    else:
        if len(args[i]) >= 2 and args[i].startswith('-'): fail(2)
        break
    i += 1
sets = args[i:]
allowed = (2,) if not squeeze else ((2,) if delete else (1, 2))
if delete and not squeeze: allowed = (1,)
if len(sets) not in allowed: fail(2)
sets = [expand(s) for s in sets]
translate = not delete and len(sets) == 2
if translate and not sets[1]: fail(2)
mapping = {c: sets[1][min(i,len(sets[1])-1)] for i,c in enumerate(sets[0])} if translate else {}
squeezed = set(sets[-1]) if squeeze else set()
removed = set(sets[0]) if delete else set()
out = []
for c in sys.stdin.buffer.read().decode('ascii'):
    if c in removed: continue
    c = mapping.get(c,c)
    if c in squeezed and out and out[-1] == c: continue
    out.append(c)
sys.stdout.buffer.write(''.join(out).encode('ascii'))
