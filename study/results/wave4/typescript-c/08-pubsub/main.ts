const MAILBOX_LIMIT = 3;

const CLIENT = /^[a-z][a-z0-9]{0,15}$/;
const SEGMENT = /^[a-z0-9]{1,16}$/;
const TEXT = /^[A-Za-z0-9_.!?-]{1,32}$/;
const MAX = /^[1-9][0-9]{0,2}$/;

function validTopic(topic: string): boolean {
  const segments = topic.split(".");
  return segments.length <= 8 && segments.every((s) => SEGMENT.test(s));
}

function validPattern(pattern: string): boolean {
  const segments = pattern.split(".");
  if (segments.length > 8) return false;
  return segments.every(
    (s, i) => SEGMENT.test(s) || s === "*" || (s === "#" && i === segments.length - 1),
  );
}

function matches(pattern: string, topic: string): boolean {
  const p = pattern.split(".");
  const t = topic.split(".");
  const multi = p[p.length - 1] === "#";
  const fixed = multi ? p.length - 1 : p.length;
  if (multi ? t.length < fixed : t.length !== fixed) return false;
  for (let i = 0; i < fixed; i++) {
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

  // Every client name implicitly exists; create the record on first use.
  private client(name: string): Client {
    let c = this.clients.get(name);
    if (c === undefined) {
      c = { subs: new Set(), mailbox: [], dropped: 0 };
      this.clients.set(name, c);
    }
    return c;
  }

  handle(line: string): string {
    const tokens = line.split(" ");
    const [cmd, a, b] = tokens;
    switch (cmd) {
      case "SUB":
        if (tokens.length === 3 && CLIENT.test(a) && validPattern(b)) return this.subscribe(a, b);
        break;
      case "UNSUB":
        if (tokens.length === 3 && CLIENT.test(a) && validPattern(b)) return this.unsubscribe(a, b);
        break;
      case "PUB":
        if (tokens.length === 3 && validTopic(a) && TEXT.test(b)) return this.publish(a, b);
        break;
      case "POLL":
        if (tokens.length === 3 && CLIENT.test(a) && MAX.test(b)) return this.poll(a, Number(b));
        break;
      case "STATS":
        if (tokens.length === 2 && CLIENT.test(a)) return this.stats(a);
        break;
    }
    return "ERR bad command";
  }

  private subscribe(name: string, pattern: string): string {
    const c = this.client(name);
    if (c.subs.has(pattern)) return "ERR already subscribed";
    c.subs.add(pattern);
    return "OK";
  }

  private unsubscribe(name: string, pattern: string): string {
    return this.client(name).subs.delete(pattern) ? "OK" : "ERR not subscribed";
  }

  private publish(topic: string, text: string): string {
    let delivered = 0;
    for (const c of this.clients.values()) {
      if (![...c.subs].some((p) => matches(p, topic))) continue;
      if (c.mailbox.length >= MAILBOX_LIMIT) {
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
    return [`MSGS ${taken.length}`, ...taken].join(" ");
  }

  private stats(name: string): string {
    const c = this.client(name);
    return `subs=${c.subs.size} queued=${c.mailbox.length} dropped=${c.dropped}`;
  }
}

function main(): void {
  if (process.argv.length > 2) {
    console.error("pubsub: takes no arguments");
    process.exitCode = 2;
    return;
  }
  const broker = new Broker();

  const respond = (rawLine: string): void => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    process.stdout.write(broker.handle(line) + "\n");
  };

  // Split on "\n" by hand and answer each line as soon as it is complete.
  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let nl = pending.indexOf("\n");
    while (nl >= 0) {
      respond(pending.slice(0, nl));
      pending = pending.slice(nl + 1);
      nl = pending.indexOf("\n");
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") respond(pending);
  });
}

main();
