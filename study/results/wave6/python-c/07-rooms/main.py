"""rooms: a meeting-room booking service over a line protocol."""
import re
import sys
from dataclasses import dataclass, field

NAME = re.compile(r"[a-z0-9]{1,12}")
CAP = re.compile(r"[1-9][0-9]{0,2}")
MINUTES = re.compile(r"[1-9][0-9]{0,3}")
TIME = re.compile(r"([0-9]{2}):([0-9]{2})")
BOOKING_ID = re.compile(r"B([1-9][0-9]{0,8})")

DAY_START, DAY_END = 8 * 60, 18 * 60


class CommandError(Exception):
    pass


BAD_COMMAND = "bad command"


@dataclass
class Booking:
    id: int
    room: str
    start: int
    end: int
    who: str


@dataclass
class Room:
    name: str
    capacity: int
    bookings: dict[int, Booking] = field(default_factory=dict)

    def sorted_bookings(self) -> list[Booking]:
        return sorted(self.bookings.values(), key=lambda b: b.start)

    def earliest_free(self, minutes: int) -> int | None:
        s = DAY_START
        for b in self.sorted_bookings():
            if b.start >= s + minutes:
                break
            s = max(s, b.end)
        return s if s + minutes <= DAY_END else None


def match(pattern: re.Pattern, token: str) -> re.Match:
    m = pattern.fullmatch(token)
    if not m:
        raise CommandError(BAD_COMMAND)
    return m


def parse_time(token: str) -> int:
    m = match(TIME, token)
    hh, mm = int(m[1]), int(m[2])
    if (hh <= 23 and mm <= 59) or (hh == 24 and mm == 0):
        return hh * 60 + mm
    raise CommandError(BAD_COMMAND)


def fmt_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


class Service:
    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self.bookings: dict[int, Booking] = {}
        self.next_id = 1

    def handle(self, line: str) -> str:
        try:
            return self.dispatch(line.split(" "))
        except CommandError as e:
            return f"ERR {e}"

    def dispatch(self, tokens: list[str]) -> str:
        command, args = tokens[0], tokens[1:]
        handler = {
            "ROOM": (self.room, 2),
            "BOOK": (self.book, 4),
            "CANCEL": (self.cancel, 1),
            "SCHEDULE": (self.schedule, 1),
            "FIND": (self.find, 2),
        }.get(command)
        if handler is None or len(args) != handler[1]:
            raise CommandError(BAD_COMMAND)
        return handler[0](*args)

    def room(self, name: str, cap: str) -> str:
        match(NAME, name)
        match(CAP, cap)
        if name in self.rooms:
            raise CommandError("room exists")
        self.rooms[name] = Room(name, int(cap))
        return "OK"

    def book(self, name: str, start_s: str, end_s: str, who: str) -> str:
        match(NAME, name)
        start, end = parse_time(start_s), parse_time(end_s)
        match(NAME, who)
        if start >= end:
            raise CommandError("bad time")
        room = self.rooms.get(name)
        if room is None:
            raise CommandError("no such room")
        for b in room.sorted_bookings():
            if b.start < end and start < b.end:
                raise CommandError(f"conflict B{b.id}")
        booking = Booking(self.next_id, name, start, end, who)
        self.next_id += 1
        room.bookings[booking.id] = booking
        self.bookings[booking.id] = booking
        return f"OK B{booking.id}"

    def cancel(self, token: str) -> str:
        booking_id = int(match(BOOKING_ID, token)[1])
        booking = self.bookings.pop(booking_id, None)
        if booking is None:
            raise CommandError("no such booking")
        del self.rooms[booking.room].bookings[booking_id]
        return "OK"

    def schedule(self, name: str) -> str:
        match(NAME, name)
        room = self.rooms.get(name)
        if room is None:
            raise CommandError("no such room")
        entries = [f"B{b.id} {fmt_time(b.start)}-{fmt_time(b.end)} {b.who}"
                   for b in room.sorted_bookings()]
        return ", ".join(entries) if entries else "(empty)"

    def find(self, people_s: str, minutes_s: str) -> str:
        people = int(match(CAP, people_s)[0])
        minutes = int(match(MINUTES, minutes_s)[0])
        best = None
        for room in self.rooms.values():
            if room.capacity < people:
                continue
            s = room.earliest_free(minutes)
            if s is None:
                continue
            key = (s, room.capacity, room.name.encode())
            if best is None or key < best[0]:
                best = (key, room)
        if best is None:
            return "NONE"
        s = best[0][0]
        return f"{best[1].name} {fmt_time(s)} {fmt_time(s + minutes)}"


def main(argv: list[str]) -> int:
    if argv:
        print("usage: rooms", file=sys.stderr)
        return 2
    service = Service()
    for raw in sys.stdin.buffer:
        line = raw.decode("ascii", errors="replace")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(service.handle(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
