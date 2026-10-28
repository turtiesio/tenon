import heapq
import re
import sys


def money(cents):
    return f'{cents // 100}.{cents % 100:02d}'


class Garage:
    def __init__(self, capacity):
        self.free = list(range(1, capacity + 1))
        self.parked = {}
        self.clock = 0
        self.revenue = 0

    def command(self, line):
        if line == 'STATUS':
            return f'free={len(self.free)} parked={len(self.parked)} revenue={money(self.revenue)}'
        match = re.fullmatch(r'WHERE ([A-Z0-9]{1,8})', line)
        if match:
            car = self.parked.get(match[1])
            return f'SPOT {car[0]}' if car else 'ERR not parked'
        match = re.fullmatch(r'(IN|OUT) ([A-Z0-9]{1,8}) ([0-9]{1,7})', line)
        if not match:
            return 'ERR bad command'
        kind, plate, time = match.groups()
        time = int(time)
        if time < self.clock:
            return 'ERR bad time'
        self.clock = time
        if kind == 'IN':
            if plate in self.parked:
                return 'ERR already parked'
            if not self.free:
                return 'FULL'
            spot = heapq.heappop(self.free)
            self.parked[plate] = (spot, time)
            return f'OK {spot}'
        if plate not in self.parked:
            return 'ERR not parked'
        spot, entry = self.parked.pop(plate)
        heapq.heappush(self.free, spot)
        duration = time - entry
        days, rest = divmod(duration, 1440)
        fee = 0 if duration <= 15 else days * 2000 + min(2000, 250 * ((rest + 59) // 60))
        self.revenue += fee
        return 'FEE ' + money(fee)


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r'[0-9]{1,4}', sys.argv[1]) or not 1 <= int(sys.argv[1]) <= 1000:
        print('Invalid capacity', file=sys.stderr)
        return 2
    garage = Garage(int(sys.argv[1]))
    for raw in sys.stdin.buffer:
        line = raw.decode('utf-8', errors='replace').removesuffix('\n').removesuffix('\r')
        print(garage.command(line), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
