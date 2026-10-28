"""Private buildorder reference, iterative Kahn ordering and levels."""
import heapq
import re
import sys

def main():
    levels = False; targets = []
    a = iter(sys.argv[1:])
    for x in a:
        if x=='-l': levels=True
        elif x=='-t':
            v = next(a,None)
            if v is None: return 2
            targets.append(v)
        else: return 2
    graph = {}; valid = r'[A-Za-z0-9_./-]+'
    for raw in sys.stdin.buffer.read().split(b'\n'):
        if raw.endswith(b'\r'): raw=raw[:-1]
        s=raw.decode('ascii')
        if not s.strip(' ') or s.lstrip(' ').startswith('#'): continue
        if ':' not in s: return 3
        head,tail=s.split(':',1); head=head.strip(' ')
        deps=[x for x in tail.split(' ') if x]
        if not re.fullmatch(valid,head) or any(not re.fullmatch(valid,d) for d in deps): return 3
        graph.setdefault(head,set()).update(deps)
        for d in deps: graph.setdefault(d,set())
    if any(t not in graph for t in targets): return 3
    selected = set()
    stack = targets[:] if targets else list(graph)
    while stack:
        n=stack.pop()
        if n in selected: continue
        selected.add(n); stack.extend(graph[n])
    remaining={n:len(graph[n]) for n in selected}; reverse={n:[] for n in selected}
    for n in selected:
        for d in graph[n]: reverse[d].append(n)
    ready=[n for n in selected if not remaining[n]]; heapq.heapify(ready)
    order=[]; height={}
    while ready:
        n=heapq.heappop(ready); order.append(n)
        height[n]=1+max((height[d] for d in graph[n]),default=-1)
        for dependent in reverse[n]:
            remaining[dependent]-=1
            if remaining[dependent]==0: heapq.heappush(ready,dependent)
    if len(order)!=len(selected):
        print('CYCLE '+' '.join(sorted(selected-set(order)))); return 1
    if levels:
        rows={}
        for n in order: rows.setdefault(height[n],[]).append(n)
        for h in sorted(rows): print(str(h)+': '+' '.join(sorted(rows[h])))
    else:
        for n in order: print(n)
    return 0

if __name__ == '__main__':
    status=main()
    if status in (2,3): print('buildorder: error',file=sys.stderr)
    sys.exit(status)
