"""servsim: discrete-event simulation of a server pool with a FIFO queue."""
import heapq
import re
import sys
from collections import deque

SERVERS_RE = re.compile(r"[0-9]{1,4}")
CAP_RE = re.compile(r"[0-9]{1,7}")
REQUEST_RE = re.compile(r"([A-Za-z0-9_-]{1,16}) ([0-9]{1,12}) ([0-9]{1,9})")


class UsageError(Exception):
    pass


class TraceError(Exception):
    pass


class Request:
    def __init__(self, rid, arrival, duration):
        self.id = rid
        self.arrival = arrival
        self.duration = duration


def parse_args(argv):
    cap = None
    positional = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-q":
            if i + 1 >= len(argv) or not CAP_RE.fullmatch(argv[i + 1]):
                raise UsageError("-q needs a capacity 0..9999999")
            cap = int(argv[i + 1])
            i += 2
            continue
        if arg.startswith("-"):
            raise UsageError(f"unknown option {arg}")
        positional.append(arg)
        i += 1
    if len(positional) != 1:
        raise UsageError("expected exactly one server count")
    if not SERVERS_RE.fullmatch(positional[0]) or not 1 <= int(positional[0]) <= 1000:
        raise UsageError(f"bad server count {positional[0]!r}")
    return int(positional[0]), cap


def read_trace(data):
    lines = data.split("\n")
    if lines[-1] == "":
        lines.pop()
    requests = []
    seen = set()
    last_arrival = 0
    for lineno, line in enumerate(lines, 1):
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip(" ") == "":
            continue
        m = REQUEST_RE.fullmatch(line)
        if not m or int(m.group(3)) < 1:
            raise TraceError(f"line {lineno}: malformed request")
        rid, arrival, duration = m.group(1), int(m.group(2)), int(m.group(3))
        if rid in seen:
            raise TraceError(f"line {lineno}: duplicate id {rid}")
        if arrival < last_arrival:
            raise TraceError(f"line {lineno}: arrival goes backwards")
        seen.add(rid)
        last_arrival = arrival
        requests.append(Request(rid, arrival, duration))
    return requests


def simulate(requests, n_servers, cap):
    out = []
    idle = list(range(1, n_servers + 1))  # min-heap of idle server numbers
    running = []  # min-heap of (finish time, server number)
    current = {}  # server number -> request it is running
    busy = [0] * (n_servers + 1)
    served_by = [0] * (n_servers + 1)
    queue = deque()
    served = rejected = max_wait = total_wait = makespan = 0

    def start(t, request, server):
        nonlocal served, max_wait, total_wait
        wait = t - request.arrival
        out.append(f"{t} start {request.id} s{server} wait={wait}")
        current[server] = request
        heapq.heappush(running, (t + request.duration, server))
        busy[server] += request.duration
        served_by[server] += 1
        served += 1
        total_wait += wait
        max_wait = max(max_wait, wait)

    next_arrival = 0
    while running or next_arrival < len(requests):
        t = running[0][0] if running else requests[next_arrival].arrival
        if next_arrival < len(requests):
            t = min(t, requests[next_arrival].arrival)

        # Durations are at least 1, so requests started here never finish at t.
        while running and running[0][0] == t:
            _, server = heapq.heappop(running)
            out.append(f"{t} done {current.pop(server).id} s{server}")
            makespan = t
            if queue:
                start(t, queue.popleft(), server)
            else:
                heapq.heappush(idle, server)

        while next_arrival < len(requests) and requests[next_arrival].arrival == t:
            request = requests[next_arrival]
            next_arrival += 1
            if idle:
                start(t, request, heapq.heappop(idle))
            elif cap is None or len(queue) < cap:
                queue.append(request)
            else:
                out.append(f"{t} reject {request.id}")
                rejected += 1

    out.append(f"served={served} rejected={rejected} max_wait={max_wait} "
               f"total_wait={total_wait} makespan={makespan}")
    for k in range(1, n_servers + 1):
        out.append(f"s{k} busy={busy[k]} served={served_by[k]}")
    return out


def main(argv):
    try:
        n_servers, cap = parse_args(argv)
    except UsageError as e:
        print(f"servsim: {e}\nusage: servsim [-q CAP] N", file=sys.stderr)
        return 2
    try:
        requests = read_trace(sys.stdin.buffer.read().decode("latin-1"))
    except TraceError as e:
        print(f"servsim: invalid trace: {e}", file=sys.stderr)
        return 1
    out = simulate(requests, n_servers, cap)
    sys.stdout.write("".join(line + "\n" for line in out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
