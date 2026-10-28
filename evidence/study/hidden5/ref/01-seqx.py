"""Private seqx reference, implemented from tasks5/01-seqx.md."""
import sys
from common import fail, match
args = sys.argv[1:]
sep, width, limit = '\n', False, None
numbers = []
i = 0
while i < len(args):
    a = args[i]
    if a in ('-s', '-n'):
        i += 1
        if i == len(args): fail(2)
        if a == '-s': sep = args[i]
        else:
            if not match(r'[0-9]{1,9}', args[i]): fail(2)
            limit = int(args[i])
    elif a == '-w': width = True
    else:
        if not match(r'-?[0-9]{1,18}', a): fail(2)
        numbers.append(int(a))
    i += 1
if len(numbers) not in (2, 3): fail(2)
first, step, last = (numbers[0], 1, numbers[1]) if len(numbers) == 2 else numbers
if step == 0: fail(2)
count = max(0, (last-first)//step + 1) if (last-first)*step >= 0 else 0
if limit is not None: count = min(count, limit)
values = [str(first + i*step) for i in range(count)]
if width and values:
    w = max(map(len, values))
    values = [v.zfill(w) for v in values]
if values: sys.stdout.write(sep.join(values)+'\n')
