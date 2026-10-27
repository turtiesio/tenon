import * as fs from "node:fs";

class UsageError extends Error {}
class InputError extends Error {}

interface Options {
  levels: boolean;
  targets: string[];
}

const NAME = /^[A-Za-z0-9_./-]+$/;

function parseArgs(args: string[]): Options {
  const opts: Options = { levels: false, targets: [] };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-l") opts.levels = true;
    else if (arg === "-t") {
      if (i + 1 >= args.length) throw new UsageError("-t requires a name");
      opts.targets.push(args[++i]);
    } else throw new UsageError(`unexpected argument: ${arg}`);
  }
  return opts;
}

function trimSpaces(s: string): string {
  return s.replace(/^ +| +$/g, "");
}

/** Reads the rules into a map from each item to its set of dependencies. */
function readRules(): Map<string, Set<string>> {
  const text = fs.readFileSync(0, "latin1");
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  const deps = new Map<string, Set<string>>();
  const item = (name: string): Set<string> => {
    let set = deps.get(name);
    if (!set) {
      set = new Set();
      deps.set(name, set);
    }
    return set;
  };
  lines.forEach((raw, i) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    const trimmed = trimSpaces(line);
    if (trimmed === "" || trimmed.startsWith("#")) return;
    const colon = line.indexOf(":");
    if (colon < 0) throw new InputError(`line ${i + 1}: missing ':'`);
    const target = trimSpaces(line.slice(0, colon));
    if (!NAME.test(target)) throw new InputError(`line ${i + 1}: invalid target: '${target}'`);
    const names = line.slice(colon + 1).split(/ +/).filter((n) => n !== "");
    for (const n of names) {
      if (!NAME.test(n)) throw new InputError(`line ${i + 1}: invalid dependency: '${n}'`);
    }
    const set = item(target);
    for (const n of names) {
      set.add(n);
      item(n);
    }
  });
  return deps;
}

function select(deps: Map<string, Set<string>>, targets: string[]): Set<string> {
  if (targets.length === 0) return new Set(deps.keys());
  for (const t of targets) {
    if (!deps.has(t)) throw new InputError(`not an item: ${t}`);
  }
  const selected = new Set<string>();
  const stack = [...targets];
  while (stack.length > 0) {
    const name = stack.pop()!;
    if (selected.has(name)) continue;
    selected.add(name);
    for (const d of deps.get(name)!) stack.push(d);
  }
  return selected;
}

class MinHeap {
  private items: string[] = [];

  get size(): number {
    return this.items.length;
  }

  push(value: string): void {
    const a = this.items;
    a.push(value);
    let i = a.length - 1;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (a[parent] <= a[i]) break;
      [a[parent], a[i]] = [a[i], a[parent]];
      i = parent;
    }
  }

  pop(): string {
    const a = this.items;
    const top = a[0];
    const last = a.pop()!;
    if (a.length > 0) {
      a[0] = last;
      let i = 0;
      for (;;) {
        const l = 2 * i + 1;
        const r = l + 1;
        let smallest = i;
        if (l < a.length && a[l] < a[smallest]) smallest = l;
        if (r < a.length && a[r] < a[smallest]) smallest = r;
        if (smallest === i) break;
        [a[smallest], a[i]] = [a[i], a[smallest]];
        i = smallest;
      }
    }
    return top;
  }
}

/** Kahn's algorithm, always taking the smallest ready name. */
function buildOrder(deps: Map<string, Set<string>>, selected: Set<string>): string[] {
  const remaining = new Map<string, number>();
  const dependents = new Map<string, string[]>();
  const ready = new MinHeap();
  for (const name of selected) {
    const ds = deps.get(name)!;
    remaining.set(name, ds.size);
    if (ds.size === 0) ready.push(name);
    for (const d of ds) {
      const list = dependents.get(d);
      if (list) list.push(name);
      else dependents.set(d, [name]);
    }
  }
  const order: string[] = [];
  while (ready.size > 0) {
    const name = ready.pop();
    order.push(name);
    for (const dependent of dependents.get(name) ?? []) {
      const left = remaining.get(dependent)! - 1;
      remaining.set(dependent, left);
      if (left === 0) ready.push(dependent);
    }
  }
  return order;
}

function byteOrder(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function formatLevels(deps: Map<string, Set<string>>, order: string[]): string {
  const level = new Map<string, number>();
  const groups: string[][] = [];
  for (const name of order) {
    let l = 0;
    for (const d of deps.get(name)!) l = Math.max(l, level.get(d)! + 1);
    level.set(name, l);
    (groups[l] ??= []).push(name);
  }
  return groups.map((names, l) => `${l}: ${names.sort(byteOrder).join(" ")}\n`).join("");
}

function main(): number {
  try {
    const opts = parseArgs(process.argv.slice(2));
    const deps = readRules();
    const selected = select(deps, opts.targets);
    const order = buildOrder(deps, selected);
    if (order.length < selected.size) {
      const printed = new Set(order);
      const stuck = [...selected].filter((n) => !printed.has(n)).sort(byteOrder);
      process.stdout.write(`CYCLE ${stuck.join(" ")}\n`);
      return 1;
    }
    process.stdout.write(opts.levels ? formatLevels(deps, order) : order.map((n) => n + "\n").join(""));
    return 0;
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`buildorder: ${e.message}\nusage: buildorder [-l] [-t NAME]...\n`);
      return 2;
    }
    if (e instanceof InputError) {
      process.stderr.write(`buildorder: ${e.message}\n`);
      return 3;
    }
    throw e;
  }
}

process.exitCode = main();
