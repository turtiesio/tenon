"""Private sheet reference with parsed terms and iterative dependency evaluation."""
import re
import sys
CELL=r'[A-Z][1-9][0-9]?'
TERM=re.compile(r'(SUM\(('+CELL+r'):('+CELL+r')\)|'+CELL+r'|[0-9]{1,9})')

def rectangle(a,b):
    return [chr(c)+str(r) for c in range(min(ord(a[0]),ord(b[0])),max(ord(a[0]),ord(b[0]))+1)
            for r in range(min(int(a[1:]),int(b[1:])),max(int(a[1:]),int(b[1:]))+1)]

def parse(s):
    if re.fullmatch(r'-?[0-9]{1,9}',s): return [('number',int(s))],set()
    if not s.startswith('='): raise ValueError('contents')
    i=1; terms=[]; refs=set(); sign=1
    if i<len(s) and s[i]=='-': sign=-1; i+=1
    while True:
        m=TERM.match(s,i)
        if not m: raise ValueError('term')
        token=m[1]; i=m.end()
        if token.startswith('SUM('):
            cells=rectangle(m[2],m[3]); refs.update(cells); terms.append(('cells',sign,cells))
        elif re.fullmatch(CELL,token): refs.add(token); terms.append(('cells',sign,[token]))
        else: terms.append(('number',sign*int(token)))
        if i==len(s): return terms,refs
        if s[i] not in '+-': raise ValueError('operator')
        sign=1 if s[i]=='+' else -1; i+=1

def main():
    if len(sys.argv)!=1: return 2
    sheet={}
    def creates_cycle(cell,refs):
        todo=list(refs); visited=set()
        while todo:
            n=todo.pop()
            if n==cell: return True
            if n in visited: continue
            visited.add(n)
            if n in sheet: todo.extend(sheet[n][2])
        return False
    def evaluate(cell):
        values={}; stack=[(cell,False)]
        while stack:
            n,ready=stack.pop()
            if n in values: continue
            if n not in sheet: values[n]=0; continue
            _,terms,refs=sheet[n]
            if not ready:
                stack.append((n,True)); stack.extend((d,False) for d in refs if d not in values)
            elif any(values[d] is None for d in refs): values[n]=None
            else:
                value=sum(t[1] if t[0]=='number' else t[1]*sum(values[c] for c in t[2]) for t in terms)
                values[n]=value if abs(value)<=10**12 else None
        return values[cell]
    for raw in sys.stdin.buffer:
        s=raw.removesuffix(b'\n').removesuffix(b'\r').decode('ascii')
        tokens=s.split(' '); response='ERR bad command'
        if len(tokens)==3 and tokens[0]=='SET' and re.fullmatch(CELL,tokens[1]):
            cell,contents=tokens[1:]
            try: terms,refs=parse(contents)
            except ValueError: pass
            else:
                if creates_cycle(cell,refs): response='ERR cycle'
                else: sheet[cell]=(contents,terms,refs); response='OK'
        elif len(tokens)==2 and re.fullmatch(CELL,tokens[1]):
            op,cell=tokens
            if op=='CLEAR': sheet.pop(cell,None); response='OK'
            elif op=='SHOW': response=sheet[cell][0] if cell in sheet else 'EMPTY'
            elif op=='GET':
                value=evaluate(cell); response='ERR overflow' if value is None else str(value)
        print(response,flush=True)
    return 0

if __name__ == '__main__':
    status=main()
    if status: print('sheet: usage',file=sys.stderr)
    sys.exit(status)
