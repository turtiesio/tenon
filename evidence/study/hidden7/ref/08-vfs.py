import sys
from common import match, fail, incoming, say
if sys.argv[1:]: fail(2)
class Error(Exception): pass
class Node:
    def __init__(self,name='',parent=None,text=None):
        self.name=name; self.parent=parent; self.text=text; self.children={}
root=Node(); root.parent=root; cwd=root

def validpath(p):
    return p=='/' or bool(p) and all(match('[A-Za-z0-9._-]{1,32}',c) for c in p.removeprefix('/').split('/'))

def resolve(p):
    node=root if p.startswith('/') else cwd
    if p=='/': return node,None,None
    parts=p.removeprefix('/').split('/')
    for i,c in enumerate(parts):
        if node.text is not None: raise Error('not a directory')
        if c=='.': continue
        if c=='..': node=node.parent; continue
        if c not in node.children:
            if i==len(parts)-1: return None,node,c
            raise Error('not found')
        node=node.children[c]
    return node,None,None

def ancestor(a,b):
    while True:
        if a is b: return True
        if b is root: return False
        b=b.parent

def usage(node):
    if node.text is not None: return len(node.text),1,0
    size=files=dirs=0
    for c in node.children.values():
        b,f,d=usage(c); size+=b; files+=f; dirs+=d+(c.text is None)
    return size,files,dirs

def command(s):
    global cwd
    t=s.split(' '); op=t[0]
    if op=='WRITE':
        t=s.split(' ',2)
        if len(t)!=3 or not validpath(t[1]) or not 1<=len(t[2])<=100 or any(not 32<=ord(c)<=126 for c in t[2]): return 'ERR bad command'
    else:
        counts={'PWD':(1,),'LS':(1,2),'DU':(1,2),'CD':(2,),'MKDIR':(2,),'CAT':(2,),'RM':(2,),'MV':(3,)}
        if op not in counts or len(t) not in counts[op] or any(not validpath(p) for p in t[1:]): return 'ERR bad command'
    if op=='PWD':
        parts=[]; node=cwd
        while node is not root: parts.append(node.name); node=node.parent
        return '/'+ '/'.join(reversed(parts))
    node,parent,name=resolve(t[1]) if len(t)>1 else (cwd,None,None)
    if op=='MV':
        if node is None: raise Error('not found')
        if node is root: raise Error('invalid')
        dest,dp,dn=resolve(t[2])
        if dest is not None:
            if dest.text is not None: raise Error('exists')
            dp,dn=dest,node.name
            if dn in dp.children: raise Error('exists')
        if node.text is None and ancestor(node,dp): raise Error('invalid')
        del node.parent.children[node.name]; node.parent=dp; node.name=dn; dp.children[dn]=node
        return 'OK'
    if op=='MKDIR':
        if node is not None: raise Error('exists')
        parent.children[name]=Node(name,parent); return 'OK'
    if op=='WRITE':
        if node is None: parent.children[name]=Node(name,parent,t[2])
        elif node.text is None: raise Error('is a directory')
        else: node.text=t[2]
        return 'OK'
    if node is None: raise Error('not found')
    if op=='CD':
        if node.text is not None: raise Error('not a directory')
        cwd=node; return 'OK'
    if op=='CAT':
        if node.text is None: raise Error('is a directory')
        return node.text
    if op=='LS':
        if node.text is not None: return node.name
        return ' '.join(n+('/' if node.children[n].text is None else '') for n in sorted(node.children)) or '-'
    if op=='DU': return '%d %d %d'%usage(node)
    if op=='RM':
        if ancestor(node,cwd): raise Error('busy')
        if node.text is None and node.children: raise Error('not empty')
        del node.parent.children[node.name]; return 'OK'
for s in incoming():
    try: say(command(s))
    except Error as e: say('ERR '+str(e))
