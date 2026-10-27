import heapq
import re
import sys
from collections import deque

def main():
    args = sys.argv[1:]
    capacity = None
    positional = []
    i = 0
    while i < len(args):
        if args[i] == '-q':
            if i + 1 == len(args) or not re.fullmatch(r'[0-9]{1,7}', args[i + 1]):
                return 2
            capacity = int(args[i + 1])
            i += 2
        elif args[i].startswith('-'):
            return 2
        else:
            positional.append(args[i])
            i += 1
    if len(positional) != 1 or not re.fullmatch(r'[0-9]{1,4}', positional[0]) or not 1 <= int(positional[0]) <= 1000:
        return 2
    servers = int(positional[0])
    requests = []
    seen = set()
    last = -1
    pattern = re.compile(r'([A-Za-z0-9_-]{1,16}) ([0-9]{1,12}) ([0-9]{1,9})')
    for line in sys.stdin:
        line = line.removesuffix('\n').removesuffix('\r')
        if not line.strip(' '):
            continue
        match = pattern.fullmatch(line)
        if not match or match[1] in seen or int(match[2]) < last or int(match[3]) == 0:
            return 1
        ident, arrival, duration = match[1], int(match[2]), int(match[3])
        requests.append((ident, arrival, duration))
        seen.add(ident)
        last = arrival
    idle = list(range(1, servers + 1))
    events = []
    queue = deque()
    busy = [0] * (servers + 1)
    counts = [0] * (servers + 1)
    served = rejected = max_wait = total_wait = makespan = 0
    def start(request, server, time):
        nonlocal served, max_wait, total_wait
        ident, arrival, duration = request
        wait = time - arrival
        print(f'{time} start {ident} s{server} wait={wait}')
        served += 1
        max_wait = max(max_wait, wait)
        total_wait += wait
        busy[server] += duration
        counts[server] += 1
        heapq.heappush(events, (time + duration, server, ident))
    index = 0
    while index < len(requests) or events:
        arrival = requests[index][1] if index < len(requests) else None
        if events and (arrival is None or events[0][0] <= arrival):
            time, server, ident = heapq.heappop(events)
            print(f'{time} done {ident} s{server}')
            makespan = time
            if queue:
                start(queue.popleft(), server, time)
            else:
                heapq.heappush(idle, server)
        else:
            request = requests[index]
            index += 1
            if idle:
                start(request, heapq.heappop(idle), arrival)
            elif capacity is None or len(queue) < capacity:
                queue.append(request)
            else:
                rejected += 1
                print(f'{arrival} reject {request[0]}')
    print(f'served={served} rejected={rejected} max_wait={max_wait} total_wait={total_wait} makespan={makespan}')
    for server in range(1, servers + 1):
        print(f's{server} busy={busy[server]} served={counts[server]}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
