interface Booking {
  id: number;
  room: string;
  start: number;
  end: number;
  who: string;
}

interface Room {
  name: string;
  cap: number;
  bookings: Map<number, Booking>;
}

const NAME = "[a-z0-9]{1,12}";
const COUNT = "[1-9][0-9]{0,2}";
const TIME = "[0-9]{2}:[0-9]{2}";
const ROOM_RE = new RegExp(`^ROOM (${NAME}) (${COUNT})$`);
const BOOK_RE = new RegExp(`^BOOK (${NAME}) (${TIME}) (${TIME}) (${NAME})$`);
const CANCEL_RE = /^CANCEL B([1-9][0-9]{0,8})$/;
const SCHEDULE_RE = new RegExp(`^SCHEDULE (${NAME})$`);
const FIND_RE = new RegExp(`^FIND (${COUNT}) ([1-9][0-9]{0,3})$`);

const DAY_START = 8 * 60;
const DAY_END = 18 * 60;

/** Parses HH:MM into minutes of the day, or null if it is not a valid time. */
function parseTime(text: string): number | null {
  const h = Number(text.slice(0, 2));
  const m = Number(text.slice(3, 5));
  if (h === 24 && m === 0) return 24 * 60;
  if (h > 23 || m > 59) return null;
  return h * 60 + m;
}

function formatTime(minutes: number): string {
  const h = String(Math.floor(minutes / 60)).padStart(2, "0");
  const m = String(minutes % 60).padStart(2, "0");
  return `${h}:${m}`;
}

function sortedBookings(room: Room): Booking[] {
  return [...room.bookings.values()].sort((a, b) => a.start - b.start);
}

/** Earliest start in working hours where the room is free for `length` minutes, or null. */
function earliestFree(room: Room, length: number): number | null {
  let s = DAY_START;
  for (const b of sortedBookings(room)) {
    if (b.end <= s) continue;
    if (b.start >= s + length) break;
    s = b.end;
  }
  return s + length <= DAY_END ? s : null;
}

class Service {
  private rooms = new Map<string, Room>();
  private bookings = new Map<number, Booking>();
  private nextId = 1;

  handle(line: string): string {
    let m: RegExpExecArray | null;
    if ((m = ROOM_RE.exec(line))) return this.addRoom(m[1], Number(m[2]));
    if ((m = BOOK_RE.exec(line))) {
      const start = parseTime(m[2]);
      const end = parseTime(m[3]);
      if (start === null || end === null) return "ERR bad command";
      return this.book(m[1], start, end, m[4]);
    }
    if ((m = CANCEL_RE.exec(line))) return this.cancel(Number(m[1]));
    if ((m = SCHEDULE_RE.exec(line))) return this.schedule(m[1]);
    if ((m = FIND_RE.exec(line))) return this.find(Number(m[1]), Number(m[2]));
    return "ERR bad command";
  }

  private addRoom(name: string, cap: number): string {
    if (this.rooms.has(name)) return "ERR room exists";
    this.rooms.set(name, { name, cap, bookings: new Map() });
    return "OK";
  }

  private book(roomName: string, start: number, end: number, who: string): string {
    if (start >= end) return "ERR bad time";
    const room = this.rooms.get(roomName);
    if (!room) return "ERR no such room";
    let blocker: Booking | null = null;
    for (const b of room.bookings.values()) {
      if (b.start < end && start < b.end && (blocker === null || b.start < blocker.start)) blocker = b;
    }
    if (blocker) return `ERR conflict B${blocker.id}`;
    const booking: Booking = { id: this.nextId++, room: roomName, start, end, who };
    room.bookings.set(booking.id, booking);
    this.bookings.set(booking.id, booking);
    return `OK B${booking.id}`;
  }

  private cancel(id: number): string {
    const booking = this.bookings.get(id);
    if (!booking) return "ERR no such booking";
    this.bookings.delete(id);
    this.rooms.get(booking.room)!.bookings.delete(id);
    return "OK";
  }

  private schedule(roomName: string): string {
    const room = this.rooms.get(roomName);
    if (!room) return "ERR no such room";
    if (room.bookings.size === 0) return "(empty)";
    return sortedBookings(room)
      .map((b) => `B${b.id} ${formatTime(b.start)}-${formatTime(b.end)} ${b.who}`)
      .join(", ");
  }

  private find(people: number, length: number): string {
    let best: { room: Room; start: number } | null = null;
    for (const room of this.rooms.values()) {
      if (room.cap < people) continue;
      const start = earliestFree(room, length);
      if (start === null) continue;
      if (
        best === null ||
        start < best.start ||
        (start === best.start && room.cap < best.room.cap) ||
        (start === best.start && room.cap === best.room.cap && room.name < best.room.name)
      ) {
        best = { room, start };
      }
    }
    if (best === null) return "NONE";
    return `${best.room.name} ${formatTime(best.start)} ${formatTime(best.start + length)}`;
  }
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("usage: rooms\n");
    process.exitCode = 2;
    return;
  }
  const service = new Service();
  const respond = (raw: string): void => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    process.stdout.write(service.handle(line) + "\n");
  };
  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let nl: number;
    while ((nl = pending.indexOf("\n")) >= 0) {
      respond(pending.slice(0, nl));
      pending = pending.slice(nl + 1);
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") respond(pending);
  });
}

main();
