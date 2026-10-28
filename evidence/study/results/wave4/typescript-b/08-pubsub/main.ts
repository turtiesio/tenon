import * as readline from "node:readline";

const CLIENT = /^[a-z][a-z0-9]{0,15}$/;
const SEGMENT = /^[a-z0-9]{1,16}$/;
const TEXT = /^[A-Za-z0-9_.!?-]{1,32}$/;
const MAX = /^[1-9][0-9]{0,2}$/;
const MAX_SEGMENTS = 8;
const MAILBOX_SIZE = 3;
const ARITY = new Map([["SUB", 3], ["UNSUB", 3], ["PUB", 3], ["POLL", 3], ["STATS", 2]]);

function isTopic(s: string): boolean {
  const segs = s.split(".");
  return segs.length <= MAX_SEGMENTS && segs.every((seg) => SEGMENT.test(seg));
}

function isPattern(s: string): boolean {
  const segs = s.split(".");
  if (segs.length > MAX_SEGMENTS) return false;
  return segs.every(
    (seg, i) => SEGMENT.test(seg) || seg === "*" || (seg === "#" && i === segs.length - 1),
  );
}

function matches(pattern: string, topic: string): boolean {
  const p = pattern.split(".");
  const t = topic.split(".");
  let k = p.length;
  if (p[k - 1] === "#") {
    k--;
    if (t.length < k) return false;
  } else if (t.length !== k) {
    return false;
  }
  for (let i = 0; i < k; i++) {
    if (p[i] !== "*" && p[i] !== t[i]) return false;
  }
  return true;
}

interface Client {
  subs: Set<string>;
  mailbox: string[];
  dropped: number;
}

class Broker {
  private readonly clients = new Map<string, Client>();

  private client(name: string): Client {
    let c = this.clients.get(name);
    if (c === undefined) {
      c = { subs: new Set(), mailbox: [], dropped: 0 };
      this.clients.set(name, c);
    }
    return c;
  }

  handle(line: string): string {
    const tok = line.split(" ");
    const [cmd, a, b] = tok;
    if (ARITY.get(cmd) !== tok.length) return "ERR bad command";
    switch (cmd) {
      case "SUB":
        if (!CLIENT.test(a) || !isPattern(b)) break;
        return this.sub(a, b);
      case "UNSUB":
        if (!CLIENT.test(a) || !isPattern(b)) break;
        return this.unsub(a, b);
      case "PUB":
        if (!isTopic(a) || !TEXT.test(b)) break;
        return this.pub(a, b);
      case "POLL":
        if (!CLIENT.test(a) || !MAX.test(b)) break;
        return this.poll(a, Number(b));
      case "STATS": {
        if (!CLIENT.test(a)) break;
        const c = this.client(a);
        return `subs=${c.subs.size} queued=${c.mailbox.length} dropped=${c.dropped}`;
      }
    }
    return "ERR bad command";
  }

  private sub(name: string, pattern: string): string {
    const c = this.client(name);
    if (c.subs.has(pattern)) return "ERR already subscribed";
    c.subs.add(pattern);
    return "OK";
  }

  private unsub(name: string, pattern: string): string {
    return this.client(name).subs.delete(pattern) ? "OK" : "ERR not subscribed";
  }

  private pub(topic: string, text: string): string {
    let delivered = 0;
    for (const c of this.clients.values()) {
      if (![...c.subs].some((p) => matches(p, topic))) continue;
      if (c.mailbox.length >= MAILBOX_SIZE) {
        c.mailbox.shift();
        c.dropped++;
      }
      c.mailbox.push(`${topic}=${text}`);
      delivered++;
    }
    return `DELIVERED ${delivered}`;
  }

  private poll(name: string, max: number): string {
    const taken = this.client(name).mailbox.splice(0, max);
    return ["MSGS " + taken.length, ...taken].join(" ");
  }
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("usage: pubsub\n");
    process.exit(2);
  }
  const broker = new Broker();
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on("line", (raw) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    process.stdout.write(broker.handle(line) + "\n");
  });
}

main();
