"""Private server-pool event simulator."""
from collections import deque
import heapq
import re
import sys

def main(args):
    cap = None; positional = []; i = 0
    while i < len(args):
        a = args[i]; i += 1
        if a == '-q':
            if i == len(args) or not re.fullmatch('[0-9]{1,7}',args[i]):
                return 2
            cap = int(args[i]); i += 1
        elif a.startswith('-'):
            return 2
        else:
            positional.append(a)
    if len(positional) != 1 or not re.fullmatch('[0-9]{1,4}', positional[0]) or not 1 <= int(positional[0]) <= 1000:
        return 2
    n = int(positional[0]); trace = []; ids = set(); prev = 0
    for raw in sys.stdin.buffer:
        line = raw.decode('ascii').removesuffix('\n').removesuffix('\r')
        if not line.strip(' '):
            continue
        m = re.fullmatch(r'([A-Za-z0-9_-]{1,16}) ([0-9]{1,12}) ([0-9]{1,9})',line)
        if not m or int(m[3]) == 0 or int(m[2]) < prev or m[1] in ids:
            return 1
        ident,t,d = m[1],int(m[2]),int(m[3]); prev = t; ids.add(ident); trace.append((ident,t,d))
    waiting = deque(); active = []; idle = list(range(1,n+1)); heapq.heapify(idle)
    busy = [0]*(n+1); counts = [0]*(n+1); served = rejected = max_wait = total_wait = makespan = 0
    def start(request,k,t):
        nonlocal served,max_wait,total_wait
        ident,arrival,duration = request; wait = t-arrival
        print(f'{t} start {ident} s{k} wait={wait}')
        heapq.heappush(active,(t+duration,k,ident)); busy[k] += duration; counts[k] += 1
        served += 1; max_wait = max(max_wait,wait); total_wait += wait
    def complete_until(limit):
        nonlocal makespan
        while active and (limit is None or active[0][0] <= limit):
            t,k,ident = heapq.heappop(active); makespan = t
            print(f'{t} done {ident} s{k}')
            if waiting:
                start(waiting.popleft(),k,t)
            else:
                heapq.heappush(idle,k)
    for request in trace:
        ident,t,d = request; complete_until(t)
        if idle:
            start(request,heapq.heappop(idle),t)
        elif cap is None or len(waiting) < cap:
            waiting.append(request)
        else:
            print(f'{t} reject {ident}'); rejected += 1
    complete_until(None)
    print(f'served={served} rejected={rejected} max_wait={max_wait} total_wait={total_wait} makespan={makespan}')
    for k in range(1,n+1):
        print(f's{k} busy={busy[k]} served={counts[k]}')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
