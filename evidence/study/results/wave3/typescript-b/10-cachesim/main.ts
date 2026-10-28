import * as fs from "node:fs";

class UsageError extends Error {}
class TraceError extends Error {}

interface Geometry {
  sets: number;
  ways: number;
}

interface Options {
  block: number;
  l1: Geometry;
  l2: Geometry;
}

interface Access {
  text: string;
  write: boolean;
  address: number;
}

function parseBlock(text: string): number {
  if (!/^[0-9]{1,4}$/.test(text)) throw new UsageError(`malformed block size: ${text}`);
  const n = Number(text);
  if (n < 1 || n > 4096 || (n & (n - 1)) !== 0) throw new UsageError(`block size must be a power of two from 1 to 4096: ${text}`);
  return n;
}

function parseGeometry(text: string): Geometry {
  const m = /^([0-9]{1,4}):([0-9]{1,2})$/.exec(text);
  if (!m) throw new UsageError(`malformed geometry: ${text}`);
  const sets = Number(m[1]);
  const ways = Number(m[2]);
  if (sets < 1 || sets > 4096) throw new UsageError(`sets out of range: ${text}`);
  if (ways < 1 || ways > 64) throw new UsageError(`ways out of range: ${text}`);
  return { sets, ways };
}

function parseArgs(args: string[]): Options {
  const opts: Options = { block: 16, l1: { sets: 4, ways: 2 }, l2: { sets: 16, ways: 4 } };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg !== "-b" && arg !== "-1" && arg !== "-2") throw new UsageError(`unexpected argument: ${arg}`);
    if (i + 1 >= args.length) throw new UsageError(`${arg} requires a value`);
    const value = args[++i];
    if (arg === "-b") opts.block = parseBlock(value);
    else if (arg === "-1") opts.l1 = parseGeometry(value);
    else opts.l2 = parseGeometry(value);
  }
  return opts;
}

function readTrace(): Access[] {
  const text = fs.readFileSync(0, "latin1");
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  const accesses: Access[] = [];
  lines.forEach((raw, i) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (/^ *$/.test(line)) return;
    const m = /^([RW]) 0x([0-9A-Fa-f]{1,8})$/.exec(line);
    if (!m) throw new TraceError(`line ${i + 1}: invalid access: ${line}`);
    accesses.push({ text: line, write: m[1] === "W", address: parseInt(m[2], 16) });
  });
  return accesses;
}

interface Victim {
  block: number;
  dirty: boolean;
}

/** A set-associative LRU cache. Each set maps block -> dirty, in LRU-to-MRU order. */
class Cache {
  hits = 0;
  misses = 0;
  writebacks = 0;
  private readonly geometry: Geometry;
  private readonly sets: Array<Map<number, boolean>>;

  constructor(geometry: Geometry) {
    this.geometry = geometry;
    this.sets = Array.from({ length: geometry.sets }, () => new Map<number, boolean>());
  }

  private setOf(block: number): Map<number, boolean> {
    return this.sets[block % this.geometry.sets];
  }

  has(block: number): boolean {
    return this.setOf(block).has(block);
  }

  /** Makes a held block MRU, optionally marking it dirty. */
  touch(block: number, makeDirty: boolean): void {
    const set = this.setOf(block);
    const dirty = set.get(block)! || makeDirty;
    set.delete(block);
    set.set(block, dirty);
  }

  /** Installs a block as MRU, returning the evicted LRU block if the set was full. */
  install(block: number, dirty: boolean): Victim | undefined {
    const set = this.setOf(block);
    let victim: Victim | undefined;
    if (set.size >= this.geometry.ways) {
      const [lru, lruDirty] = set.entries().next().value!;
      set.delete(lru);
      victim = { block: lru, dirty: lruDirty };
    }
    set.set(block, dirty);
    return victim;
  }

  summary(name: string): string {
    return `${name} hits=${this.hits} misses=${this.misses} writebacks=${this.writebacks}\n`;
  }
}

class Hierarchy {
  readonly l1: Cache;
  readonly l2: Cache;

  constructor(opts: Options) {
    this.l1 = new Cache(opts.l1);
    this.l2 = new Cache(opts.l2);
  }

  private installL2(block: number, dirty: boolean): void {
    const victim = this.l2.install(block, dirty);
    if (victim?.dirty) this.l2.writebacks++;
  }

  access(block: number, write: boolean): "L1" | "L2" | "MEM" {
    if (this.l1.has(block)) {
      this.l1.hits++;
      this.l1.touch(block, write);
      return "L1";
    }
    this.l1.misses++;
    let result: "L2" | "MEM";
    if (this.l2.has(block)) {
      this.l2.hits++;
      this.l2.touch(block, false);
      result = "L2";
    } else {
      this.l2.misses++;
      this.installL2(block, false);
      result = "MEM";
    }
    const victim = this.l1.install(block, write);
    if (victim?.dirty) {
      this.l1.writebacks++;
      if (this.l2.has(victim.block)) this.l2.touch(victim.block, true);
      else this.installL2(victim.block, true);
    }
    return result;
  }
}

function main(): number {
  try {
    const opts = parseArgs(process.argv.slice(2));
    const trace = readTrace();
    const hierarchy = new Hierarchy(opts);
    const out: string[] = [];
    for (const access of trace) {
      const result = hierarchy.access(Math.floor(access.address / opts.block), access.write);
      out.push(`${access.text} ${result}\n`);
    }
    out.push(hierarchy.l1.summary("L1"), hierarchy.l2.summary("L2"));
    process.stdout.write(out.join(""));
    return 0;
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`cachesim: ${e.message}\nusage: cachesim [-b BLOCK] [-1 SETS:WAYS] [-2 SETS:WAYS]\n`);
      return 2;
    }
    if (e instanceof TraceError) {
      process.stderr.write(`cachesim: ${e.message}\n`);
      return 1;
    }
    throw e;
  }
}

process.exitCode = main();
