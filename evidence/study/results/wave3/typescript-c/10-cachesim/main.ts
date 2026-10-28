import { readFileSync } from "node:fs";

class UsageError extends Error {}
class TraceError extends Error {}

interface Geometry {
  sets: number;
  ways: number;
}

interface Config {
  blockSize: number;
  l1: Geometry;
  l2: Geometry;
}

interface Access {
  op: "R" | "W";
  addressText: string;
  address: number;
}

interface Line {
  block: number;
  dirty: boolean;
}

function parseGeometry(option: string, text: string): Geometry {
  const m = text.match(/^([0-9]{1,4}):([0-9]{1,2})$/);
  if (!m) throw new UsageError(`bad geometry for ${option}: ${text}`);
  const sets = Number(m[1]);
  const ways = Number(m[2]);
  if (sets < 1 || sets > 4096 || ways < 1 || ways > 64) {
    throw new UsageError(`geometry out of range for ${option}: ${text}`);
  }
  return { sets, ways };
}

function parseArgs(args: string[]): Config {
  const config: Config = {
    blockSize: 16,
    l1: { sets: 4, ways: 2 },
    l2: { sets: 16, ways: 4 },
  };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg !== "-b" && arg !== "-1" && arg !== "-2") {
      throw new UsageError(`unexpected argument: ${arg}`);
    }
    if (i + 1 >= args.length) throw new UsageError(`${arg} needs an argument`);
    const value = args[++i];
    if (arg === "-b") {
      if (!/^[0-9]{1,4}$/.test(value)) throw new UsageError(`bad block size: ${value}`);
      const size = Number(value);
      if (size < 1 || size > 4096 || (size & (size - 1)) !== 0) {
        throw new UsageError(`block size must be a power of two up to 4096: ${value}`);
      }
      config.blockSize = size;
    } else if (arg === "-1") {
      config.l1 = parseGeometry(arg, value);
    } else {
      config.l2 = parseGeometry(arg, value);
    }
  }
  return config;
}

function parseTrace(text: string): Access[] {
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  const accesses: Access[] = [];
  lines.forEach((raw, index) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line.trim() === "") return;
    const m = line.match(/^([RW]) 0x([0-9a-fA-F]{1,8})$/);
    if (!m) throw new TraceError(`line ${index + 1}: invalid access`);
    accesses.push({
      op: m[1] as "R" | "W",
      addressText: `${m[1]} 0x${m[2]}`,
      address: parseInt(m[2], 16),
    });
  });
  return accesses;
}

// One set-associative LRU cache. Each set is ordered from LRU to MRU.
class Cache {
  hits = 0;
  misses = 0;
  writebacks = 0;
  private readonly sets: Line[][];
  private readonly ways: number;

  constructor(geometry: Geometry) {
    this.sets = Array.from({ length: geometry.sets }, () => []);
    this.ways = geometry.ways;
  }

  private setOf(block: number): Line[] {
    return this.sets[block % this.sets.length];
  }

  // Looks the block up; if present, makes it MRU and returns it.
  touch(block: number): Line | undefined {
    const set = this.setOf(block);
    const index = set.findIndex((line) => line.block === block);
    if (index < 0) return undefined;
    const [line] = set.splice(index, 1);
    set.push(line);
    return line;
  }

  // Adds the block as MRU, returning the evicted LRU line if the set was full.
  install(block: number, dirty: boolean): Line | undefined {
    const set = this.setOf(block);
    const victim = set.length >= this.ways ? set.shift() : undefined;
    set.push({ block, dirty });
    return victim;
  }
}

class Hierarchy {
  readonly l1: Cache;
  readonly l2: Cache;

  constructor(config: Config) {
    this.l1 = new Cache(config.l1);
    this.l2 = new Cache(config.l2);
  }

  private installL2(block: number, dirty: boolean): void {
    const victim = this.l2.install(block, dirty);
    if (victim?.dirty) this.l2.writebacks++;
  }

  private writeBackToL2(block: number): void {
    this.l1.writebacks++;
    const line = this.l2.touch(block);
    if (line) line.dirty = true;
    else this.installL2(block, true);
  }

  access(block: number, write: boolean): "L1" | "L2" | "MEM" {
    const hit = this.l1.touch(block);
    if (hit) {
      this.l1.hits++;
      if (write) hit.dirty = true;
      return "L1";
    }
    this.l1.misses++;
    let result: "L2" | "MEM";
    if (this.l2.touch(block)) {
      this.l2.hits++;
      result = "L2";
    } else {
      this.l2.misses++;
      this.installL2(block, false);
      result = "MEM";
    }
    const victim = this.l1.install(block, write);
    if (victim?.dirty) this.writeBackToL2(victim.block);
    return result;
  }
}

function main(): number {
  try {
    const config = parseArgs(process.argv.slice(2));
    const accesses = parseTrace(readFileSync(0).toString("latin1"));
    const cache = new Hierarchy(config);
    const out: string[] = [];
    for (const { op, addressText, address } of accesses) {
      const block = Math.floor(address / config.blockSize);
      out.push(`${addressText} ${cache.access(block, op === "W")}`);
    }
    const { l1, l2 } = cache;
    out.push(`L1 hits=${l1.hits} misses=${l1.misses} writebacks=${l1.writebacks}`);
    out.push(`L2 hits=${l2.hits} misses=${l2.misses} writebacks=${l2.writebacks}`);
    process.stdout.write(out.join("\n") + "\n");
    return 0;
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`cachesim: ${e.message}\n`);
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
