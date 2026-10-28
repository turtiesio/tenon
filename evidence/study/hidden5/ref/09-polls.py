"""Private polls reference, implemented from tasks5/09-polls.md."""
from pathlib import Path
import re
import sys
from common import fail, emit
if len(sys.argv) != 2: fail(2)
try:
    directory = Path(sys.argv[1])
    if not directory.exists(): directory.mkdir()
    if not directory.is_dir(): fail(1)
except OSError: fail(1)
name = r'[a-z0-9]{1,12}'
forms = [r'CREATE '+name+'(?: '+name+'){2,9}',r'VOTE '+name+' '+name+' '+name,r'CLOSE '+name,r'RESULT '+name]
polls = {}
def apply(line):
    if not any(re.fullmatch(p,line) for p in forms): return 'ERR bad command'
    t = line.split(' ')
    command,p = t[:2]
    if command == 'CREATE':
        if len(set(t[2:])) != len(t)-2: return 'ERR bad command'
        if p in polls: return 'ERR poll exists'
        polls[p] = [t[2:],{},False]
        return 'OK'
    if p not in polls: return 'ERR no such poll'
    options,votes,closed = polls[p]
    if command in ('VOTE','CLOSE') and closed: return 'ERR poll closed'
    if command == 'CLOSE':
        polls[p][2] = True
        return 'OK'
    if command == 'VOTE':
        voter,option = t[2:]
        if option not in options: return 'ERR no such option'
        old = votes.get(voter)
        if old == option: return 'UNCHANGED'
        votes[voter] = option
        return 'VOTED' if old is None else 'CHANGED'
    counts = {o:0 for o in options}
    for option in votes.values(): counts[option] += 1
    return p+(' closed' if closed else ' open')+''.join(f' {o}={counts[o]}' for o in options)
journal = directory/'polls.log'
try:
    raw = journal.read_bytes() if journal.exists() else b''
    end = raw.rfind(b'\n')+1
    complete = raw[:end]
    # Validate before altering even a torn suffix on an invalid journal.
    for record in complete.split(b'\n')[:-1]:
        line = record.decode('ascii')
        if not line.startswith(('CREATE ','VOTE ','CLOSE ')) or apply(line) not in ('OK','VOTED','CHANGED'): fail(1)
    if end != len(raw):
        with journal.open('r+b') as stream: stream.truncate(end)
except (OSError,UnicodeError): fail(1)
for raw in sys.stdin.buffer:
    line = raw.decode('utf-8').removesuffix('\n').removesuffix('\r')
    response = apply(line)
    if response in ('OK','VOTED','CHANGED'):
        try:
            with journal.open('ab') as stream:
                stream.write((line+'\n').encode('ascii'))
                stream.flush()
        except OSError: fail(1)
    emit(response)
