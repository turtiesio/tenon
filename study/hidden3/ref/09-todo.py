"""Private todo reference with strict byte validation and atomic snapshots."""
from pathlib import Path
import os
import re
import sys

def load(path):
    if not path.exists(): return 1,{}
    data=path.read_bytes()
    if not data.endswith(b'\n'): raise ValueError('newline')
    rows=data[:-1].split(b'\n')
    if len(rows)<2 or rows[0]!=b'TODO 1' or not re.fullmatch(rb'next [1-9][0-9]{0,8}',rows[1]): raise ValueError('header')
    n=int(rows[1][5:]); items={}; previous=0
    for row in rows[2:]:
        m=re.fullmatch(rb'([1-9][0-9]{0,8}) ([1-9]) ([od]) ([\x20-\x7e]+)',row)
        if not m: raise ValueError('item')
        ident=int(m[1])
        if not previous<ident<n: raise ValueError('order')
        previous=ident; items[ident]=(int(m[2]),m[3]==b'd',m[4].decode('ascii'))
    return n,items

def main():
    if len(sys.argv)!=2: return 2
    if not sys.argv[1]: return 1
    directory=Path(sys.argv[1])
    try:
        if not directory.exists(): directory.mkdir()
        if not directory.is_dir(): return 1
        temp=directory/'todo.db.tmp'; temp.unlink(missing_ok=True)
        path=directory/'todo.db'; next_id,items=load(path)
    except (OSError,ValueError): return 1
    def save():
        data='TODO 1\nnext '+str(next_id)+'\n'
        data+=''.join(f'{i} {p} {"d" if d else "o"} {t}\n' for i,(p,d,t) in sorted(items.items()))
        with temp.open('wb') as file: file.write(data.encode('ascii'))
        os.replace(temp,path)
    def show(i):
        p,d,t=items[i]; return f'{i} {p} {"done" if d else "open"} {t}'
    for raw in sys.stdin.buffer:
        raw=raw.removesuffix(b'\n').removesuffix(b'\r')
        changed=False; response='ERR bad command'
        if all(32<=c<=126 for c in raw):
            s=raw.decode('ascii'); add=re.fullmatch(r'ADD ([1-9]) (.+)',s)
            ident=re.fullmatch(r'(DONE|SHOW) ([0-9]{1,9})',s)
            if add:
                i=next_id; next_id+=1; items[i]=(int(add[1]),False,add[2]); changed=True
                response='ADDED '+str(i)
            elif ident:
                op=ident[1]; i=int(ident[2])
                if i not in items: response='ERR no such item'
                elif op=='SHOW': response=show(i)
                elif items[i][1]: response='ERR already done'
                else:
                    p,_,t=items[i]; items[i]=(p,True,t); changed=True; response='OK'
            elif s in ('LIST','NEXT'):
                ids=sorted((i for i in items if not items[i][1]),key=lambda i:(items[i][0],i))
                response=('OPEN'+(' '+' '.join(map(str,ids)) if ids else '')) if s=='LIST' else show(ids[0]) if ids else 'NONE'
            elif s=='PURGE':
                ids=[i for i in items if items[i][1]]
                for i in ids: del items[i]
                changed=bool(ids); response='PURGED '+str(len(ids))
            elif s=='STATS':
                done=sum(d for _,d,_ in items.values()); response=f'open={len(items)-done} done={done} next_id={next_id}'
        if changed:
            try: save()
            except OSError: return 1
        print(response,flush=True)
    return 0

if __name__ == '__main__':
    status=main()
    if status: print('todo: error',file=sys.stderr)
    sys.exit(status)
