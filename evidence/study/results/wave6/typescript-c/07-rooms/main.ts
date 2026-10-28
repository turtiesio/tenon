interface Booking {
  id: number;
  start: number;
  end: number;
  who: string;
}

interface Room {
  name: string;
  capacity: number;
  bookings: Booking[]; // sorted by start; ranges never overlap
}

const WORK_START = 8 * 60;
const WORK_END = 18 * 60;

const NAME = /^[a-z0-9]{1,12}$/;
const COUNT = /^[1-9][0-9]{0,2}$/;
const MINUTES = /^[1-9][0-9]{0,3}$/;
const TIME = /^(?:([01][0-9]|2[0-3]):([0-5][0-9])|(24):00)$/;
const BOOKING_ID = /^B([1-9][0-9]{0,8})$/;

function parseTime(token: string): number | null {
  const m = TIME.exec(token);
  if (!m) return null;
  return m[3] ? 24 * 60 : Number(m[1]) * 60 + Number(m[2]);
}

function formatTime(minutes: number): string {
  const hh = String(Math.floor(minutes / 60)).padStart(2, "0");
  const mm = String(minutes % 60).padStart(2, "0");
  return `${hh}:${mm}`;
}

function compareBytes(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0; // names are ASCII
}

class Service {
  private rooms = new Map<string, Room>();
  private nextId = 1;

  handle(line: string): string {
    const t = line.split(" ");
    switch (t[0]) {
      case "ROOM":
        if (t.length === 3 && NAME.test(t[1]) && COUNT.test(t[2])) return this.addRoom(t[1], Number(t[2]));
        break;
      case "BOOK": {
        if (t.length !== 5 || !NAME.test(t[1]) || !NAME.test(t[4])) break;
        const start = parseTime(t[2]);
        const end = parseTime(t[3]);
        if (start === null || end === null) break;
        return this.book(t[1], start, end, t[4]);
      }
      case "CANCEL": {
        const m = t.length === 2 ? BOOKING_ID.exec(t[1]) : null;
        if (m) return this.cancel(Number(m[1]));
        break;
      }
      case "SCHEDULE":
        if (t.length === 2 && NAME.test(t[1])) return this.schedule(t[1]);
        break;
      case "FIND":
        if (t.length === 3 && COUNT.test(t[1]) && MINUTES.test(t[2])) return this.find(Number(t[1]), Number(t[2]));
        break;
    }
    return "ERR bad command";
  }

  private addRoom(name: string, capacity: number): string {
    if (this.rooms.has(name)) return "ERR room exists";
    this.rooms.set(name, { name, capacity, bookings: [] });
    return "OK";
  }

  private book(roomName: string, start: number, end: number, who: string): string {
    if (start >= end) return "ERR bad time";
    const room = this.rooms.get(roomName);
    if (!room) return "ERR no such room";
    const clash = room.bookings.find((b) => b.start < end && start < b.end);
    if (clash) return `ERR conflict B${clash.id}`;
    const booking = { id: this.nextId++, start, end, who };
    room.bookings.push(booking);
    room.bookings.sort((a, b) => a.start - b.start);
    return `OK B${booking.id}`;
  }

  private cancel(id: number): string {
    for (const room of this.rooms.values()) {
      const i = room.bookings.findIndex((b) => b.id === id);
      if (i >= 0) {
        room.bookings.splice(i, 1);
        return "OK";
      }
    }
    return "ERR no such booking";
  }

  private schedule(roomName: string): string {
    const room = this.rooms.get(roomName);
    if (!room) return "ERR no such room";
    if (room.bookings.length === 0) return "(empty)";
    return room.bookings.map((b) => `B${b.id} ${formatTime(b.start)}-${formatTime(b.end)} ${b.who}`).join(", ");
  }

  /** Earliest start in working hours at which `length` minutes are free in the room, or null. */
  private earliestFree(room: Room, length: number): number | null {
    // The earliest free start is the start of the day or the end of some booking.
    const candidates = [WORK_START, ...room.bookings.map((b) => b.end).filter((e) => e > WORK_START)];
    candidates.sort((a, b) => a - b);
    for (const s of candidates) {
      if (s + length > WORK_END) break;
      if (!room.bookings.some((b) => b.start < s + length && s < b.end)) return s;
    }
    return null;
  }

  private find(people: number, length: number): string {
    let best: { room: Room; start: number } | null = null;
    for (const room of this.rooms.values()) {
      if (room.capacity < people) continue;
      const start = this.earliestFree(room, length);
      if (start === null) continue;
      if (
        best === null ||
        start < best.start ||
        (start === best.start &&
          (room.capacity < best.room.capacity ||
            (room.capacity === best.room.capacity && compareBytes(room.name, best.room.name) < 0)))
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
  const respond = (line: string): void => {
    const clean = line.endsWith("\r") ? line.slice(0, -1) : line;
    process.stdout.write(service.handle(clean) + "\n");
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
