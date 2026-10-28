import re
import sys
from bisect import bisect_left, bisect_right

NAME_RE = re.compile(r"[a-z0-9]{1,12}")
CAP_RE = re.compile(r"[1-9][0-9]{0,2}")
MINUTES_RE = re.compile(r"[1-9][0-9]{0,3}")
TIME_RE = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]|24:00")
ID_RE = re.compile(r"B([1-9][0-9]{0,8})")

DAY_START = 8 * 60
DAY_END = 18 * 60


def parse_time(text):
    return int(text[:2]) * 60 + int(text[3:])


def format_time(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


class Room:
    def __init__(self, name, capacity):
        self.name = name
        self.capacity = capacity
        # Bookings never overlap, so sorting by start also sorts by end.
        self.starts = []
        self.ends = []
        self.entries = []  # (booking id, who), parallel to starts/ends

    def first_overlap(self, start, end):
        """Index of the earliest-starting booking overlapping [start, end), or None."""
        i = bisect_right(self.ends, start)
        if i < len(self.starts) and self.starts[i] < end:
            return i
        return None

    def add(self, start, end, booking_id, who):
        i = bisect_left(self.starts, start)
        self.starts.insert(i, start)
        self.ends.insert(i, end)
        self.entries.insert(i, (booking_id, who))

    def remove(self, start):
        i = bisect_left(self.starts, start)
        del self.starts[i], self.ends[i], self.entries[i]

    def earliest_free(self, minutes):
        """Earliest start in [08:00, 18:00 - minutes] free of bookings, or None."""
        candidate = DAY_START
        for start, end in zip(self.starts, self.ends):
            if end <= candidate:
                continue
            if candidate + minutes <= start:
                break
            candidate = end
        if candidate + minutes <= DAY_END:
            return candidate
        return None


class Service:
    def __init__(self):
        self.rooms = {}
        self.bookings = {}  # booking id -> (room, start)
        self.next_id = 1

    def handle(self, line):
        tokens = line.split(" ")
        cmd, args = tokens[0], tokens[1:]
        if cmd == "ROOM" and len(args) == 2:
            if NAME_RE.fullmatch(args[0]) and CAP_RE.fullmatch(args[1]):
                return self.add_room(args[0], int(args[1]))
        elif cmd == "BOOK" and len(args) == 4:
            room, start, end, who = args
            if (NAME_RE.fullmatch(room) and TIME_RE.fullmatch(start)
                    and TIME_RE.fullmatch(end) and NAME_RE.fullmatch(who)):
                return self.book(room, parse_time(start), parse_time(end), who)
        elif cmd == "CANCEL" and len(args) == 1:
            m = ID_RE.fullmatch(args[0])
            if m:
                return self.cancel(int(m.group(1)))
        elif cmd == "SCHEDULE" and len(args) == 1:
            if NAME_RE.fullmatch(args[0]):
                return self.schedule(args[0])
        elif cmd == "FIND" and len(args) == 2:
            if CAP_RE.fullmatch(args[0]) and MINUTES_RE.fullmatch(args[1]):
                return self.find(int(args[0]), int(args[1]))
        return "ERR bad command"

    def add_room(self, name, capacity):
        if name in self.rooms:
            return "ERR room exists"
        self.rooms[name] = Room(name, capacity)
        return "OK"

    def book(self, room_name, start, end, who):
        if start >= end:
            return "ERR bad time"
        room = self.rooms.get(room_name)
        if room is None:
            return "ERR no such room"
        i = room.first_overlap(start, end)
        if i is not None:
            return f"ERR conflict B{room.entries[i][0]}"
        booking_id = self.next_id
        self.next_id += 1
        room.add(start, end, booking_id, who)
        self.bookings[booking_id] = (room, start)
        return f"OK B{booking_id}"

    def cancel(self, booking_id):
        entry = self.bookings.pop(booking_id, None)
        if entry is None:
            return "ERR no such booking"
        room, start = entry
        room.remove(start)
        return "OK"

    def schedule(self, room_name):
        room = self.rooms.get(room_name)
        if room is None:
            return "ERR no such room"
        if not room.starts:
            return "(empty)"
        return ", ".join(
            f"B{booking_id} {format_time(start)}-{format_time(end)} {who}"
            for start, end, (booking_id, who) in zip(room.starts, room.ends, room.entries)
        )

    def find(self, people, minutes):
        best = None  # (start, capacity, name)
        for room in self.rooms.values():
            if room.capacity < people:
                continue
            start = room.earliest_free(minutes)
            if start is None:
                continue
            key = (start, room.capacity, room.name.encode("ascii"))
            if best is None or key < best:
                best = key
        if best is None:
            return "NONE"
        start, _, name = best
        return f"{name.decode('ascii')} {format_time(start)} {format_time(start + minutes)}"


def main(argv):
    if argv:
        print("usage: rooms", file=sys.stderr)
        return 2
    service = Service()
    for raw in sys.stdin.buffer:
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(service.handle(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
