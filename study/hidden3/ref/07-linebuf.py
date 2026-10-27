"""Private linebuf reference. History stores reversible splice operations."""
import re
import sys

def main():
    if len(sys.argv)!=1: return 2
    buffer=[]; undo=[]; redo=[]
    def apply(change,forward):
        at,before,after=change
        old,new=(before,after) if forward else (after,before)
        buffer[at:at+len(old)]=new
    for raw in sys.stdin.buffer:
        s=raw.removesuffix(b'\n').removesuffix(b'\r').decode('ascii')
        response='ERR bad command'; change=None
        m=re.fullmatch(r'(INSERT|REPLACE) ([0-9]{1,9}) (.*)',s)
        d=re.fullmatch(r'DELETE ([0-9]{1,9})(?: ([0-9]{1,9}))?',s)
        p=re.fullmatch(r'PRINT ([0-9]{1,9})',s)
        if s.startswith('APPEND '): change=(len(buffer),[],[s[7:]])
        elif m:
            op,n,text=m.groups(); n=int(n)
            if not 1<=n<=len(buffer)+(op=='INSERT'): response='ERR bad line'
            else: change=(n-1,[] if op=='INSERT' else [buffer[n-1]],[text])
        elif d:
            a=int(d[1]); b=int(d[2]) if d[2] is not None else a
            if not 1<=a<=b<=len(buffer): response='ERR bad line'
            else: change=(a-1,buffer[a-1:b],[])
        elif p:
            n=int(p[1]); response=f'{n}|{buffer[n-1]}' if 1<=n<=len(buffer) else 'ERR bad line'
        elif s.startswith('FIND ') and s[5:]:
            found=[str(i) for i,t in enumerate(buffer,1) if s[5:] in t]
            response=' '.join(found) or 'NONE'
        elif s=='COUNT': response=str(len(buffer))
        elif s in ('UNDO','REDO'):
            source,dest=(undo,redo) if s=='UNDO' else (redo,undo)
            if not source: response='ERR nothing to '+s.lower()
            else:
                record=source.pop(); apply(record,s=='REDO'); dest.append(record)
                response='OK '+str(len(buffer))
        if change is not None:
            apply(change,True); undo.append(change); redo.clear(); response='OK '+str(len(buffer))
        print(response,flush=True)
    return 0

if __name__ == '__main__':
    status=main()
    if status: print('linebuf: usage',file=sys.stderr)
    sys.exit(status)
