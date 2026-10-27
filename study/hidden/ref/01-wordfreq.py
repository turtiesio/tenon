"""Private spec-only reference; no acceptance-case access."""
import collections
import re
import sys

def main(a):
    n, length, fold, files, end = 10, 1, False, [], False
    i = 0
    while i < len(a):
        x = a[i]
        if not end and x == '--':
            end = True
        elif not end and x in ('-i', '--ignore-case'):
            fold = True
        elif not end and (x in ('-n','--top','-m','--min-length') or x.startswith(('--top=','--min-length='))):
            opt = x.split('=')[0]
            if '=' in x:
                value = x.split('=',1)[1]
            else:
                i += 1
                if i == len(a): return 2
                value = a[i]
            top = opt in ('-n','--top')
            if not re.fullmatch('[0-9]+',value): return 2
            v = int(value)
            if not (0 <= v <= 1000000000 if top else 1 <= v <= 1000): return 2
            if top: n = v
            else: length = v
        elif not end and x.startswith('-') and x != '-':
            return 2
        else: files.append(x)
        i += 1
    counts = collections.Counter()
    rc = 0
    for f in files or ['-']:
        try:
            data = sys.stdin.buffer.read() if f == '-' else open(f,'rb').read()
        except OSError:
            rc = 1
            continue
        if fold: data = data.lower()
        counts.update(w for w in re.findall(rb'[A-Za-z0-9]+',data) if len(w) >= length)
    words = sorted(counts, key=lambda w:(-counts[w],w))
    if n: words = words[:n]
    for w in words: print(counts[w],w.decode('ascii'))
    return rc
sys.exit(main(sys.argv[1:]))
