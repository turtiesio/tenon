import sys
from common import match, fail
args=sys.argv[1:]; files=[]; stops=[8]; leading=False; i=0
while i<len(args):
    arg=args[i]; i+=1
    if arg=='-i': leading=True
    elif arg=='-t':
        if i==len(args) or not match('[1-9][0-9]{0,3}(,[1-9][0-9]{0,3})*',args[i]): fail(2)
        stops=list(map(int,args[i].split(','))); i+=1
        if any(x>=y for x,y in zip(stops,stops[1:])): fail(2)
    elif arg.startswith('-'): fail(2)
    else: files.append(arg)
code=0; chunks=[]
if not files: chunks=[sys.stdin.buffer.read()]
else:
    for path in files:
        try: chunks.append(open(path,'rb').read())
        except OSError: print('unreadable file',file=sys.stderr); code=1
text=b''.join(chunks).decode('utf-8'); col=0; indent=True; out=[]
for c in text:
    if c=='\n': out.append(c); col=0; indent=True
    elif c=='\t' and (not leading or indent):
        n=stops[0]-col%stops[0] if len(stops)==1 else next((s-col for s in stops if s>col),1)
        out.append(' '*n); col+=n
    else:
        out.append(c); col+=1
        if c not in ' \t': indent=False
sys.stdout.buffer.write(''.join(out).encode()); sys.exit(code)
