"""Private spec-only reference."""
import re
import sys

def main(a):
    fields=None; delim='\t'; output=None; only=False; files=[]; end=False; i=0
    while i<len(a):
        x=a[i]
        if not end and x=='--': end=True
        elif not end and x in ('-s','--only-delimited'): only=True
        elif not end and x.startswith('--output-delimiter='): output=x.split('=',1)[1]
        elif not end and (x.startswith('-f') or x.startswith('-d')):
            kind=x[1]
            if len(x)==2:
                i+=1
                if i==len(a): return 2
                v=a[i]
            else: v=x[2:]
            if kind=='d':
                if len(v)!=1 or ord(v)>127: return 2
                delim=v
            else:
                parsed=[]
                for element in v.split(','):
                    if not re.fullmatch(r'(?:[0-9]+(?:-[0-9]*)?|-[0-9]+)',element): return 2
                    parts=element.split('-')
                    if any(p and not 1<=int(p)<=1000000 for p in parts): return 2
                    lo=int(parts[0]) if parts[0] else 1
                    hi=(int(parts[1]) if parts[1] else None) if len(parts)==2 else lo
                    if hi is not None and lo>hi: return 2
                    parsed.append((lo,hi))
                fields=parsed
        elif not end and x.startswith('-') and x!='-': return 2
        else: files.append(x)
        i+=1
    if fields is None: return 2
    rc=0
    for f in files or ['-']:
        try: data=sys.stdin.read() if f=='-' else open(f,encoding='utf-8',newline='').read()
        except OSError:
            rc=1; continue
        lines=data.split('\n')
        if lines[-1]=='': lines.pop()
        for line in lines:
            if delim not in line:
                if not only: sys.stdout.write(line+'\n')
                continue
            items=line.split(delim); selected=[]
            for lo,hi in fields: selected.extend(items[lo-1:min(hi,len(items)) if hi is not None else len(items)])
            sys.stdout.write((delim if output is None else output).join(selected)+'\n')
    return rc
sys.exit(main(sys.argv[1:]))
