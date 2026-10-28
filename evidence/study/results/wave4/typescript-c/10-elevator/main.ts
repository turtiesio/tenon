import * as fs from "node:fs";

const REQUEST = /^([0-9]{1,6}) ([0-9]{1,3}) ([0-9]{1,3})$/;

type Direction = "up" | "down" | "idle";

interface Request {
  time: number;
  from: number;
  to: number;
}

interface Result {
  board: number[];
  arrive: number[];
  moves: number;
  stops: number;
  finish: number;
  totalWait: number;
}

// Returns the requests, or a message describing the first problem.
function parseRequests(text: string, floors: number): Request[] | string {
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  const requests: Request[] = [];
  for (let line of lines) {
    if (line.endsWith("\r")) line = line.slice(0, -1);
    if (/^ *$/.test(line)) continue;
    const m = REQUEST.exec(line);
    if (m === null) return `bad request line: ${JSON.stringify(line)}`;
    const req: Request = { time: Number(m[1]), from: Number(m[2]), to: Number(m[3]) };
    if (req.from >= floors || req.to >= floors) return `floor out of range: ${line}`;
    if (req.from === req.to) return `from equals to: ${line}`;
    const prev = requests[requests.length - 1];
    if (prev !== undefined && req.time < prev.time) return `time goes backwards: ${line}`;
    requests.push(req);
  }
  return requests;
}

function chooseDirection(floor: number, current: Direction, targets: number[]): Direction {
  if (!targets.some((n) => n > 0)) return "idle";
  const above = targets.slice(floor + 1).some((n) => n > 0);
  const below = targets.slice(0, floor).some((n) => n > 0);
  if (current === "up") return above ? "up" : "down";
  if (current === "down") return below ? "down" : "up";
  // Idle: head for the nearest target floor; a tie goes up.
  for (let d = 1; d < targets.length; d++) {
    if (floor + d < targets.length && targets[floor + d] > 0) return "up";
    if (floor - d >= 0 && targets[floor - d] > 0) return "down";
  }
  return "idle"; // unreachable: some target exists and none is on this floor
}

function simulate(requests: Request[], floors: number): Result {
  const n = requests.length;
  const result: Result = {
    board: new Array<number>(n).fill(0),
    arrive: new Array<number>(n).fill(0),
    moves: 0,
    stops: 0,
    finish: 0,
    totalWait: 0,
  };
  if (n === 0) return result;

  // Per floor: passengers waiting there, passengers on board bound for it.
  const waiting: number[][] = Array.from({ length: floors }, () => []);
  const riding: number[][] = Array.from({ length: floors }, () => []);
  // Number of passengers (waiting or riding) that make each floor a target.
  const targets = new Array<number>(floors).fill(0);

  let floor = 0;
  let direction: Direction = "idle";
  let nextRequest = 0;
  let arrived = 0;

  for (let tick = 0; arrived < n; tick++) {
    while (nextRequest < n && requests[nextRequest].time === tick) {
      const r = requests[nextRequest];
      waiting[r.from].push(nextRequest);
      targets[r.from]++;
      nextRequest++;
    }

    if (riding[floor].length > 0 || waiting[floor].length > 0) {
      result.stops++;
      for (const p of riding[floor]) {
        result.arrive[p] = tick;
        arrived++;
      }
      targets[floor] -= riding[floor].length;
      riding[floor] = [];
      for (const p of waiting[floor]) {
        result.board[p] = tick;
        result.totalWait += tick - requests[p].time;
        riding[requests[p].to].push(p);
        targets[requests[p].to]++;
      }
      targets[floor] -= waiting[floor].length;
      waiting[floor] = [];
      result.finish = tick;
      continue;
    }

    direction = chooseDirection(floor, direction, targets);
    if (direction === "up") floor++;
    else if (direction === "down") floor--;
    if (direction !== "idle") result.moves++;
  }
  return result;
}

function main(): number {
  const args = process.argv.slice(2);
  if (args.length !== 1 || !/^[0-9]{1,3}$/.test(args[0]) || Number(args[0]) < 2 || Number(args[0]) > 100) {
    console.error("usage: elevator FLOORS (2-100)");
    return 2;
  }
  const floors = Number(args[0]);

  let text: string;
  try {
    text = fs.readFileSync(0, "latin1");
  } catch {
    text = "";
  }
  const requests = parseRequests(text, floors);
  if (typeof requests === "string") {
    console.error(`elevator: ${requests}`);
    return 1;
  }

  const r = simulate(requests, floors);
  const out = requests.map((_, i) => `${i + 1} board=${r.board[i]} arrive=${r.arrive[i]}\n`);
  out.push(`moves=${r.moves} stops=${r.stops} finish=${r.finish} total_wait=${r.totalWait}\n`);
  process.stdout.write(out.join(""));
  return 0;
}

process.exitCode = main();
