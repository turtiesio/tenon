"""Audit the fixture protocol, frozen example names, Python imports and limits.

This audits fixture data directly and never invokes task references.
"""
import ast
import hashlib
import re
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
SPECS = ROOT.parent/'tasks5'
NAME = re.compile(r'[a-z0-9][a-z0-9_-]*\Z')

def read_lines(raw):
    text = raw.decode('utf-8')
    if not text: return []
    parts = text.split('\n')
    if parts[-1] == '': parts.pop()
    return [p.removesuffix('\r') for p in parts]

def argv(path):
    b = path.read_bytes()
    assert not b or b.endswith(b'\n'), path
    assert b'\0' not in b, path
    return b.decode('utf-8').split('\n')[:-1] if b else []

def check_limits(task,args,data,setup):
    number = int(task[:2])
    rows = read_lines(data)
    if number == 1:
        # Derive the sequence length from argv only to enforce the input domain.
        values,limit = [],100000
        i = 0
        valid = True
        while i < len(args):
            a = args[i]
            if a in ('-s','-n'):
                i += 1
                if i >= len(args): valid = False; break
                if a == '-n':
                    if not re.fullmatch(r'[0-9]{1,9}',args[i]): valid = False; break
                    limit = int(args[i])
            elif a != '-w':
                if not re.fullmatch(r'-?[0-9]{1,18}',a): valid = False; break
                values.append(int(a))
            i += 1
        if valid and len(values) in (2,3):
            first,step,last = (values[0],1,values[1]) if len(values)==2 else values
            if step:
                count = min(limit,max(0,(last-first)//step+1)) if (last-first)*step >= 0 else 0
                assert count <= 100000
                assert abs(first) <= 10**18 and abs(last) <= 10**18
    elif number == 2:
        assert len(data) <= 1000000 and all(b < 128 for b in data)
        assert all(all(ord(c)<128 for c in a) for a in args)
    elif number == 3:
        assert len(rows) <= 10000
        sep = None
        for i,a in enumerate(args[:-1]):
            if a == '-s': sep = args[i+1]
        for row in rows:
            fields = re.findall(r'[^ \t]+',row) if sep is None else row.split(sep) if len(sep)==1 else []
            assert len(fields) <= 100
    elif number == 4:
        assert len(rows) <= 10000
        people = set()
        for row in rows:
            t = re.findall(r'[^ \t]+',row)
            if t and t[0] == 'expense' and len(t)>=4:
                assert len(t)-3 <= 50
                people.update([t[1]]+t[3:])
            if t and t[0]=='transfer' and len(t)==4: people.update(t[1:3])
        assert len(people) <= 1000
    elif number == 5:
        assert sum(bool(re.fullmatch(r'[0-9]{1,9}',x)) for x in rows) <= 10000
        # Valid timestamp spellings remain below 100 h after positive shifts.
        if len(args)==1 and re.fullmatch(r'[+-]?[0-9]{1,9}',args[0]):
            offset = int(args[0])
            for row in rows:
                for h,m,s,ms in re.findall(r'([0-9]{2}):([0-5][0-9]):([0-5][0-9]),([0-9]{3})',row):
                    assert ((int(h)*60+int(m))*60+int(s))*1000+int(ms)+offset < 360000000
    elif number == 6 and setup.exists():
        for p in setup.rglob('*'):
            if p.is_file():
                ls = read_lines(p.read_bytes())
                records = [l for l in ls if l and not l.startswith('#')]
                # All large book fixtures are 4-field records; loans have 5.
                if len(records)>10000: assert all(l.count('|')==4 for l in records)
                assert len(records) <= 100000
    elif number == 7:
        assert len(rows) <= 20000
        totals = {}
        for row in rows:
            m = re.fullmatch(r'SCORE ([a-z][a-z0-9_]{0,15}) (-?[0-9]{1,6})',row)
            if m: totals[m[1]] = totals.get(m[1],0)+int(m[2])
            m = re.fullmatch(r'REMOVE ([a-z][a-z0-9_]{0,15})',row)
            if m: totals.pop(m[1],None)
            assert len(totals) <= 1000 and all(abs(x)<=10**9 for x in totals.values())
    elif number == 8: assert len(rows) <= 100000
    elif number == 9:
        assert len(rows) <= 10000
        assert len({r.split(' ')[1] for r in rows if r.startswith('CREATE ') and len(r.split(' '))>=4}) <= 1000
        for p in setup.rglob('polls.log') if setup.exists() else []:
            if p.is_file():
                planted = p.read_bytes()
                assert planted.count(b'\n') <= 100000
                assert sum(r.startswith(b'CREATE ') for r in planted.split(b'\n')) <= 1000
    elif number == 10:
        split = rows.index('') if '' in rows else len(rows)
        grid = rows[:split]
        assert len(grid) <= 50 and all(len(r)<=50 for r in grid)
        assert all(len(p.split(':',1)[-1])<=100 for p in rows[split+1:])

cases = runs = kills = 0
allowed_exits = {1:{0,2},2:{0,2},3:{0,2},4:{0,1,2},5:{0,1,2},6:{0,1,2},7:{0,2},8:{0,2},9:{0,1,2},10:{0,1,2}}
for spec in sorted(SPECS.glob('*.md')):
    task = ROOT/spec.stem
    dirs = sorted((task/'cases').iterdir())
    assert len(dirs)==25, (task,len(dirs))
    examples = re.findall(r'^### Example ([0-9]+):',spec.read_text(),re.M)
    assert {p.name for p in dirs if p.name.startswith('example-')} == {'example-'+n for n in examples}
    seen_exits = set()
    for case in dirs:
        assert case.is_dir() and NAME.fullmatch(case.name)
        cases += 1
        if (case/'steps').exists():
            assert not any((case/f).exists() for f in ['cmd','stdin','expected_stdout','expected_exit'])
            steps = []
            for line in (case/'steps').read_text().splitlines():
                m = re.fullmatch(r'([a-z0-9][a-z0-9_-]*)(?: kill-after=([1-9][0-9]*))?',line)
                assert m, (case,line)
                steps.append((case/m[1],int(m[2]) if m[2] else None))
            assert steps
        else: steps = [(case,None)]
        for step,kill in steps:
            args = argv(step/'cmd')
            data = (step/'stdin').read_bytes() if (step/'stdin').exists() else b''
            expected = (step/'expected_stdout').read_bytes()
            runs += 1
            if kill:
                kills += 1
                assert not (step/'expected_exit').exists()
                assert expected.endswith(b'\n') and expected.count(b'\n')==kill
                assert data.count(b'\n')>=kill
                assert int(spec.stem[:2]) in (7,8,9)
            else:
                code = int((step/'expected_exit').read_text())
                assert code in allowed_exits[int(spec.stem[:2])]
                seen_exits.add(code)
            check_limits(spec.stem,args,data,case/'setup')
    assert seen_exits == allowed_exits[int(spec.stem[:2])], (spec.stem,seen_exits)
    print(f'{spec.stem}: 25 cases; examples 1–{len(examples)}; exit codes {sorted(seen_exits)}')
# Independently inspect the explicitly specified draw: gravity rows, parity,
# player counts and the absence of any winning segment. No reference is used.
draw = ROOT/'08-connect4/cases/full-board-draw'
commands = read_lines((draw/'stdin').read_bytes())[:42]
answers = read_lines((draw/'expected_stdout').read_bytes())[:42]
board = [['.']*7 for _ in range(6)]
for i,(command,answer) in enumerate(zip(commands,answers)):
    c = int(command[-1])-1
    r = next(y for y in range(6) if board[y][c]=='.')
    player = 'XO'[i%2]
    assert answer == f'PLAYED {player} {r+1}'+(' DRAW' if i==41 else '')
    board[r][c] = player
for y in range(6):
    for x in range(7):
        for dx,dy in [(1,0),(0,1),(1,1),(1,-1)]:
            cells = [(x+k*dx,y+k*dy) for k in range(4)]
            if all(0<=xx<7 and 0<=yy<6 for xx,yy in cells):
                assert len({board[yy][xx] for xx,yy in cells}) > 1
print('Full-board draw: 42 legal alternating drops; 21 discs each; no four-in-a-row')
for source in ROOT.rglob('*.py'):
    tree = ast.parse(source.read_text(),filename=str(source))
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): modules = [a.name.split('.')[0] for a in node.names]
        elif isinstance(node,ast.ImportFrom): modules = [node.module.split('.')[0]] if node.module else []
        else: continue
        assert all(m in sys.stdlib_module_names or m == 'common' for m in modules),(source,modules)
fixtures = [(p.relative_to(ROOT).as_posix(),hashlib.sha256(p.read_bytes()).hexdigest()) for task in ROOT.glob('[0-9][0-9]-*') for p in task.rglob('*') if p.is_file()]
put = ROOT/'fixture-manifest.sha256'
put.write_text(''.join(f'{digest}  {name}\n' for name,digest in sorted(fixtures)))
print(f'AUDIT PASS: {cases} cases; {runs} process runs; {kills} kill steps; {len(fixtures)} fixture files')
