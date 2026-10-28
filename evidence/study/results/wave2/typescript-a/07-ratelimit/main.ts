import { createInterface } from 'node:readline';

if (process.argv.length !== 2) {
  console.error('No arguments expected');
  process.exit(2);
}
type Bucket = { tokens: bigint; anchor: bigint };
type Policy = { capacity: bigint; interval: bigint; allowed: number; denied: number; buckets: Map<string, Bucket> };
const policies = new Map<string, Policy>();
let clock = 0n;
const name = '[a-z0-9_.-]{1,32}';
const positive = '[0-9]{1,9}';
const patterns = {
  POLICY: new RegExp(`^POLICY (${name}) (${positive}) (${positive})$`),
  HIT: new RegExp(`^HIT ([0-9]{1,15}) (${name}) (${name})(?: (${positive}))?$`),
  PEEK: new RegExp(`^PEEK ([0-9]{1,15}) (${name}) (${name})$`),
  RESET: new RegExp(`^RESET (${name}) (${name})$`),
  STATS: new RegExp(`^STATS (${name})$`),
};
function respond(line: string): string {
  const command = line.split(' ')[0] as keyof typeof patterns;
  const match = Object.hasOwn(patterns, command) ? patterns[command].exec(line) : null;
  if (!match) return 'ERR bad command';
  if (command === 'POLICY' && (BigInt(match[2]) === 0n || BigInt(match[3]) === 0n)) return 'ERR bad command';
  if (command === 'HIT' && match[4] !== undefined && BigInt(match[4]) === 0n) return 'ERR bad command';
  const timed = command === 'HIT' || command === 'PEEK';
  const now = timed ? BigInt(match[1]) : clock;
  if (timed) {
    if (now < clock) return 'ERR time went backwards';
    clock = now;
  }
  const policyName = match[timed ? 2 : 1];
  if (command === 'POLICY') {
    if (policies.has(policyName)) return 'ERR policy exists';
    policies.set(policyName, { capacity: BigInt(match[2]), interval: BigInt(match[3]), allowed: 0, denied: 0, buckets: new Map() });
    return 'OK';
  }
  const policy = policies.get(policyName);
  if (!policy) return 'ERR no such policy';
  const cost = command === 'HIT' ? BigInt(match[4] ?? '1') : 0n;
  if (cost > policy.capacity) return 'ERR cost exceeds capacity';
  if (command === 'STATS') return `allowed=${policy.allowed} denied=${policy.denied} clients=${policy.buckets.size}`;
  const client = match[timed ? 3 : 2];
  if (command === 'RESET') return policy.buckets.delete(client) ? 'OK' : 'ERR no such client';
  const bucket = policy.buckets.get(client) ?? { tokens: policy.capacity, anchor: now };
  policy.buckets.set(client, bucket);
  if (bucket.tokens === policy.capacity) bucket.anchor = now;
  else {
    const k = (now - bucket.anchor) / policy.interval;
    bucket.tokens += k;
    if (bucket.tokens >= policy.capacity) {
      bucket.tokens = policy.capacity;
      bucket.anchor = now;
    } else bucket.anchor += k * policy.interval;
  }
  if (command === 'PEEK') return `TOKENS ${bucket.tokens}`;
  if (bucket.tokens >= cost) {
    bucket.tokens -= cost;
    policy.allowed++;
    return `ALLOW ${bucket.tokens}`;
  }
  policy.denied++;
  return `DENY ${bucket.anchor + (cost - bucket.tokens) * policy.interval - now}`;
}
const input = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) process.stdout.write(respond(line.replace(/\r$/, '')) + '\n');
