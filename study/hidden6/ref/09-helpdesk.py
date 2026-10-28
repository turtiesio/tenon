import re
import sys
from pathlib import Path
from common import fail, emit
if len(sys.argv)!=2: fail(2)
name=r'[a-z0-9]{1,12}'; tid=r'T[1-9][0-9]{0,8}'; title=r'[!-~](?:[ -~]{0,58}[!-~])?'
forms=[r'OPEN ('+name+r') ('+title+r')',r'ASSIGN ('+tid+r') ('+name+r')',r'(?:CLOSE|REOPEN|SHOW) ('+tid+r')',r'QUEUE ('+name+r'|-)']
tickets={}; nxt=1
# Compute response/change independently of journal I/O, so invalid replay is atomic.
def command(line):
    global nxt
    m=next((m for p in forms if (m:=re.fullmatch(p,line))),None)
    if not m: return 'ERR bad command',None
    cmd=line.split(' ')[0]; a=m.groups()
    if cmd=='OPEN':
        i=nxt; nxt+=1; tickets[i]=[a[0],None,a[1],True]
        return f'T{i}',f'OPEN T{i} {a[0]} {a[1]}'
    if cmd=='QUEUE':
        agent=None if a[0]=='-' else a[0]
        return ' '.join(f'T{i}' for i,t in sorted(tickets.items()) if t[3] and t[1]==agent) or '-',None
    i=int(a[0][1:])
    if i not in tickets: return 'ERR no such ticket',None
    t=tickets[i]
    if cmd in ('ASSIGN','CLOSE') and not t[3]: return 'ERR closed',None
    if cmd=='REOPEN' and t[3]: return 'ERR not closed',None
    if cmd=='SHOW': return f'T{i} '+('open' if t[3] else 'closed')+f' {t[0]} {t[1] or "-"} {t[2]}',None
    if cmd=='ASSIGN':
        if t[1]==a[1]: return 'UNCHANGED',None
        t[1]=a[1]
    else: t[3]=cmd=='REOPEN'
    return 'OK',line
try:
    directory=Path(sys.argv[1])
    if not directory.exists(): directory.mkdir()
    if not directory.is_dir(): fail()
    journal=directory/'tickets.log'
    data=journal.read_bytes() if journal.exists() else b''
    end=data.rfind(b'\n')+1
    prefix=data[:end]
    for raw in prefix.split(b'\n')[:-1]:
        record=raw.decode('ascii')
        m=re.fullmatch(r'OPEN ('+tid+r') ('+name+r') ('+title+r')',record)
        if m:
            if int(m[1][1:])!=nxt: fail()
            response,written=command('OPEN '+m[2]+' '+m[3])
        else:
            if not record.startswith(('ASSIGN ','CLOSE ','REOPEN ')): fail()
            response,written=command(record)
            if response!='OK': fail()
        if written!=record: fail()
    if end!=len(data):
        with journal.open('r+b') as stream: stream.truncate(end)
    for raw in sys.stdin.buffer:
        line=raw.decode('ascii').removesuffix('\n').removesuffix('\r')
        response,record=command(line)
        if record:
            with journal.open('ab') as stream:
                stream.write((record+'\n').encode('ascii')); stream.flush()
        emit(response+'\n')
except (OSError,UnicodeError): fail()
