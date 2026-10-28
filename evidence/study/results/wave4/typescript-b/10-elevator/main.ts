import * as fs from "node:fs";

interface Passenger {
  time: number;
  from: number;
  to: number;
  board: number;
  arrive: number;
}

type Direction = "up" | "down" | "idle";

function parseFloors(args: string[]): number {
  if (args.length === 1 && /^[0-9]{1,3}$/.test(args[0])) {
    const n = Number(args[0]);
    if (n >= 2 && n <= 100) return n;
  }
  process.stderr.write("usage: elevator FLOORS   (2-100)\n");
  process.exit(2);
}

function invalid(lineNo: number, msg: string): never {
  process.stderr.write(`elevator: line ${lineNo}: ${msg}\n`);
  process.exit(1);
}

function readRequests(floors: number): Passenger[] {
  const passengers: Passenger[] = [];
  const lines = fs.readFileSync(0, "latin1").split("\n");
  lines.forEach((raw, i) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (/^ *$/.test(line)) return;
    const m = /^([0-9]{1,6}) ([0-9]{1,3}) ([0-9]{1,3})$/.exec(line);
    if (m === null) invalid(i + 1, "expected '<time> <from> <to>'");
    const [time, from, to] = [Number(m[1]), Number(m[2]), Number(m[3])];
    if (from >= floors || to >= floors) invalid(i + 1, "no such floor");
    if (from === to) invalid(i + 1, "from and to are the same floor");
    const prev = passengers[passengers.length - 1];
    if (prev !== undefined && time < prev.time) invalid(i + 1, "time goes backwards");
    passengers.push({ time, from, to, board: -1, arrive: -1 });
  });
  return passengers;
}

function chooseDirection(dir: Direction, floor: number, targets: number[]): Direction {
  let above = false;
  let below = false;
  let nearestAbove = Infinity;
  let nearestBelow = Infinity;
  targets.forEach((count, f) => {
    if (count === 0) return;
    if (f > floor) {
      above = true;
      nearestAbove = Math.min(nearestAbove, f - floor);
    } else if (f < floor) {
      below = true;
      nearestBelow = Math.min(nearestBelow, floor - f);
    }
  });
  if (dir === "up") return above ? "up" : "down";
  if (dir === "down") return below ? "down" : "up";
  return nearestAbove <= nearestBelow ? "up" : "down";
}

function simulate(passengers: Passenger[], floors: number): string[] {
  const waiting: Passenger[][] = Array.from({ length: floors }, () => []);
  const riding: Passenger[][] = Array.from({ length: floors }, () => []);
  // targets[f] = waiting passengers on f + riding passengers bound for f
  const targets = new Array<number>(floors).fill(0);
  let pending = 0; // waiting or riding
  let next = 0; // index of the next passenger to appear
  let arrived = 0;

  let floor = 0;
  let dir: Direction = "idle";
  let moves = 0;
  let stops = 0;
  let finish = 0;

  for (let t = 0; arrived < passengers.length; t++) {
    if (pending === 0 && passengers[next].time > t) {
      // Nothing to do until the next passenger appears.
      dir = "idle";
      t = passengers[next].time;
    }
    while (next < passengers.length && passengers[next].time === t) {
      const p = passengers[next++];
      waiting[p.from].push(p);
      targets[p.from]++;
      pending++;
    }

    if (targets[floor] > 0) {
      stops++;
      for (const p of riding[floor]) {
        p.arrive = t;
        arrived++;
        pending--;
      }
      targets[floor] -= riding[floor].length;
      riding[floor] = [];
      for (const p of waiting[floor]) {
        p.board = t;
        riding[p.to].push(p);
        targets[p.to]++;
      }
      targets[floor] -= waiting[floor].length;
      waiting[floor] = [];
      finish = t;
    } else if (pending === 0) {
      dir = "idle";
    } else {
      dir = chooseDirection(dir, floor, targets);
      floor += dir === "up" ? 1 : -1;
      moves++;
    }
  }

  const out = passengers.map((p, i) => `${i + 1} board=${p.board} arrive=${p.arrive}`);
  const totalWait = passengers.reduce((sum, p) => sum + (p.board - p.time), 0);
  out.push(`moves=${moves} stops=${stops} finish=${finish} total_wait=${totalWait}`);
  return out;
}

function main(): void {
  const floors = parseFloors(process.argv.slice(2));
  const passengers = readRequests(floors);
  const out = simulate(passengers, floors);
  process.stdout.write(out.map((l) => l + "\n").join(""));
}

main();
