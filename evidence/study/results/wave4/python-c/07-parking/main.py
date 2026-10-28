"""parking: a parking garage service driven by a line protocol."""
import heapq
import re
import sys

PLATE = r"[A-Z0-9]{1,8}"
TIME = r"[0-9]{1,7}"
COMMANDS = [
    (re.compile(rf"(IN) ({PLATE}) ({TIME})"), "IN"),
    (re.compile(rf"(OUT) ({PLATE}) ({TIME})"), "OUT"),
    (re.compile(rf"(WHERE) ({PLATE})"), "WHERE"),
    (re.compile(r"(STATUS)"), "STATUS"),
]
GRACE = 15
DAY = 1440
HOUR_FEE = 250
DAY_CAP = 2000


def fee(duration):
    if duration <= GRACE:
        return 0
    days, rest = divmod(duration, DAY)
    hours = -(-rest // 60)
    return days * DAY_CAP + min(DAY_CAP, HOUR_FEE * hours)


def amount(cents):
    return f"{cents // 100}.{cents % 100:02d}"


class Garage:
    def __init__(self, capacity):
        self.free = list(range(1, capacity + 1))  # already a valid min-heap
        self.parked = {}  # plate -> (spot, entry time)
        self.clock = 0
        self.revenue = 0

    def handle(self, line):
        for pattern, name in COMMANDS:
            m = pattern.fullmatch(line)
            if m:
                break
        else:
            return "ERR bad command"

        if name == "STATUS":
            return f"free={len(self.free)} parked={len(self.parked)} revenue={amount(self.revenue)}"
        plate = m.group(2)
        if name == "WHERE":
            return f"SPOT {self.parked[plate][0]}" if plate in self.parked else "ERR not parked"

        time = int(m.group(3))
        if time < self.clock:
            return "ERR bad time"
        self.clock = time
        if name == "IN":
            if plate in self.parked:
                return "ERR already parked"
            if not self.free:
                return "FULL"
            spot = heapq.heappop(self.free)
            self.parked[plate] = (spot, time)
            return f"OK {spot}"
        # OUT
        if plate not in self.parked:
            return "ERR not parked"
        spot, entered = self.parked.pop(plate)
        heapq.heappush(self.free, spot)
        charge = fee(time - entered)
        self.revenue += charge
        return f"FEE {amount(charge)}"


def main(argv):
    if len(argv) != 1 or not re.fullmatch(r"[0-9]{1,4}", argv[0]) or not 1 <= int(argv[0]) <= 1000:
        print("usage: parking CAPACITY  (1-1000)", file=sys.stderr)
        return 2

    garage = Garage(int(argv[0]))
    stdin = sys.stdin.buffer
    while True:
        raw = stdin.readline()
        if not raw:
            break
        line = raw.decode("latin-1").removesuffix("\n").removesuffix("\r")
        sys.stdout.write(garage.handle(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
