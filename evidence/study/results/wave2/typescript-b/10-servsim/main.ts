import * as fs from "node:fs";

interface Config {
  servers: number;
  queueCap: number;
}

interface Request {
  id: string;
  arrival: number;
  duration: number;
}

interface Server {
  busy: number;
  served: number;
  current: Request | null;
  finishAt: number;
}

const REQUEST_RE = /^([A-Za-z0-9_-]{1,16}) ([0-9]{1,12}) ([0-9]{1,9})$/;

class TraceError extends Error {}

// Binary min-heap with a caller-supplied ordering.
class Heap<T> {
  private readonly items: T[] = [];
  private readonly less: (a: T, b: T) => boolean;

  constructor(less: (a: T, b: T) => boolean) {
    this.less = less;
  }

  get size(): number {
    return this.items.length;
  }

  peek(): T | undefined {
    return this.items[0];
  }

  push(item: T): void {
    const items = this.items;
    items.push(item);
    let i = items.length - 1;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (!this.less(items[i], items[parent])) {
        break;
      }
      [items[parent], items[i]] = [items[i], items[parent]];
      i = parent;
    }
  }

  pop(): T | undefined {
    const items = this.items;
    const top = items[0];
    const last = items.pop();
    if (items.length > 0 && last !== undefined) {
      items[0] = last;
      let i = 0;
      while (true) {
        const left = 2 * i + 1;
        const right = left + 1;
        let smallest = i;
        if (left < items.length && this.less(items[left], items[smallest])) {
          smallest = left;
        }
        if (right < items.length && this.less(items[right], items[smallest])) {
          smallest = right;
        }
        if (smallest === i) {
          break;
        }
        [items[smallest], items[i]] = [items[i], items[smallest]];
        i = smallest;
      }
    }
    return top;
  }
}

function parseArgs(argv: string[]): Config | null {
  let queueCap = Infinity;
  const positional: string[] = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "-q") {
      const value = argv[i + 1];
      if (value === undefined || !/^[0-9]{1,7}$/.test(value)) {
        return null;
      }
      queueCap = Number(value);
      i++;
    } else if (arg.startsWith("-")) {
      return null;
    } else {
      positional.push(arg);
    }
  }
  if (positional.length !== 1 || !/^[0-9]{1,4}$/.test(positional[0])) {
    return null;
  }
  const servers = Number(positional[0]);
  if (servers < 1 || servers > 1000) {
    return null;
  }
  return { servers, queueCap };
}

function parseTrace(text: string): Request[] {
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") {
    lines.pop();
  }
  const requests: Request[] = [];
  const ids = new Set<string>();
  let lastArrival = 0;
  lines.forEach((rawLine, index) => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    if (/^ *$/.test(line)) {
      return;
    }
    const lineNo = index + 1;
    const m = REQUEST_RE.exec(line);
    if (!m) {
      throw new TraceError(`line ${lineNo}: malformed request`);
    }
    const [, id, arrivalText, durationText] = m;
    const arrival = Number(arrivalText);
    const duration = Number(durationText);
    if (duration < 1) {
      throw new TraceError(`line ${lineNo}: duration must be at least 1`);
    }
    if (ids.has(id)) {
      throw new TraceError(`line ${lineNo}: duplicate id ${id}`);
    }
    if (arrival < lastArrival) {
      throw new TraceError(`line ${lineNo}: arrival goes backwards`);
    }
    ids.add(id);
    lastArrival = arrival;
    requests.push({ id, arrival, duration });
  });
  return requests;
}

function simulate(config: Config, requests: Request[]): string[] {
  const out: string[] = [];
  const servers: Server[] = Array.from({ length: config.servers }, () => ({
    busy: 0,
    served: 0,
    current: null,
    finishAt: 0,
  }));
  // Busy servers ordered by finish time, then server number.
  const running = new Heap<number>((a, b) => {
    const fa = servers[a].finishAt;
    const fb = servers[b].finishAt;
    return fa !== fb ? fa < fb : a < b;
  });
  const idle = new Heap<number>((a, b) => a < b);
  for (let k = 0; k < config.servers; k++) {
    idle.push(k);
  }
  const queue: Request[] = [];
  let queueHead = 0;

  let served = 0;
  let rejected = 0;
  let maxWait = 0;
  let totalWait = 0n;
  let makespan = 0;

  const start = (k: number, request: Request, t: number): void => {
    const server = servers[k];
    const wait = t - request.arrival;
    server.current = request;
    server.finishAt = t + request.duration;
    server.busy += request.duration;
    server.served++;
    running.push(k);
    served++;
    maxWait = Math.max(maxWait, wait);
    totalWait += BigInt(wait);
    out.push(`${t} start ${request.id} s${k + 1} wait=${wait}`);
  };

  let next = 0;
  while (next < requests.length || running.size > 0) {
    const nextFinish = running.peek();
    let t = next < requests.length ? requests[next].arrival : Infinity;
    if (nextFinish !== undefined) {
      t = Math.min(t, servers[nextFinish].finishAt);
    }

    while (running.size > 0 && servers[running.peek()!].finishAt === t) {
      const k = running.pop()!;
      const server = servers[k];
      out.push(`${t} done ${server.current!.id} s${k + 1}`);
      server.current = null;
      makespan = t;
      if (queueHead < queue.length) {
        start(k, queue[queueHead++], t);
      } else {
        idle.push(k);
      }
    }

    while (next < requests.length && requests[next].arrival === t) {
      const request = requests[next++];
      if (idle.size > 0) {
        start(idle.pop()!, request, t);
      } else if (queue.length - queueHead < config.queueCap) {
        queue.push(request);
      } else {
        rejected++;
        out.push(`${t} reject ${request.id}`);
      }
    }
  }

  out.push(`served=${served} rejected=${rejected} max_wait=${maxWait} total_wait=${totalWait} makespan=${makespan}`);
  servers.forEach((server, k) => {
    out.push(`s${k + 1} busy=${server.busy} served=${server.served}`);
  });
  return out;
}

function main(argv: string[]): number {
  const config = parseArgs(argv);
  if (config === null) {
    process.stderr.write("usage: servsim [-q CAP] N\n");
    return 2;
  }
  let requests: Request[];
  try {
    requests = parseTrace(fs.readFileSync(0, "latin1"));
  } catch (err) {
    if (err instanceof TraceError) {
      process.stderr.write(`servsim: invalid trace: ${err.message}\n`);
      return 1;
    }
    throw err;
  }
  const lines = simulate(config, requests);
  process.stdout.write(lines.map((line) => line + "\n").join(""));
  return 0;
}

process.exitCode = main(process.argv.slice(2));
