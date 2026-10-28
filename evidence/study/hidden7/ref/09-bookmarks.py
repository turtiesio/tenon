import os
from pathlib import Path
import sys
from common import match, fail, incoming, say
if len(sys.argv)!=2: fail(2)
name=r'[a-z0-9-]{1,20}'; url=r'[!-~]{1,200}'; tag=r'[a-z0-9]{1,12}'
patterns={'ADD':f'ADD {name} {url}','DEL':f'DEL {name}','TAG':f'TAG {name} {tag}','UNTAG':f'UNTAG {name} {tag}','GET':f'GET {name}','FIND':f'FIND {tag}','COMPACT':'COMPACT'}
state={}
def parse(s):
    t=s.split(' ')
    return t if t[0] in patterns and match(patterns[t[0]],s) else None

def apply(t):
    op=t[0]
    if op=='ADD':
        if t[1] in state: return 'ERR exists'
        state[t[1]]=(t[2],set()); return 'OK'
    if op=='FIND': return ' '.join(n for n in sorted(state) if t[1] in state[n][1]) or '-'
    if t[1] not in state: return 'ERR no such bookmark'
    if op=='GET': return display(t[1])
    if op=='DEL': del state[t[1]]; return 'OK'
    tags=state[t[1]][1]
    if op=='TAG':
        if t[2] in tags: return 'UNCHANGED'
        tags.add(t[2]); return 'OK'
    if t[2] not in tags: return 'UNCHANGED'
    tags.remove(t[2]); return 'OK'

def display(n):
    u,t=state[n]; return n+' '+u+' '+(','.join(sorted(t)) or '-')
try:
    directory=Path(sys.argv[1])
    if not directory.exists(): directory.mkdir()
    if not directory.is_dir(): raise ValueError()
    snapshot=directory/'snapshot'; journal=directory/'journal'; temp=directory/'snapshot.tmp'; seq=0
    if snapshot.exists():
        data=snapshot.read_bytes()
        if not data.endswith(b'\n'): raise ValueError()
        rows=data.decode('ascii').split('\n')[:-1]
        if not rows or not match(r'bookmarks (0|[1-9][0-9]*)',rows[0]): raise ValueError()
        seq=int(rows[0].split(' ')[1]); prev=''
        for row in rows[1:]:
            t=row.split(' ')
            if len(t)!=3 or not match(name,t[0]) or not match(url,t[1]) or t[0]<=prev: raise ValueError()
            tags=[] if t[2]=='-' else t[2].split(',')
            if any(not match(tag,x) for x in tags) or any(a>=b for a,b in zip(tags,tags[1:])): raise ValueError()
            state[t[0]]=(t[1],set(tags)); prev=t[0]
    raw=journal.read_bytes() if journal.exists() else b''
    cut=raw.rfind(b'\n')+1; complete=raw[:cut]; records=[]
    for row in complete.decode('ascii').split('\n')[:-1]:
        if ' ' not in row: raise ValueError()
        number,s=row.split(' ',1); t=parse(s)
        if not match('[1-9][0-9]*',number) or t is None or t[0] not in ('ADD','DEL','TAG','UNTAG'): raise ValueError()
        records.append((int(number),t))
    if records:
        if records[0][0]>seq+1 or records[-1][0]<seq or any(b[0]!=a[0]+1 for a,b in zip(records,records[1:])): raise ValueError()
        for n,t in records:
            if n>seq and apply(t)!='OK': raise ValueError()
        seq=max(seq,records[-1][0])
    # Validate before discarding any torn bytes, to preserve unusable files.
    if cut!=len(raw):
        with journal.open('r+b') as f: f.truncate(cut)
except (OSError,ValueError,UnicodeError): fail(1,'unusable data')
for s in incoming():
    t=parse(s)
    if t is None: say('ERR bad command'); continue
    try:
        if t[0]=='COMPACT':
            text=f'bookmarks {seq}\n'+''.join(display(n)+'\n' for n in sorted(state))
            with temp.open('wb') as f: f.write(text.encode('ascii')); f.flush()
            os.replace(temp,snapshot)
            with journal.open('wb'): pass
            say(f'OK {seq}')
        else:
            result=apply(t)
            if result=='OK':
                seq+=1
                with journal.open('ab') as f: f.write(f'{seq} {s}\n'.encode('ascii')); f.flush()
            say(result)
    except OSError: fail(1,'write failed')
