if (process.argv.length > 2) { console.error('Usage: rooms'); process.exit(2); }
type Booking = { id: string; start: number; end: number; who: string; room: string };
type Room = { capacity: number; bookings: Booking[] };
const rooms = new Map<string, Room>(), bookings = new Map<string, Booking>();
let nextId = 1;
const name = '[a-z0-9]{1,12}', time = '(?:[01][0-9]|2[0-3]):[0-5][0-9]|24:00';
const patterns = {
  ROOM: new RegExp(`^ROOM (${name}) ([1-9][0-9]{0,2})$`),
  BOOK: new RegExp(`^BOOK (${name}) (${time}) (${time}) (${name})$`),
  CANCEL: /^CANCEL (B[1-9][0-9]{0,8})$/,
  SCHEDULE: new RegExp(`^SCHEDULE (${name})$`),
  FIND: /^FIND ([1-9][0-9]{0,2}) ([1-9][0-9]{0,3})$/,
};
const minutes = (s: string) => Number(s.slice(0, 2)) * 60 + Number(s.slice(3));
const format = (n: number) => `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`;
function handle(line: string): string {
  let match: RegExpExecArray | null;
  if ((match = patterns.ROOM.exec(line))) {
    if (rooms.has(match[1])) return 'ERR room exists';
    rooms.set(match[1], { capacity: Number(match[2]), bookings: [] }); return 'OK';
  }
  if ((match = patterns.BOOK.exec(line))) {
    const [, roomName, startText, endText, who] = match;
    const start = minutes(startText), end = minutes(endText);
    if (start >= end) return 'ERR bad time';
    const room = rooms.get(roomName);
    if (!room) return 'ERR no such room';
    const conflict = room.bookings.find(b => start < b.end && b.start < end);
    if (conflict) return `ERR conflict ${conflict.id}`;
    const booking = { id: `B${nextId++}`, start, end, who, room: roomName };
    room.bookings.push(booking); room.bookings.sort((a, b) => a.start - b.start);
    bookings.set(booking.id, booking); return `OK ${booking.id}`;
  }
  if ((match = patterns.CANCEL.exec(line))) {
    const booking = bookings.get(match[1]);
    if (!booking) return 'ERR no such booking';
    const room = rooms.get(booking.room)!;
    room.bookings = room.bookings.filter(b => b.id !== booking.id);
    bookings.delete(booking.id); return 'OK';
  }
  if ((match = patterns.SCHEDULE.exec(line))) {
    const room = rooms.get(match[1]);
    if (!room) return 'ERR no such room';
    return room.bookings.map(b => `${b.id} ${format(b.start)}-${format(b.end)} ${b.who}`).join(', ') || '(empty)';
  }
  if ((match = patterns.FIND.exec(line))) {
    const people = Number(match[1]), duration = Number(match[2]);
    const candidates: { name: string; capacity: number; start: number }[] = [];
    for (const [name, room] of rooms) {
      if (room.capacity < people) continue;
      let start = 480;
      for (const booking of room.bookings) {
        if (booking.end <= start) continue;
        if (start + duration <= booking.start) break;
        start = booking.end;
      }
      if (start + duration <= 1080) candidates.push({ name, capacity: room.capacity, start });
    }
    candidates.sort((a, b) => a.start - b.start || a.capacity - b.capacity || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    const best = candidates[0];
    return best ? `${best.name} ${format(best.start)} ${format(best.start + duration)}` : 'NONE';
  }
  return 'ERR bad command';
}
let pending = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk: string) => {
  pending += chunk;
  let newline: number;
  while ((newline = pending.indexOf('\n')) !== -1) {
    const line = pending.slice(0, newline).replace(/\r$/, '');
    pending = pending.slice(newline + 1);
    process.stdout.write(handle(line) + '\n');
  }
});
process.stdin.on('end', () => {
  if (pending.length) process.stdout.write(handle(pending.replace(/\r$/, '')) + '\n');
});
