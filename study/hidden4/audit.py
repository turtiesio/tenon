"""Audit only frozen specs and hidden4 artifacts; never run a reference."""
import ast
from collections import Counter
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parent
TASKS = ['01-hexdump','02-uniqx','03-icalc','04-timesheet','05-runoff','06-mdtoc','07-parking','08-pubsub','09-shorten','10-elevator']
NAME = re.compile(r'[a-z0-9][a-z0-9_-]*\Z')

def argv(p):
    data = (p/'cmd').read_bytes()
    assert not data or data.endswith(b'\n'), p
    return data.decode().split('\n')[:-1] if data else []

def input_lines(data):
    return data.split(b'\n')[:-1] if data.endswith(b'\n') else data.split(b'\n') if data else []

def check_limits(task, p, setup):
    data = (p/'stdin').read_bytes() if (p/'stdin').exists() else b''
    args = argv(p)
    n = len(input_lines(data))
    if task == '01-hexdump':
        assert len(data) <= 1048576, p
        for f in setup.rglob('*'):
            if f.is_file(): assert f.stat().st_size <= 1048576, f
    elif task in ('02-uniqx','06-mdtoc'):
        assert len(data) <= 1000000, p
    elif task == '03-icalc':
        i = 0
        while i < len(args):
            if args[i] == '-D': i += 2; continue
            text = args[i]
            assert len(text.encode()) <= 1000, p
            depth = peak = 0
            for c in text:
                if c == '(': depth += 1; peak = max(peak,depth)
                elif c == ')': depth -= 1
            assert peak <= 50, p
            i += 1
    elif task == '04-timesheet': assert n <= 100000, p
    elif task == '05-runoff':
        meaningful = [s.removesuffix(b'\r') for s in input_lines(data) if s.removesuffix(b'\r').strip(b' ') and not s.startswith(b'#')]
        assert max(0,len(meaningful)-1) <= 100000, p
    elif task in ('07-parking','08-pubsub'): assert n <= 100000, p
    elif task == '09-shorten': assert n <= 10000, p
    elif task == '10-elevator':
        assert len([s for s in input_lines(data) if s.removesuffix(b'\r').strip(b' ')]) <= 10000, p
    if task != '01-hexdump': assert data.isascii(), p


def main():
    cases = runs = kills = 0
    counts = Counter()
    for source in ROOT.glob('*.py'): ast.parse(source.read_text(), filename=str(source))
    assert sorted(p.stem for p in (ROOT/'ref').glob('*.py')) == TASKS
    for source in (ROOT/'ref').glob('*.py'):
        tree = ast.parse(source.read_text(), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(x.name in ('sys','os','re','collections') for x in node.names), source
            elif isinstance(node, ast.ImportFrom): assert node.module in ('collections',), source
    for task in TASKS:
        taskroot = ROOT/task/'cases'
        children = sorted(taskroot.iterdir())
        assert len(children) == 25 and all(p.is_dir() and NAME.fullmatch(p.name) for p in children), task
        spec = (ROOT.parent/'tasks4'/(task+'.md')).read_text()
        numbers = re.findall(r'^### Example (\d+):', spec, re.M)
        assert {p.name for p in children if p.name.startswith('example-')} == {'example-'+n for n in numbers}, task
        for p in children:
            cases += 1
            setup = p/'setup'
            if task == '09-shorten':
                for journal in setup.rglob('journal'):
                    assert len(input_lines(journal.read_bytes())) <= 100000, journal
            if (p/'steps').exists():
                assert not any((p/x).exists() for x in ['cmd','stdin','expected_stdout','expected_exit']), p
                steps = []
                for text in (p/'steps').read_text().splitlines():
                    m = re.fullmatch(r'([a-z0-9][a-z0-9_-]*)(?: kill-after=([1-9][0-9]*))?', text)
                    assert m, p
                    steps.append((p/m[1],int(m[2]) if m[2] else None))
                assert steps and len(set(s for s,_ in steps)) == len(steps), p
            else: steps = [(p,None)]
            for s,kill in steps:
                runs += 1; counts[task] += 1
                argv(s)
                assert (s/'expected_stdout').is_file(), s
                output = (s/'expected_stdout').read_bytes()
                if kill:
                    kills += 1
                    assert task in ('07-parking','08-pubsub','09-shorten'), s
                    assert not (s/'expected_exit').exists(), s
                    assert output.endswith(b'\n') and output.count(b'\n') == kill, s
                    incoming = input_lines((s/'stdin').read_bytes())
                    assert len(incoming) >= kill, s
                    assert (s/'stdin').read_bytes().count(b'\n') >= kill, s
                else:
                    status = int((s/'expected_exit').read_text())
                    assert status in ({0,2} if task in ('02-uniqx','04-timesheet','06-mdtoc','07-parking','08-pubsub') else {0,1,2}), s
                check_limits(task,s,setup)
    for task in TASKS: print(f'{task}: 25 cases; {counts[task]} runs; examples complete; input limits checked')
    print(f'AUDIT PASS: {cases} cases; {runs} process runs; {kills} kill steps')
if __name__ == '__main__': main()
