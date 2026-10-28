import heapq
import re
import sys

CAPACITY_RE = re.compile(r"[0-9]{1,4}")
PLATE_RE = re.compile(r"[A-Z0-9]{1,8}")
TIME_RE = re.compile(r"[0-9]{1,7}")

GRACE = 15
HOUR_RATE = 250
DAY_RATE = 2000
MINUTES_PER_DAY = 1440


def fee_for(duration):
    if duration <= GRACE:
        return 0
    days, rest = divmod(duration, MINUTES_PER_DAY)
    started_hours = -(-rest // 60)
    return days * DAY_RATE + min(DAY_RATE, HOUR_RATE * started_hours)


def money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


class Garage:
    def __init__(self, capacity):
        self.capacity = capacity
        self.free_spots = list(range(1, capacity + 1))  # already a valid min-heap
        self.parked = {}  # plate -> (spot, entry time)
        self.clock = 0
        self.revenue = 0

    def handle(self, line):
        tokens = line.split(" ")
        cmd = tokens[0]
        if cmd == "STATUS" and len(tokens) == 1:
            return (f"free={len(self.free_spots)} parked={len(self.parked)} "
                    f"revenue={money(self.revenue)}")
        if cmd == "WHERE" and len(tokens) == 2 and PLATE_RE.fullmatch(tokens[1]):
            return self.where(tokens[1])
        if (cmd in ("IN", "OUT") and len(tokens) == 3
                and PLATE_RE.fullmatch(tokens[1]) and TIME_RE.fullmatch(tokens[2])):
            time = int(tokens[2])
            if time < self.clock:
                return "ERR bad time"
            self.clock = time
            if cmd == "IN":
                return self.enter(tokens[1], time)
            return self.leave(tokens[1], time)
        return "ERR bad command"

    def where(self, plate):
        if plate not in self.parked:
            return "ERR not parked"
        return f"SPOT {self.parked[plate][0]}"

    def enter(self, plate, time):
        if plate in self.parked:
            return "ERR already parked"
        if not self.free_spots:
            return "FULL"
        spot = heapq.heappop(self.free_spots)
        self.parked[plate] = (spot, time)
        return f"OK {spot}"

    def leave(self, plate, time):
        if plate not in self.parked:
            return "ERR not parked"
        spot, entered = self.parked.pop(plate)
        heapq.heappush(self.free_spots, spot)
        fee = fee_for(time - entered)
        self.revenue += fee
        return f"FEE {money(fee)}"


def main():
    argv = sys.argv[1:]
    if len(argv) != 1 or not CAPACITY_RE.fullmatch(argv[0]) or not 1 <= int(argv[0]) <= 1000:
        print("parking: usage: parking CAPACITY (1-1000)", file=sys.stderr)
        sys.exit(2)
    garage = Garage(int(argv[0]))

    for raw in sys.stdin.buffer:
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(garage.handle(line) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
