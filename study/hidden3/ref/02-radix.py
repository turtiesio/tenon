"""Private spec-derived reference for radix (stdlib only)."""
import re
import sys

def main():
    opts = {'-f':10,'-t':10,'-w':0,'-g':0,'-u':False}
    values = []
    a = iter(sys.argv[1:])
    for x in a:
        if x == '-u': opts[x] = True
        elif x in ('-f','-t','-w','-g'):
            v = next(a, '')
            if not re.fullmatch(r'[0-9]{1,2}',v): return 2
            n = int(v)
            if not (2 <= n <= 36 if x in ('-f','-t') else 1 <= n <= 64): return 2
            opts[x] = n
        else: values.append(x)
    if not values: return 2
    status = 0
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    for value in values:
        s = value[1:] if value.startswith('-') else value
        if not re.fullmatch('[0-9a-zA-Z]+',s) or any(alphabet.index(c.lower()) >= opts['-f'] for c in s):
            status = 1; continue
        n = 0
        for c in s:
            n = n*opts['-f'] + alphabet.index(c.lower())
            if n > 9223372036854775807: break
        if n > 9223372036854775807:
            status = 1; continue
        negative = value.startswith('-') and n != 0
        digits = ''
        while n:
            n, d = divmod(n, opts['-t']); digits = alphabet[d]+digits
        digits = (digits or '0').rjust(opts['-w'],'0')
        if opts['-g']:
            g = opts['-g']; chunks = []
            while digits: chunks.append(digits[-g:]); digits = digits[:-g]
            digits = '_'.join(reversed(chunks))
        if opts['-u']: digits = digits.upper()
        print(('-' if negative else '')+digits)
    return status

if __name__ == '__main__':
    status = main()
    if status: print('radix: error',file=sys.stderr)
    sys.exit(status)
