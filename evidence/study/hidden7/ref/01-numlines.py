import sys
from common import match, fail
opts = {'-b':'t','-w':'6','-s':'\t','-v':'1','-i':'1','-f':'rn'}
paths=[]
a=sys.argv[1:]; i=0
while i<len(a):
    arg=a[i]; i+=1
    if arg in opts:
        if i==len(a): fail(2)
        val=a[i]; i+=1
        valid = (arg=='-s' or arg=='-b' and val in ('a','t','n') or
                 arg=='-f' and val in ('ln','rn','rz') or
                 arg=='-w' and match('[1-9][0-9]?',val) and int(val)<=20 or
                 arg in ('-v','-i') and match('-?[0-9]{1,9}',val))
        if not valid: fail(2)
        opts[arg]=val
    elif arg.startswith('-'): fail(2)
    else: paths.append(arg)
if len(paths)>1: fail(2)
try: data=open(paths[0],'rb').read() if paths else sys.stdin.buffer.read()
except OSError: fail(1)
rows=data.split(b'\n')
if rows[-1]==b'': rows.pop()
n=int(opts['-v']); step=int(opts['-i']); w=int(opts['-w']); out=[]
for row in rows:
    if opts['-b']=='a' or opts['-b']=='t' and row:
        field=str(n)
        if opts['-f']=='ln': field=field.ljust(w)
        elif opts['-f']=='rn': field=field.rjust(w)
        else: field=field.zfill(w)
        out.append(field.encode()+opts['-s'].encode()+row+b'\n'); n+=step
    else: out.append(row+b'\n')
sys.stdout.buffer.write(b''.join(out))
