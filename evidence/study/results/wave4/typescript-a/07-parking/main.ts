const args = process.argv.slice(2);
if (args.length !== 1 || !/^[0-9]{1,4}$/.test(args[0]) || Number(args[0]) < 1 || Number(args[0]) > 1000) {
  console.error('Invalid capacity'); process.exit(2);
}
const capacity = Number(args[0]);
const cars = new Map<string, {spot: number; entered: number}>();
const occupied = new Set<number>();
let clock = 0, revenue = 0;
const money = (cents: number) => `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, '0')}`;
function command(line: string): string {
  if (line === 'STATUS') return `free=${capacity - cars.size} parked=${cars.size} revenue=${money(revenue)}`;
  const where = /^WHERE ([A-Z0-9]{1,8})$/.exec(line);
  if (where) { const car = cars.get(where[1]); return car ? `SPOT ${car.spot}` : 'ERR not parked'; }
  const match = /^(IN|OUT) ([A-Z0-9]{1,8}) ([0-9]{1,7})$/.exec(line);
  if (!match) return 'ERR bad command';
  const [, action, plate, timeText] = match;
  const time = Number(timeText);
  if (time < clock) return 'ERR bad time';
  clock = time;
  const car = cars.get(plate);
  if (action === 'IN') {
    if (car) return 'ERR already parked';
    if (cars.size === capacity) return 'FULL';
    let spot = 1;
    while (occupied.has(spot)) spot++;
    cars.set(plate, {spot, entered: time}); occupied.add(spot);
    return `OK ${spot}`;
  }
  if (!car) return 'ERR not parked';
  const duration = time - car.entered;
  const fee = duration <= 15 ? 0 : Math.floor(duration / 1440) * 2000 + Math.min(2000, 250 * Math.ceil((duration % 1440) / 60));
  cars.delete(plate); occupied.delete(car.spot); revenue += fee;
  return `FEE ${money(fee)}`;
}
let pending = '';
function respond(line: string): void { process.stdout.write(command(line.replace(/\r$/, '')) + '\n'); }
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk: string) => {
  pending += chunk;
  let start = 0, end: number;
  while ((end = pending.indexOf('\n', start)) !== -1) { respond(pending.slice(start, end)); start = end + 1; }
  pending = pending.slice(start);
});
process.stdin.on('end', () => { if (pending.length) respond(pending); });
