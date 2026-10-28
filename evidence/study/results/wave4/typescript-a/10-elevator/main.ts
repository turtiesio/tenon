import fs from 'node:fs';
const args = process.argv.slice(2);
if (args.length !== 1 || !/^[0-9]{1,3}$/.test(args[0]) || /[\r\n]/.test(args[0]) || Number(args[0]) < 2 || Number(args[0]) > 100) {
  console.error('Invalid floor count'); process.exit(2);
}
const floors = Number(args[0]);
type Passenger = {time: number; from: number; to: number; board: number; arrive: number};
const passengers: Passenger[] = [];
function invalid(): never { console.error('Invalid request'); process.exit(1); }
for (const raw of fs.readFileSync(0, 'utf8').split('\n')) {
  const line = raw.replace(/\r$/, '');
  if (/^ *$/.test(line) && !line.includes('\r')) continue;
  const match = /^([0-9]{1,6}) ([0-9]{1,3}) ([0-9]{1,3})$/.exec(line);
  if (!match || match[0] !== line) invalid();
  const time = Number(match[1]), from = Number(match[2]), to = Number(match[3]);
  if (from >= floors || to >= floors || from === to || (passengers.length && time < passengers.at(-1)!.time)) invalid();
  passengers.push({time, from, to, board: -1, arrive: -1});
}
const waiting: Passenger[][] = Array.from({length: floors}, () => []);
const riding: Passenger[][] = Array.from({length: floors}, () => []);
const targets = new Set<number>();
let floor = 0, direction = 0, next = 0, arrived = 0;
let moves = 0, stops = 0, finish = 0, totalWait = 0;
for (let tick = 0; arrived < passengers.length; tick++) {
  while (next < passengers.length && passengers[next].time === tick) {
    const passenger = passengers[next++];
    waiting[passenger.from].push(passenger); targets.add(passenger.from);
  }
  if (riding[floor].length || waiting[floor].length) {
    stops++;
    for (const passenger of riding[floor]) { passenger.arrive = tick; arrived++; }
    riding[floor] = [];
    targets.delete(floor);
    for (const passenger of waiting[floor]) {
      passenger.board = tick; totalWait += tick - passenger.time;
      riding[passenger.to].push(passenger); targets.add(passenger.to);
    }
    waiting[floor] = [];
    if (arrived === passengers.length) finish = tick;
    continue;
  }
  if (targets.size === 0) {
    direction = 0;
    if (next < passengers.length) tick = passengers[next].time - 1;
    continue;
  }
  let above = false, below = false, nearest = -1, distance = Infinity;
  for (const target of targets) {
    if (target > floor) above = true;
    if (target < floor) below = true;
    const d = Math.abs(target - floor);
    if (d < distance || (d === distance && target > nearest)) { distance = d; nearest = target; }
  }
  if (direction === 0) direction = nearest > floor ? 1 : -1;
  else if (direction === 1 && !above) direction = -1;
  else if (direction === -1 && !below) direction = 1;
  floor += direction; moves++;
}
const output = passengers.map((p, i) => `${i + 1} board=${p.board} arrive=${p.arrive}`);
output.push(`moves=${moves} stops=${stops} finish=${finish} total_wait=${totalWait}`);
process.stdout.write(output.join('\n') + '\n');
