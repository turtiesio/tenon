"""Audit structure, examples, fixture domains, limits and Python syntax."""
import ast
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent
NAME=re.compile(r'[a-z0-9][a-z0-9_-]*\Z')

def lines(data):
    result=data.split(b'\n')
    if result[-1]==b'': result.pop()
    return [s[:-1] if s.endswith(b'\r') else s for s in result]

def check():
    cases=runs=kills=0; task_ids=[]
    for task in sorted(ROOT.glob('[0-9][0-9]-*')):
        task_ids.append(task.name); number=task.name[:2]
        entries=sorted((task/'cases').iterdir())
        assert len(entries)==25,(task,len(entries))
        spec=(ROOT.parent/'tasks3'/(task.name+'.md')).read_text()
        examples=re.findall(r'^### Example ([0-9]+):',spec,re.M)
        assert {c.name for c in entries if c.name.startswith('example-')}=={'example-'+n for n in examples},task
        for case in entries:
            assert case.is_dir() and NAME.fullmatch(case.name),case
            cases+=1
            if (case/'steps').exists():
                assert not any((case/x).exists() for x in ('cmd','stdin','expected_stdout','expected_exit')),case
                steps=[]
                for row in (case/'steps').read_text().splitlines():
                    m=re.fullmatch(r'([a-z0-9][a-z0-9_-]*)(?: kill-after=([1-9][0-9]*))?',row)
                    assert m,(case,row)
                    steps.append((case/m[1],int(m[2]) if m[2] else None))
                assert steps and len({s for s,k in steps})==len(steps),case
            else: steps=[(case,None)]
            for step,kill in steps:
                runs+=1; cmd=(step/'cmd').read_bytes(); out=(step/'expected_stdout').read_bytes()
                assert not cmd or cmd.endswith(b'\n'),step
                args=cmd.decode('utf-8').split('\n')[:-1] if cmd else []
                data=(step/'stdin').read_bytes() if (step/'stdin').exists() else b''
                if kill:
                    kills+=1
                    assert number in ('07','08','09'),step
                    assert not (step/'expected_exit').exists(),step
                    assert out.endswith(b'\n') and out.count(b'\n')==kill,step
                    assert data.count(b'\n')>=kill,step
                else:
                    code=int((step/'expected_exit').read_text())
                    assert code in (0,1,2,3),step
                    assert number=='06' or code!=3,step
                if number=='01': assert len(data)<=1000000,step
                if number=='03':
                    assert len(data)<=100000,step
                    # All non-option pattern candidates, including invalid ones.
                    assert all(len(a.encode('ascii'))<=40 for a in args),step
                    assert all(a.count('*')<=20 for a in args),step
                if number in ('05','06','07','08','09','10'):
                    rows=lines(data)
                    limit={'05':10000,'06':10000,'07':100000,'08':20000,'09':10000,'10':200000}[number]
                    assert len(rows)<=limit,step
                    if number=='05':
                        teams=set()
                        for row in rows:
                            m=re.fullmatch(rb"([A-Za-z0-9.&']+(?: [A-Za-z0-9.&']+)*) [0-9]{1,2}-[0-9]{1,2} ([A-Za-z0-9.&']+(?: [A-Za-z0-9.&']+)*)",row)
                            if m: teams.update(m.groups())
                        assert len(teams)<=99,step
                    if number=='06':
                        items=set()
                        for row in rows:
                            if b':' not in row: continue
                            head,tail=row.split(b':',1)
                            for n in [head.strip(b' ')]+tail.split(b' '):
                                if re.fullmatch(rb'[A-Za-z0-9_./-]+',n):
                                    assert len(n)<=64,step
                                    items.add(n)
                        assert len(items)<=10000,step
                    if number=='07':
                        for row in rows:
                            m=re.fullmatch(rb'(?:APPEND |(?:INSERT|REPLACE) [0-9]{1,9} )(.*)',row)
                            if m: assert len(m[1])<=1000,step
                    if number=='08': assert max(map(len,rows),default=0)<=200,step
                    if number=='09':
                        for row in rows:
                            if row.startswith(b'ADD '):
                                tokens=row.split(b' ',2)
                                if len(tokens)==3: assert len(tokens[2])<=200,step
            for file in (case/'setup').rglob('*') if (case/'setup').exists() else []:
                assert not file.is_symlink(),file
                if not file.is_file(): continue
                data=file.read_bytes()
                if number=='04':
                    assert len(data)<=1000000,file
                    # Quote-aware count of physical record terminators; malformed
                    # fixtures are short and do not approach the record limit.
                    count=0; quoted=False; i=0
                    while i<len(data):
                        c=data[i]
                        if c==34:
                            if quoted and i+1<len(data) and data[i+1]==34: i+=2; continue
                            quoted=not quoted
                        elif c==10 and not quoted: count+=1
                        i+=1
                    if data and not data.endswith(b'\n'): count+=1
                    assert count<=10000,file
                if number=='09' and file.name=='todo.db':
                    rows=lines(data)
                    assert max(0,len(rows)-2)<=10000,file
                    for row in rows[2:]:
                        m=re.fullmatch(rb'[1-9][0-9]{0,8} [1-9] [od] ([\x20-\x7e]+)',row)
                        if m: assert len(m[1])<=200,file
    assert len(task_ids)==10 and cases==250,task_ids
    for source in ROOT.rglob('*.py'): ast.parse(source.read_text(),filename=str(source))
    print(f'AUDIT PASS: {cases} cases; {runs} process runs; {kills} kill steps')

if __name__=='__main__': check()
