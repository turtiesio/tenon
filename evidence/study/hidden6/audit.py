"""Audit fixture structure, frozen-example coverage, limits, and validation artifacts."""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parent
NAME=re.compile(r'[a-z0-9][a-z0-9_-]*\Z')
TASKS=['01-wcx','02-b64','03-hsize','04-shoplist','05-orgchart','06-climate','07-rooms','08-locks','09-helpdesk','10-sand']
def fixture_manifest():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for t in TASKS for p in sorted((ROOT/t/'cases').rglob('*')) if p.is_file()}
def rows(raw):
    result=raw.split(b'\n')
    if result[-1]==b'': result.pop()
    return result
if sys.argv[1:]==['--manifest']:
    print(''.join(f'{digest}  {name}\n' for name,digest in sorted(fixture_manifest().items())),end='')
    raise SystemExit
runs=kills=examples=multis=0
for t in TASKS:
    task=ROOT/t; cases=sorted((task/'cases').iterdir())
    assert len(cases)==25,(t,len(cases))
    spec=(ROOT.parent/'tasks6'/(t+'.md')).read_text()
    nums=re.findall(r'^### Example ([0-9]+):',spec,re.M)
    assert {p.name for p in cases if p.name.startswith('example-')}=={'example-'+n for n in nums}
    examples+=len(nums); codes=set()
    for case in cases:
        assert NAME.fullmatch(case.name)
        if (case/'steps').exists():
            multis+=1; steps=[]
            assert not any((case/x).exists() for x in ['cmd','stdin','expected_stdout','expected_exit'])
            for entry in (case/'steps').read_text().splitlines():
                m=re.fullmatch(r'([a-z0-9][a-z0-9_-]*)(?: kill-after=([1-9][0-9]*))?',entry)
                assert m,entry
                steps.append((case/m[1],int(m[2]) if m[2] else None))
            assert len({p.name for p,_ in steps})==len(steps)
            assert {p.name for p in case.iterdir()}=={'steps',*('setup' for _ in [0] if (case/'setup').exists()),*(p.name for p,_ in steps)}
        else: steps=[(case,None)]
        for step,kill in steps:
            runs+=1
            cmd=(step/'cmd').read_bytes()
            assert not cmd or cmd.endswith(b'\n')
            args=[a.decode('utf-8') for a in rows(cmd)]
            assert all('\x00' not in a for a in args)
            data=(step/'stdin').read_bytes() if (step/'stdin').exists() else b''
            expected=(step/'expected_stdout').read_bytes()
            allowed={'cmd','stdin','expected_stdout'}|({'expected_exit'} if not kill else set())
            if step==case: allowed.add('setup')
            assert all(p.name in allowed for p in step.iterdir())
            if kill:
                kills+=1
                assert not (step/'expected_exit').exists()
                assert t in ['07-rooms','08-locks','09-helpdesk']
                assert expected.endswith(b'\n') and expected.count(b'\n')==kill
                assert len(rows(data))>=kill and all(data.splitlines(keepends=True)[i].endswith(b'\n') for i in range(kill))
                if t=='09-helpdesk': assert len(rows(data))>kill # deliberately unsent mutation
            else:
                exit_code=int((step/'expected_exit').read_text()); codes.add(exit_code)
            if t=='02-b64': assert len(data)<=1000000
            if t=='03-hsize': assert len(rows(data))<=10000
            if t in ['07-rooms','08-locks','09-helpdesk']: assert len(rows(data))<=10000
            if t=='07-rooms':
                assert sum(line.startswith(b'ROOM ') for line in rows(data))<=100
                assert sum(line.startswith(b'BOOK ') for line in rows(data))<=10000
            if t=='08-locks':
                clients=set(); resources=set()
                for line in rows(data):
                    f=line.decode('ascii').removesuffix('\r').split(' ')
                    if f[0] in ('LOCK','UNLOCK') and len(f)>=3: clients.add(f[1]); resources.add(f[2])
                assert len(clients)<=1000 and len(resources)<=1000
            if t=='05-orgchart': assert len([r for r in rows(data)[1:] if r])<=10000
        setup=case/'setup'
        if t=='04-shoplist' and setup.exists():
            assert all(len(rows(p.read_bytes()))<=1000 for p in setup.rglob('*') if p.is_file())
        if t=='09-helpdesk' and setup.exists():
            for p in setup.rglob('tickets.log'):
                if p.is_file():
                    data=p.read_bytes()
                    assert data.count(b'\n')<=100000
                    assert sum(r.startswith(b'OPEN ') for r in rows(data))<=100000
    assert codes==({0,2} if t in ['06-climate','07-rooms','08-locks'] else {0,1,2}),(t,codes)
# Compile without writing bytecode; references use only stdlib and local common.
for p in sorted(ROOT.glob('*.py'))+sorted((ROOT/'ref').glob('*.py')):
    source=p.read_text(); compile(source,str(p),'exec')
    tree=ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): modules=[a.name.split('.')[0] for a in node.names]
        elif isinstance(node,ast.ImportFrom): modules=[node.module.split('.')[0]]
        else: continue
        assert all(m in sys.stdlib_module_names or m=='common' for m in modules),(p,modules)
        if p.name=='build_cases.py': assert set(modules)<={'pathlib','shutil'}
for label,passed in [('reference',250),('silent',10)]:
    data=json.loads((ROOT/(label+'-results.json')).read_text())
    assert data['total']==250 and data['passed']==passed
    assert sum(len(c['steps']) for c in data['results'])==runs
    assert {(c['task'],c['case']) for c in data['results']}=={(t,p.name) for t in TASKS for p in (ROOT/t/'cases').iterdir()}
    assert (ROOT/(label+'-validation.log')).read_text().rstrip().endswith(f'{passed}/250 passed; {250-passed} failed')
print(f'AUDIT PASS: 250 cases; {runs} process runs; {examples} numbered examples; {multis} multi-run cases; {kills} kill steps; {len(fixture_manifest())} fixture files')
