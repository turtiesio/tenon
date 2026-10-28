"""Check fixture structure, byte contracts and reported spec limits."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
NAME = re.compile(r'[a-z0-9][a-z0-9_-]*\Z')

def check():
    cases = runs = kills = 0
    for task in sorted(ROOT.glob('[0-9][0-9]-*')):
        entries = sorted((task/'cases').iterdir())
        assert 15 <= len(entries) <= 25, task
        for case in entries:
            assert case.is_dir() and NAME.fullmatch(case.name), case
            cases += 1
            if (case/'steps').exists():
                assert not any((case/p).exists() for p in ('cmd','stdin','expected_stdout','expected_exit')), case
                steps = []
                for row in (case/'steps').read_text().splitlines():
                    m = re.fullmatch(r'([a-z0-9][a-z0-9_-]*)(?: kill-after=([1-9][0-9]*))?',row)
                    assert m, (case,row)
                    steps.append((case/m[1],int(m[2]) if m[2] else None))
            else:
                steps = [(case,None)]
            for step,kill in steps:
                runs += 1
                cmd = (step/'cmd').read_bytes()
                assert not cmd or cmd.endswith(b'\n'), step
                cmd.decode('utf-8')
                out = (step/'expected_stdout').read_bytes()
                if kill:
                    kills += 1
                    assert not (step/'expected_exit').exists(), step
                    assert out.endswith(b'\n') and out.count(b'\n') == kill, step
                    assert (step/'stdin').read_bytes().count(b'\n') >= kill, step
                    assert task.name[:2] in ('07','08','09'), step
                else:
                    code = int((step/'expected_exit').read_text())
                    assert code in (0,1,2,3), step
                if task.name[:2] in ('04','06','07','08','09','10') and (step/'stdin').exists():
                    data = (step/'stdin').read_bytes()
                    num = data.count(b'\n') + int(bool(data) and not data.endswith(b'\n'))
                    limit = {'04':200000,'06':200000,'07':100000,'08':100000,'09':10000,'10':100000}[task.name[:2]]
                    assert num <= limit, step
                if task.name[:2] == '04' and (step/'stdin').exists():
                    assert max(map(len,(step/'stdin').read_bytes().split(b'\n')),default=0) <= 4000, step
            setup = case/'setup'
            if setup.exists():
                for file in setup.rglob('*'):
                    assert not file.is_symlink(), file
                    if file.is_file() and task.name[:2] == '01':
                        data = file.read_bytes()
                        assert len(data) <= 1000000 and max(map(len,data.split(b'\n')),default=0) <= 1000,file
                    if file.is_file() and task.name[:2] == '02':
                        data = file.read_bytes()
                        assert data.count(b'\n')+int(bool(data) and not data.endswith(b'\n')) <= 2000,file
                        assert max(map(len,data.split(b'\n')),default=0) <= 1000,file
    print(f'AUDIT PASS: {cases} cases; {runs} process runs; {kills} kill steps')

if __name__ == '__main__':
    check()
