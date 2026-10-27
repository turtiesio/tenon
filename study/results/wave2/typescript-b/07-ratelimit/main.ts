interface Bucket {
  tokens: bigint;
  anchor: bigint;
}

interface Policy {
  capacity: bigint;
  interval: bigint;
  allowed: number;
  denied: number;
  buckets: Map<string, Bucket>;
}

type Command =
  | { kind: "POLICY"; policy: string; capacity: bigint; interval: bigint }
  | { kind: "HIT"; time: bigint; policy: string; client: string; cost: bigint }
  | { kind: "PEEK"; time: bigint; policy: string; client: string }
  | { kind: "RESET"; policy: string; client: string }
  | { kind: "STATS"; policy: string };

const NAME_RE = /^[a-z0-9_.-]{1,32}$/;
const TIME_RE = /^[0-9]{1,15}$/;
const COUNT_RE = /^[0-9]{1,9}$/;

function isName(s: string): boolean {
  return NAME_RE.test(s);
}

function parseTime(s: string): bigint | null {
  return TIME_RE.test(s) ? BigInt(s) : null;
}

function parsePositive(s: string): bigint | null {
  if (!COUNT_RE.test(s)) {
    return null;
  }
  const n = BigInt(s);
  return n >= 1n ? n : null;
}

function parseCommand(line: string): Command | null {
  const tokens = line.split(" ");
  const [name, ...args] = tokens;
  switch (name) {
    case "POLICY": {
      if (args.length !== 3 || !isName(args[0])) {
        return null;
      }
      const capacity = parsePositive(args[1]);
      const interval = parsePositive(args[2]);
      if (capacity === null || interval === null) {
        return null;
      }
      return { kind: "POLICY", policy: args[0], capacity, interval };
    }
    case "HIT": {
      if (args.length !== 3 && args.length !== 4) {
        return null;
      }
      const time = parseTime(args[0]);
      const cost = args.length === 4 ? parsePositive(args[3]) : 1n;
      if (time === null || cost === null || !isName(args[1]) || !isName(args[2])) {
        return null;
      }
      return { kind: "HIT", time, policy: args[1], client: args[2], cost };
    }
    case "PEEK": {
      if (args.length !== 3) {
        return null;
      }
      const time = parseTime(args[0]);
      if (time === null || !isName(args[1]) || !isName(args[2])) {
        return null;
      }
      return { kind: "PEEK", time, policy: args[1], client: args[2] };
    }
    case "RESET":
      if (args.length !== 2 || !isName(args[0]) || !isName(args[1])) {
        return null;
      }
      return { kind: "RESET", policy: args[0], client: args[1] };
    case "STATS":
      if (args.length !== 1 || !isName(args[0])) {
        return null;
      }
      return { kind: "STATS", policy: args[0] };
    default:
      return null;
  }
}

function minBig(a: bigint, b: bigint): bigint {
  return a < b ? a : b;
}

class RateLimiter {
  private clock = 0n;
  private readonly policies = new Map<string, Policy>();

  handle(line: string): string {
    const command = parseCommand(line);
    if (command === null) {
      return "ERR bad command";
    }
    if (command.kind === "HIT" || command.kind === "PEEK") {
      if (command.time < this.clock) {
        return "ERR time went backwards";
      }
      this.clock = command.time;
    }

    if (command.kind === "POLICY") {
      if (this.policies.has(command.policy)) {
        return "ERR policy exists";
      }
      this.policies.set(command.policy, {
        capacity: command.capacity,
        interval: command.interval,
        allowed: 0,
        denied: 0,
        buckets: new Map(),
      });
      return "OK";
    }

    const policy = this.policies.get(command.policy);
    if (policy === undefined) {
      return "ERR no such policy";
    }

    switch (command.kind) {
      case "HIT": {
        if (command.cost > policy.capacity) {
          return "ERR cost exceeds capacity";
        }
        const bucket = this.refill(policy, command.client, command.time);
        if (bucket.tokens >= command.cost) {
          bucket.tokens -= command.cost;
          policy.allowed++;
          return `ALLOW ${bucket.tokens}`;
        }
        policy.denied++;
        const retryAfter = bucket.anchor + (command.cost - bucket.tokens) * policy.interval - command.time;
        return `DENY ${retryAfter}`;
      }
      case "PEEK":
        return `TOKENS ${this.refill(policy, command.client, command.time).tokens}`;
      case "RESET":
        if (!policy.buckets.delete(command.client)) {
          return "ERR no such client";
        }
        return "OK";
      case "STATS":
        return `allowed=${policy.allowed} denied=${policy.denied} clients=${policy.buckets.size}`;
    }
  }

  // Returns the client's bucket, created if needed and refilled up to `now`.
  private refill(policy: Policy, client: string, now: bigint): Bucket {
    let bucket = policy.buckets.get(client);
    if (bucket === undefined) {
      bucket = { tokens: policy.capacity, anchor: now };
      policy.buckets.set(client, bucket);
    }
    if (bucket.tokens === policy.capacity) {
      bucket.anchor = now;
      return bucket;
    }
    const k = (now - bucket.anchor) / policy.interval;
    bucket.tokens = minBig(policy.capacity, bucket.tokens + k);
    if (bucket.tokens === policy.capacity) {
      bucket.anchor = now;
    } else {
      bucket.anchor += k * policy.interval;
    }
    return bucket;
  }
}

function main(argv: string[]): void {
  if (argv.length > 0) {
    process.stderr.write("usage: rl (takes no arguments)\n");
    process.exitCode = 2;
    return;
  }

  const limiter = new RateLimiter();
  const respond = (rawLine: string): void => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    process.stdout.write(limiter.handle(line) + "\n");
  };

  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let start = 0;
    let newline = pending.indexOf("\n", start);
    while (newline >= 0) {
      respond(pending.slice(start, newline));
      start = newline + 1;
      newline = pending.indexOf("\n", start);
    }
    pending = pending.slice(start);
  });
  process.stdin.on("end", () => {
    if (pending !== "") {
      respond(pending);
    }
  });
}

main(process.argv.slice(2));
