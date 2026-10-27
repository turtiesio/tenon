#!/usr/bin/env python3
"""servsim: discrete-event simulation of N servers sharing one FIFO queue."""

import heapq
import re
import sys
from collections import deque
from dataclasses import dataclass

ID_RE = re.compile(r"[A-Za-z0-9_-]{1,16}")
ARRIVAL_RE = re.compile(r"[0-9]{1,12}")
DURATION_RE = re.compile(r"[0-9]{1,9}")
SERVERS_RE = re.compile(r"[0-9]{1,4}")
CAPACITY_RE = re.compile(r"[0-9]{1,7}")

EXIT_INVALID_TRACE, EXIT_USAGE = 1, 2


@dataclass
class Request:
    id: str
    arrival: int
    duration: int


class TraceError(Exception):
    pass


def parse_args(argv):
    """Return (servers, queue capacity or None), or None on a usage error."""
    servers = None
    capacity = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-q":
            if i + 1 >= len(argv) or not CAPACITY_RE.fullmatch(argv[i + 1]):
                return None
            capacity = int(argv[i + 1])
            i += 2
        elif arg.startswith("-") or servers is not None:
            return None
        else:
            if not SERVERS_RE.fullmatch(arg) or not 1 <= int(arg) <= 1000:
                return None
            servers = int(arg)
            i += 1
    if servers is None:
        return None
    return servers, capacity


def parse_trace(text):
    requests = []
    seen = set()
    previous_arrival = 0
    for number, line in enumerate(text.split("\n"), start=1):
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip(" ") == "":
            continue
        parts = line.split(" ")
        if (
            len(parts) != 3
            or not ID_RE.fullmatch(parts[0])
            or not ARRIVAL_RE.fullmatch(parts[1])
            or not DURATION_RE.fullmatch(parts[2])
            or int(parts[2]) < 1
        ):
            raise TraceError(f"line {number}: malformed request")
        request = Request(parts[0], int(parts[1]), int(parts[2]))
        if request.id in seen:
            raise TraceError(f"line {number}: duplicate id {request.id}")
        if request.arrival < previous_arrival:
            raise TraceError(f"line {number}: arrival goes backwards")
        seen.add(request.id)
        previous_arrival = request.arrival
        requests.append(request)
    return requests


def simulate(requests, server_count, capacity):
    """Run the simulation; return the output lines."""
    out = []
    busy = []  # heap of (finish time, server number, request)
    idle = list(range(1, server_count + 1))  # heap of idle server numbers
    queue = deque()
    busy_time = [0] * (server_count + 1)
    served_by = [0] * (server_count + 1)
    served = rejected = max_wait = total_wait = makespan = 0

    def start(t, server, request):
        nonlocal served, max_wait, total_wait
        wait = t - request.arrival
        served += 1
        total_wait += wait
        max_wait = max(max_wait, wait)
        busy_time[server] += request.duration
        served_by[server] += 1
        heapq.heappush(busy, (t + request.duration, server, request))
        out.append(f"{t} start {request.id} s{server} wait={wait}")

    next_request = 0
    while next_request < len(requests) or busy:
        candidates = []
        if busy:
            candidates.append(busy[0][0])
        if next_request < len(requests):
            candidates.append(requests[next_request].arrival)
        t = min(candidates)

        # Completions first, in increasing server number.
        while busy and busy[0][0] == t:
            _, server, finished = heapq.heappop(busy)
            out.append(f"{t} done {finished.id} s{server}")
            makespan = t
            if queue:
                start(t, server, queue.popleft())
            else:
                heapq.heappush(idle, server)

        # Then arrivals, in input order.
        while next_request < len(requests) and requests[next_request].arrival == t:
            request = requests[next_request]
            next_request += 1
            if idle:
                start(t, heapq.heappop(idle), request)
            elif capacity is None or len(queue) < capacity:
                queue.append(request)
            else:
                rejected += 1
                out.append(f"{t} reject {request.id}")

    out.append(
        f"served={served} rejected={rejected} max_wait={max_wait} "
        f"total_wait={total_wait} makespan={makespan}"
    )
    for server in range(1, server_count + 1):
        out.append(f"s{server} busy={busy_time[server]} served={served_by[server]}")
    return out


def main(argv):
    parsed = parse_args(argv)
    if parsed is None:
        print("usage: servsim [-q CAP] N", file=sys.stderr)
        return EXIT_USAGE
    server_count, capacity = parsed

    try:
        requests = parse_trace(sys.stdin.buffer.read().decode("latin-1"))
    except TraceError as e:
        print(f"servsim: invalid trace: {e}", file=sys.stderr)
        return EXIT_INVALID_TRACE

    sys.stdout.write("\n".join(simulate(requests, server_count, capacity)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
