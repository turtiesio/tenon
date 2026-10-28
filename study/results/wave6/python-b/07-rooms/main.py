import re
import sys

NAME = r'[a-z0-9]{1,12}'
NUMBER = r'[1-9][0-9]{0,2}'
TIME = r'(?:[01][0-9]:[0-5][0-9]|2[0-3]:[0-5][0-9]|24:00)'
PATTERNS = [
    re.compile(f'ROOM ({NAME}) ({NUMBER})'),
    re.compile(f'BOOK ({NAME}) ({TIME}) ({TIME}) ({NAME})'),
    re.compile(r'CANCEL (B[1-9][0-9]{0,8})'),
    re.compile(f'SCHEDULE ({NAME})'),
    re.compile(f'FIND ({NUMBER}) ([1-9][0-9]{{0,3}})'),
]


def minutes(value):
    hour, minute = map(int, value.split(':'))
    return hour * 60 + minute


def time_text(value):
    return f'{value // 60:02d}:{value % 60:02d}'


class Service:
    def __init__(self):
        self.rooms = {}
        self.bookings = {}
        self.next_id = 1

    def schedule(self, room):
        return sorted((booking for booking in self.bookings.values() if booking[0] == room), key=lambda booking: booking[1])

    def command(self, line):
        match = next((match for pattern in PATTERNS if (match := pattern.fullmatch(line))), None)
        if match is None:
            return 'ERR bad command'
        args = match.groups()
        command = line.split(' ', 1)[0]
        if command == 'ROOM':
            room, cap = args
            if room in self.rooms:
                return 'ERR room exists'
            self.rooms[room] = int(cap)
            return 'OK'
        if command == 'CANCEL':
            if args[0] not in self.bookings:
                return 'ERR no such booking'
            del self.bookings[args[0]]
            return 'OK'
        if command in ('BOOK', 'SCHEDULE'):
            room = args[0]
            if command == 'BOOK':
                start, end = minutes(args[1]), minutes(args[2])
                if start >= end:
                    return 'ERR bad time'
            if room not in self.rooms:
                return 'ERR no such room'
            bookings = self.schedule(room)
            if command == 'SCHEDULE':
                return ', '.join(f'{bid} {time_text(s)}-{time_text(e)} {who}' for _, s, e, who, bid in bookings) or '(empty)'
            for _, s, e, _, bid in bookings:
                if start < e and s < end:
                    return f'ERR conflict {bid}'
            bid = f'B{self.next_id}'
            self.next_id += 1
            self.bookings[bid] = (room, start, end, args[3], bid)
            return f'OK {bid}'
        people, duration = map(int, args)
        choices = []
        for room, capacity in self.rooms.items():
            if capacity < people:
                continue
            start = 480
            for _, s, e, _, _ in self.schedule(room):
                if start + duration <= s:
                    break
                if start < e:
                    start = e
            if start + duration <= 1080:
                choices.append((start, capacity, room))
        if not choices:
            return 'NONE'
        start, _, room = min(choices)
        return f'{room} {time_text(start)} {time_text(start + duration)}'


def main():
    if len(sys.argv) != 1:
        print('no arguments allowed', file=sys.stderr)
        return 2
    service = Service()
    for raw in sys.stdin.buffer:
        line = raw.removesuffix(b'\n').removesuffix(b'\r').decode('ascii')
        print(service.command(line), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
