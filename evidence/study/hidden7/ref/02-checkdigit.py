import sys
from common import match, fail
args=sys.argv[1:]
if len(args)<3 or args[0] not in ('luhn','isbn10','isbn13') or args[1] not in ('make','check'): fail(2)
scheme,mode=args[:2]; code=0

def correct(s):
    ds=[10 if c=='X' else int(c) for c in s]
    if scheme=='luhn':
        return sum((2*d-9 if d>=5 else 2*d) if i%2 else d for i,d in enumerate(reversed(ds)))%10==0
    if scheme=='isbn10': return sum(d*(10-i) for i,d in enumerate(ds))%11==0
    return sum(d*(1 if i%2==0 else 3) for i,d in enumerate(ds))%10==0
for v in args[2:]:
    digits=v.replace('-','')
    lo,hi={'luhn':(2,19),'isbn10':(10,10),'isbn13':(13,13)}[scheme]
    if mode=='make': lo-=1; hi-=1
    valid=match('[0-9X]+(-[0-9X]+)*',v) and lo<=len(digits)<=hi
    if 'X' in v: valid=valid and scheme=='isbn10' and mode=='check' and v.endswith('X') and v.count('X')==1
    if scheme=='isbn13': valid=valid and digits[:3] in ('978','979')
    if not valid: print(v+' invalid'); code=1
    elif mode=='check':
        ok=correct(digits); print(v+(' ok' if ok else ' bad')); code=max(code,not ok)
    else:
        check=next(c for c in ('0123456789X' if scheme=='isbn10' else '0123456789') if correct(digits+c))
        print(v+('-' if '-' in v else '')+check)
sys.exit(code)
