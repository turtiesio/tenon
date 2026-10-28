"""Private cachesim reference, independent per-set ordered dictionaries."""
from collections import OrderedDict
import re
import sys

class Cache:
    def __init__(self,sets,ways):
        self.sets=[OrderedDict() for _ in range(sets)]; self.ways=ways
        self.hits=self.misses=self.writebacks=0
    def group(self,b): return self.sets[b%len(self.sets)]
    def lookup(self,b,write=False):
        group=self.group(b)
        if b not in group: self.misses+=1; return False
        self.hits+=1; group[b]=group[b] or write; group.move_to_end(b); return True
    def install(self,b,dirty):
        group=self.group(b); victim=None
        if len(group)==self.ways: victim=group.popitem(last=False)
        group[b]=dirty
        return victim
    def memory_victim(self,victim):
        if victim is not None and victim[1]: self.writebacks+=1

def main():
    block=16; geometries={'-1':(4,2),'-2':(16,4)}
    args=iter(sys.argv[1:])
    for op in args:
        if op not in ('-b','-1','-2'): return 2
        value=next(args,'')
        if op=='-b':
            if not re.fullmatch('[0-9]{1,4}',value): return 2
            n=int(value)
            if not 1<=n<=4096 or n&(n-1): return 2
            block=n
        else:
            m=re.fullmatch(r'([0-9]{1,4}):([0-9]{1,2})',value)
            if not m or not 1<=int(m[1])<=4096 or not 1<=int(m[2])<=64: return 2
            geometries[op]=int(m[1]),int(m[2])
    trace=[]
    for raw in sys.stdin.buffer.read().split(b'\n'):
        if raw.endswith(b'\r'): raw=raw[:-1]
        if not raw.strip(b' '): continue
        if not re.fullmatch(rb'[RW] 0x[0-9a-fA-F]{1,8}',raw): return 1
        s=raw.decode('ascii'); trace.append((s,s[0]=='W',int(s[4:],16)//block))
    l1,l2=Cache(*geometries['-1']),Cache(*geometries['-2'])
    output=[]
    for text,write,b in trace:
        if l1.lookup(b,write): result='L1'
        else:
            if l2.lookup(b): result='L2'
            else:
                result='MEM'; l2.memory_victim(l2.install(b,False))
            victim=l1.install(b,write)
            if victim is not None and victim[1]:
                l1.writebacks+=1; v=victim[0]; group=l2.group(v)
                if v in group: group[v]=True; group.move_to_end(v)
                else: l2.memory_victim(l2.install(v,True))
        output.append(text+' '+result+'\n')
    for name,cache in (('L1',l1),('L2',l2)):
        output.append(f'{name} hits={cache.hits} misses={cache.misses} writebacks={cache.writebacks}\n')
    sys.stdout.write(''.join(output)); return 0

if __name__ == '__main__':
    status=main()
    if status: print('cachesim: error',file=sys.stderr)
    sys.exit(status)
