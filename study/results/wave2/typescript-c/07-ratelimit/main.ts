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

const NAME_RE = /^[a-z0-9_.-]{1,32}$/;
const TIME_RE = /^[0-9]{1,15}$/;
const COUNT_RE = /^[0-9]{1,9}$/;

const BAD_COMMAND = "ERR bad command";

class RateLimiter {
  private policies = new Map<string, Policy>();
  private clock = 0n;

  handle(line: string): string {
    const tokens = line.split(" ");
    switch (tokens[0]) {
      case "POLICY":
        return this.definePolicy(tokens);
      case "HIT":
        return this.hit(tokens);
      case "PEEK":
        return this.peek(tokens);
      case "RESET":
        return this.reset(tokens);
      case "STATS":
        return this.stats(tokens);
      default:
        return BAD_COMMAND;
    }
  }

  private definePolicy(tokens: string[]): string {
    if (
      tokens.length !== 4 ||
      !NAME_RE.test(tokens[1]) ||
      !COUNT_RE.test(tokens[2]) ||
      !COUNT_RE.test(tokens[3])
    ) {
      return BAD_COMMAND;
    }
    const capacity = BigInt(tokens[2]);
    const interval = BigInt(tokens[3]);
    if (capacity < 1n || interval < 1n) {
      return BAD_COMMAND;
    }
    if (this.policies.has(tokens[1])) {
      return "ERR policy exists";
    }
    this.policies.set(tokens[1], {
      capacity,
      interval,
      allowed: 0,
      denied: 0,
      buckets: new Map(),
    });
    return "OK";
  }

  // Shared by HIT and PEEK: validates, advances the clock, finds the policy
  // and returns the refilled bucket.
  private touch(
    tokens: string[],
    cost: bigint,
  ): { error: string } | { policy: Policy; bucket: Bucket; now: bigint } {
    const now = BigInt(tokens[1]);
    if (now < this.clock) {
      return { error: "ERR time went backwards" };
    }
    this.clock = now;
    const policy = this.policies.get(tokens[2]);
    if (policy === undefined) {
      return { error: "ERR no such policy" };
    }
    if (cost > policy.capacity) {
      return { error: "ERR cost exceeds capacity" };
    }

    let bucket = policy.buckets.get(tokens[3]);
    if (bucket === undefined) {
      bucket = { tokens: policy.capacity, anchor: now };
      policy.buckets.set(tokens[3], bucket);
    }
    if (bucket.tokens === policy.capacity) {
      bucket.anchor = now;
    } else {
      const k = (now - bucket.anchor) / policy.interval;
      const refilled = bucket.tokens + k;
      bucket.tokens = refilled < policy.capacity ? refilled : policy.capacity;
      bucket.anchor =
        bucket.tokens === policy.capacity ? now : bucket.anchor + k * policy.interval;
    }
    return { policy, bucket, now };
  }

  private hit(tokens: string[]): string {
    if (
      (tokens.length !== 4 && tokens.length !== 5) ||
      !TIME_RE.test(tokens[1]) ||
      !NAME_RE.test(tokens[2]) ||
      !NAME_RE.test(tokens[3])
    ) {
      return BAD_COMMAND;
    }
    let cost = 1n;
    if (tokens.length === 5) {
      if (!COUNT_RE.test(tokens[4])) {
        return BAD_COMMAND;
      }
      cost = BigInt(tokens[4]);
      if (cost < 1n) {
        return BAD_COMMAND;
      }
    }
    const result = this.touch(tokens, cost);
    if ("error" in result) {
      return result.error;
    }
    const { policy, bucket, now } = result;
    if (bucket.tokens >= cost) {
      bucket.tokens -= cost;
      policy.allowed++;
      return `ALLOW ${bucket.tokens}`;
    }
    policy.denied++;
    return `DENY ${bucket.anchor + (cost - bucket.tokens) * policy.interval - now}`;
  }

  private peek(tokens: string[]): string {
    if (
      tokens.length !== 4 ||
      !TIME_RE.test(tokens[1]) ||
      !NAME_RE.test(tokens[2]) ||
      !NAME_RE.test(tokens[3])
    ) {
      return BAD_COMMAND;
    }
    const result = this.touch(tokens, 0n);
    if ("error" in result) {
      return result.error;
    }
    return `TOKENS ${result.bucket.tokens}`;
  }

  private reset(tokens: string[]): string {
    if (tokens.length !== 3 || !NAME_RE.test(tokens[1]) || !NAME_RE.test(tokens[2])) {
      return BAD_COMMAND;
    }
    const policy = this.policies.get(tokens[1]);
    if (policy === undefined) {
      return "ERR no such policy";
    }
    if (!policy.buckets.delete(tokens[2])) {
      return "ERR no such client";
    }
    return "OK";
  }

  private stats(tokens: string[]): string {
    if (tokens.length !== 2 || !NAME_RE.test(tokens[1])) {
      return BAD_COMMAND;
    }
    const policy = this.policies.get(tokens[1]);
    if (policy === undefined) {
      return "ERR no such policy";
    }
    return `allowed=${policy.allowed} denied=${policy.denied} clients=${policy.buckets.size}`;
  }
}

function main(): void {
  if (process.argv.length > 2) {
    console.error("usage: rl (no arguments)");
    process.exitCode = 2;
    return;
  }

  const limiter = new RateLimiter();
  let pending = "";

  const respond = (rawLine: string) => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    process.stdout.write(limiter.handle(line) + "\n");
  };

  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let newline = pending.indexOf("\n");
    while (newline >= 0) {
      respond(pending.slice(0, newline));
      pending = pending.slice(newline + 1);
      newline = pending.indexOf("\n");
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") {
      respond(pending);
    }
  });
}

main();
