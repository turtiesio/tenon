"""Private spec-only reference."""
import re
import sys

def main(a):
    files, flags = [], set()
    for x in a:
        if x in ('-r','-u','--no-pre'): flags.add(x)
        elif x.startswith('-'): return 2
        else: files.append(x)
    if len(files)>1: return 2
    try: data = open(files[0],encoding='utf-8',newline='').read() if files else sys.stdin.read()
    except OSError: return 1
    num = r'(?:0|[1-9][0-9]{0,8})'
    pattern = re.compile('('+num+r')\.('+num+r')\.('+num+r')(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?')
    versions, rc = [], 0
    for s in data.split('\n'):
        if s.endswith('\r'): s=s[:-1]
        s=s.strip(' \t')
        if not s: continue
        m = pattern.fullmatch(s)
        if not m:
            rc=1; continue
        major,minor,patch,pre,build=m.groups()
        ids=pre.split('.') if pre else []
        if (pre is not None and any(not x or (x.isdigit() and not re.fullmatch(num,x)) for x in ids)) or (build is not None and any(not x for x in build.split('.'))):
            rc=1; continue
        key=(int(major),int(minor),int(patch),int(pre is None),tuple((0,int(x)) if x.isdigit() else (1,x) for x in ids))
        versions.append((key,s,pre))
    versions.sort(key=lambda x:x[0])
    if '--no-pre' in flags: versions=[v for v in versions if v[2] is None]
    if '-u' in flags:
        unique=[]
        for v in versions:
            if not unique or unique[-1][0]!=v[0]: unique.append(v)
        versions=unique
    if '-r' in flags: versions.reverse()
    for _,s,_ in versions: print(s)
    return rc
sys.exit(main(sys.argv[1:]))
