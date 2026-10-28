import sys
from common import match, fail, split
args = sys.argv[1:]
base, precision, sizes, i = 1024, 1, [], 0
while i < len(args):
    a = args[i]
    if a == '-s': base = 1000
    elif a == '-p':
        i += 1
        if i == len(args) or args[i] not in ('0','1','2'): fail(2)
        precision = int(args[i])
    elif match(r'[0-9]{1,16}',a): sizes.append(a)
    else: fail(2)
    i += 1
if not sizes: sizes = split(sys.stdin.buffer.read().decode('ascii'))
code = 0
units = ['B','KiB','MiB','GiB','TiB','PiB'] if base == 1024 else ['B','kB','MB','GB','TB','PB']
for value in sizes:
    if not match(r'[0-9]{1,16}',value): print('?'); code=1; continue
    v = int(value)
    if v < base: print(f'{v} B'); continue
    k = 1
    while k < 5 and v >= base**(k+1): k+=1
    scale = 10**precision
    while True:
        div = base**k
        rounded = (2*v*scale+div)//(2*div)
        if rounded >= base*scale and k < 5: k+=1
        else: break
    text = str(rounded//scale)
    if precision: text += '.'+str(rounded%scale).zfill(precision)
    print(text+' '+units[k])
sys.exit(code)
