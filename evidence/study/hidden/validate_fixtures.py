"""Structural validation of the README's byte-oriented fixture format."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent
NAME=re.compile(r'[a-z0-9][a-z0-9_-]*\Z')

def check_run(p,kill=None):
    allowed={'cmd','stdin','expected_stdout'} | ({'expected_exit'} if kill is None else set())
    assert {x.name for x in p.iterdir()}<=allowed,(p,'unexpected run file')
    for f in ['cmd','expected_stdout']+(['expected_exit'] if kill is None else []): assert (p/f).is_file(),(p,f)
    raw=(p/'cmd').read_bytes(); raw.decode('utf-8')
    assert not raw or raw.endswith(b'\n'),p
    if kill is None: assert re.fullmatch(rb'-?[0-9]+\n?',(p/'expected_exit').read_bytes()),p
    else:
        out=(p/'expected_stdout').read_bytes()
        assert out.endswith(b'\n') and out.count(b'\n')==kill,p
        assert (p/'stdin').read_bytes().count(b'\n')>=kill,p

total=normal=kills=0
for task in sorted(ROOT.glob('[0-9][0-9]-*')):
    cases=sorted((task/'cases').iterdir())
    assert 12<=len(cases)<=25,(task,len(cases))
    assert all((task/'cases'/('example-'+str(i))).exists() for i in range(1,6)),task
    for case in cases:
        total+=1
        assert case.is_dir() and NAME.fullmatch(case.name),case
        if (case/'steps').exists():
            expected={'steps','setup'}
            for line in (case/'steps').read_text().split('\n'):
                if not line.strip(): continue
                m=re.fullmatch(r'([a-z0-9][a-z0-9_-]*)(?: kill-after=([1-9][0-9]*))?',line)
                assert m,(case,line)
                expected.add(m[1]); kill=int(m[2]) if m[2] else None
                check_run(case/m[1],kill)
                kills+=kill is not None; normal+=kill is None
            assert {p.name for p in case.iterdir()}<=expected,case
        else:
            # setup belongs to the case, not to a multi-run step.
            files={p.name for p in case.iterdir()}
            assert files<= {'cmd','stdin','expected_stdout','expected_exit','setup'},case
            raw=(case/'cmd').read_bytes(); raw.decode('utf-8')
            assert not raw or raw.endswith(b'\n'),case
            assert (case/'expected_stdout').is_file(),case
            assert re.fullmatch(rb'-?[0-9]+\n?',(case/'expected_exit').read_bytes()),case
            normal+=1
        if (case/'setup').exists(): assert (case/'setup').is_dir(),case
    print(task.name,len(cases))
print('%d cases; %d normal invocations; %d kill invocations'%(total,normal,kills))
