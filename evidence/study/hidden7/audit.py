"""Read-only audit of fixtures, frozen example coverage, and final validations."""
import ast
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('harness',ROOT.parent/'harness.py')
h=importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
assert h.ROOT!=ROOT

def need(ok,message):
    if not ok: raise AssertionError(message)

def lf(data):
    return data.split(b'\n')[:-1] if data.endswith(b'\n') else data.split(b'\n') if data else []

def manifest():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for task in sorted(ROOT.glob('[0-9][0-9]-*')) for p in sorted(task.rglob('*')) if p.is_file()}

def main():
    tasks=sorted(ROOT.glob('[0-9][0-9]-*')); need(len(tasks)==10,'ten tasks')
    total=runs=examples=multi=kills=book_multi=book_kills=0; known=set(); run_counts={}
    for task in tasks:
        cases=h.cases_in(task); need(len(cases)==25,task.name+' case count')
        source=(ROOT.parent/'tasks7'/(task.name+'.md')).read_text()
        nums=re.findall(r'^### Example ([0-9]+):',source,re.M)
        want={'example-'+n for n in nums}; got={p.name for p in cases if p.name.startswith('example-')}
        need(got==want,task.name+' example coverage'); examples+=len(nums)
        exits=set()
        for c in cases:
            total+=1; known.add((task.name,c.name))
            need(not any(p.is_symlink() for p in c.rglob('*')),'symlink')
            if (c/'steps').exists():
                multi+=1; book_multi+=task.name=='09-bookmarks'
                need(not any((c/f).exists() for f in ('cmd','stdin','expected_exit','expected_stdout')),'mixed case format')
                entries=[]
                for s in (c/'steps').read_text().splitlines():
                    m=re.fullmatch(r'([a-z0-9][a-z0-9_-]*)(?: kill-after=([1-9][0-9]*))?',s)
                    need(m is not None,'step grammar'); entries.append((c/m[1],int(m[2]) if m[2] else None))
            else: entries=[(c,None)]
            run_counts[(task.name,c.name)]=len(entries)
            for p,k in entries:
                runs+=1; args=h.arguments(p/'cmd')
                need((p/'cmd').read_bytes()==''.join(a+'\n' for a in args).encode(),'argv roundtrip')
                need(all('\x00' not in a for a in args),'NUL argument')
                output=(p/'expected_stdout').read_bytes()
                data=(p/'stdin').read_bytes() if (p/'stdin').exists() else b''
                if k:
                    kills+=1; book_kills+=task.name=='09-bookmarks'
                    need(not (p/'expected_exit').exists(),'kill exit file')
                    need(output.endswith(b'\n') and output.count(b'\n')==k,'kill stdout lines')
                    need(len(lf(data))>k and all(x.endswith(b'\n') for x in data.splitlines(keepends=True)[:k]),'kill needs complete lines and unsent suffix')
                else:
                    n=int((p/'expected_exit').read_text()); exits.add(n)
                    need(n in (0,1,2),'exit code')
                if task.name[:2] in ('06','07','08','09'): need(len(lf(data))<=10000,'command/line ceiling')
                if task.name[:2] in ('01','03','04'): need(len(lf(data))<=100000,'line ceiling')
                if task.name=='03-detab': need(all(len(s.decode('utf-8'))<=10000 for s in lf(output)),'expanded line ceiling')
                if task.name=='08-vfs':
                    for line in lf(data):
                        text=line.decode('ascii'); fields=text.split(' ',2) if text.startswith('WRITE ') else text.split(' ')
                        need(all(len(s)<=200 for s in fields[1:2] if s),'path ceiling')
                if task.name=='10-war': need(len(output)<1000000,'War output ceiling')
            setup=c/'setup'
            for p in setup.rglob('*') if setup.exists() else []:
                if not p.is_file(): continue
                if task.name=='05-reconcile': need(len(lf(p.read_bytes()))<=10000,'CSV line ceiling')
                if task.name=='09-bookmarks' and p.name=='journal': need(len(lf(p.read_bytes()))<=100000,'journal ceiling')
                if task.name=='09-bookmarks' and p.name=='snapshot': need(len(lf(p.read_bytes()))<=1001,'snapshot bookmark ceiling')
        required={0,2} if task.name[:2] in ('07','08') else {0,1,2}
        need(exits==required,task.name+' exit coverage')
    for p in [*sorted((ROOT/'ref').glob('*.py')),ROOT/'build_cases.py',ROOT/'run.py',ROOT/'silent.py',Path(__file__)]:
        tree=ast.parse(p.read_text(),filename=str(p)); compile(tree,str(p),'exec')
        for node in ast.walk(tree):
            modules=[a.name.split('.')[0] for a in node.names] if isinstance(node,ast.Import) else [node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else []
            need(all(m in sys.stdlib_module_names or m=='common' for m in modules),'non-stdlib import '+str(p))
    stats={}
    for label in ('reference','silent'):
        obj=json.loads((ROOT/(label+'-results.json')).read_text())
        need(obj['total']==total and len(obj['results'])==total,'result count')
        need({(r['task'],r['case']) for r in obj['results']}==known,'result identities')
        need(obj['passed']==sum(r['passed'] for r in obj['results']),'pass tally')
        for r in obj['results']:
            need(len(r['steps'])==run_counts[(r['task'],r['case'])],'result step count')
            if label=='reference': need(r['passed'],'reference failed: '+r['case'])
            else:
                need(all(not base64.b64decode(s['stdout_b64']) for s in r['steps']),'silent output')
                need(all(s['exit']==0 for s in r['steps']),'silent exit')
        stats[label]=obj['passed']
    need(stats['reference']==total,'reference not green')
    recorded={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (ROOT/'fixture-manifest.sha256').read_text().splitlines()}
    need(recorded==manifest(),'fixture manifest mismatch')
    print(f'AUDIT PASS: {total} cases; {runs} process runs; {examples} numbered examples; {multi} multi-run cases; {kills} SIGKILL steps; {len(manifest())} fixture files')
    print(f'Bookmarks: {book_multi} multi-run cases; {book_kills} SIGKILL steps')
    print(f'References {stats["reference"]}/{total}; silent control fails {total-stats["silent"]}/{total}')
if __name__=='__main__': main()
