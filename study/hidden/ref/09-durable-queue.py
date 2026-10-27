"""Private spec-only reference; private snapshot encoding, atomic replacement."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile

def main():
    if len(sys.argv)!=2: return 2
    directory=Path(sys.argv[1])
    try:
        if not directory.exists(): directory.mkdir()
        if not directory.is_dir(): return 1
        path=directory/'queue.snap'
        state=json.loads(path.read_text()) if path.exists() else dict(next=1,acked=0,jobs={})
    except OSError: return 1
    for job in state['jobs'].values(): job[2]='ready'
    def save():
        fd,name=tempfile.mkstemp(prefix='queue.snap.tmp',dir=directory)
        with os.fdopen(fd,'w') as f: json.dump(state,f)
        os.replace(name,path)
    for raw in sys.stdin.buffer:
        line=raw.decode().removesuffix('\n').removesuffix('\r'); changed=False
        put=re.fullmatch(r'PUT ([!-~]{1,64})',line)
        op=re.fullmatch(r'(ACK|NACK) ([1-9][0-9]{0,15})',line)
        if put:
            n=state['next']; state['next']+=1; state['jobs'][str(n)]=[put[1],0,'ready']; answer='OK '+str(n); changed=True
        elif line=='GET':
            ready=[int(n) for n,j in state['jobs'].items() if j[2]=='ready']
            if not ready: answer='EMPTY'
            else:
                n=min(ready); j=state['jobs'][str(n)]; j[1]+=1; j[2]='inflight'; changed=True
                answer='JOB %d %d %s'%(n,j[1],j[0])
        elif op:
            kind,n=op.groups(); j=state['jobs'].get(n)
            if not j or j[2]!='inflight': answer='ERR not in flight'
            else:
                if kind=='ACK': del state['jobs'][n]; state['acked']+=1
                else: j[2]='ready'
                answer='OK'; changed=True
        elif line=='STATS':
            inflight=sum(j[2]=='inflight' for j in state['jobs'].values())
            answer='ready=%d inflight=%d acked=%d next=%d'%(len(state['jobs'])-inflight,inflight,state['acked'],state['next'])
        else: answer='ERR bad command'
        if changed: save()
        print(answer,flush=True)
    return 0
sys.exit(main())
