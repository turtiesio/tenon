import { readFileSync } from "node:fs";

interface Request {
  id: string;
  arrival: number;
  duration: number;
}

interface Server {
  busy: number;
  served: number;
}

class MinHeap<T> {
  private items: T[] = [];
  private readonly less: (a: T, b: T) => boolean;

  constructor(less: (a: T, b: T) => boolean) {
    this.less = less;
  }

  get size(): number {
    return this.items.length;
  }

  peek(): T {
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

  pop(): T {
    const items = this.items;
    const top = items[0];
    const last = items.pop()!;
    if (items.length > 0) {
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

const LINE_RE = /^([A-Za-z0-9_-]{1,16}) ([0-9]{1,12}) ([0-9]{1,9})$/;

function parseArgs(args: string[]): { servers: number; capacity: number } | null {
  let servers: number | null = null;
  let capacity = Infinity;
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-q") {
      const value = args[++i];
      if (value === undefined || !/^[0-9]{1,7}$/.test(value)) {
        return null;
      }
      capacity = Number(value);
    } else if (arg.startsWith("-") || servers !== null) {
      return null;
    } else if (/^[0-9]{1,4}$/.test(arg) && Number(arg) >= 1 && Number(arg) <= 1000) {
      servers = Number(arg);
    } else {
      return null;
    }
  }
  return servers === null ? null : { servers, capacity };
}

// Returns the requests, or an error message if the trace is invalid.
function parseTrace(text: string): Request[] | string {
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") {
    lines.pop();
  }
  const requests: Request[] = [];
  const ids = new Set<string>();
  let lastArrival = 0;
  for (let [index, line] of lines.entries()) {
    if (line.endsWith("\r")) {
      line = line.slice(0, -1);
    }
    if (/^ *$/.test(line)) {
      continue;
    }
    const match = LINE_RE.exec(line);
    if (match === null || Number(match[3]) < 1) {
      return `line ${index + 1}: malformed request`;
    }
    const request = { id: match[1], arrival: Number(match[2]), duration: Number(match[3]) };
    if (ids.has(request.id)) {
      return `line ${index + 1}: duplicate id ${request.id}`;
    }
    if (request.arrival < lastArrival) {
      return `line ${index + 1}: arrival goes backwards`;
    }
    ids.add(request.id);
    lastArrival = request.arrival;
    requests.push(request);
  }
  return requests;
}

function main(): number {
  const config = parseArgs(process.argv.slice(2));
  if (config === null) {
    console.error("usage: servsim [-q CAP] N");
    return 2;
  }
  const trace = parseTrace(readFileSync(0, "latin1"));
  if (typeof trace === "string") {
    console.error(trace);
    return 1;
  }

  const servers: Server[] = Array.from({ length: config.servers }, () => ({ busy: 0, served: 0 }));
  // Running servers ordered by (finish time, server number); idle servers by number.
  const running = new MinHeap<{ finish: number; server: number; id: string }>(
    (a, b) => a.finish < b.finish || (a.finish === b.finish && a.server < b.server),
  );
  const idle = new MinHeap<number>((a, b) => a < b);
  for (let k = 0; k < config.servers; k++) {
    idle.push(k);
  }

  const out: string[] = [];
  const queue: Request[] = [];
  let queueHead = 0;
  let next = 0;
  let served = 0;
  let rejected = 0;
  let maxWait = 0;
  let totalWait = 0;
  let makespan = 0;

  const start = (request: Request, server: number, now: number) => {
    const wait = now - request.arrival;
    out.push(`${now} start ${request.id} s${server + 1} wait=${wait}`);
    running.push({ finish: now + request.duration, server, id: request.id });
    servers[server].busy += request.duration;
    servers[server].served++;
    served++;
    totalWait += wait;
    maxWait = Math.max(maxWait, wait);
  };

  while (next < trace.length || running.size > 0) {
    const nextFinish = running.size > 0 ? running.peek().finish : Infinity;
    const nextArrival = next < trace.length ? trace[next].arrival : Infinity;
    const now = Math.min(nextFinish, nextArrival);

    while (running.size > 0 && running.peek().finish === now) {
      const done = running.pop();
      out.push(`${now} done ${done.id} s${done.server + 1}`);
      makespan = now;
      if (queueHead < queue.length) {
        start(queue[queueHead++], done.server, now);
      } else {
        idle.push(done.server);
      }
    }

    while (next < trace.length && trace[next].arrival === now) {
      const request = trace[next++];
      if (idle.size > 0) {
        start(request, idle.pop(), now);
      } else if (queue.length - queueHead < config.capacity) {
        queue.push(request);
      } else {
        rejected++;
        out.push(`${now} reject ${request.id}`);
      }
    }
  }

  out.push(
    `served=${served} rejected=${rejected} max_wait=${maxWait} total_wait=${totalWait} makespan=${makespan}`,
  );
  servers.forEach((server, k) => {
    out.push(`s${k + 1} busy=${server.busy} served=${server.served}`);
  });
  process.stdout.write(out.join("\n") + "\n");
  return 0;
}

process.exitCode = main();
