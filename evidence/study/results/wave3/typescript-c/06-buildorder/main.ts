import { readFileSync } from "node:fs";

class UsageError extends Error {}
class InputError extends Error {}

interface Options {
  levels: boolean;
  targets: string[];
}

const NAME = /^[A-Za-z0-9_./-]+$/;

function parseArgs(args: string[]): Options {
  let levels = false;
  const targets: string[] = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "-l") {
      levels = true;
    } else if (args[i] === "-t") {
      if (i + 1 >= args.length) throw new UsageError("-t needs an argument");
      targets.push(args[++i]);
    } else {
      throw new UsageError(`unexpected argument: ${args[i]}`);
    }
  }
  return { levels, targets };
}

// Maps every item to the set of items it depends on.
function parseRules(text: string): Map<string, Set<string>> {
  const deps = new Map<string, Set<string>>();
  const item = (name: string): Set<string> => {
    let set = deps.get(name);
    if (!set) {
      set = new Set();
      deps.set(name, set);
    }
    return set;
  };
  const lines = text.split("\n");
  lines.forEach((raw, index) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    const trimmed = line.trim();
    if (trimmed === "" || trimmed.startsWith("#")) return;
    const colon = line.indexOf(":");
    if (colon < 0) throw new InputError(`line ${index + 1}: missing ':'`);
    const target = line.slice(0, colon).replace(/^ +| +$/g, "");
    if (!NAME.test(target)) throw new InputError(`line ${index + 1}: bad target`);
    const names = line
      .slice(colon + 1)
      .split(" ")
      .filter((n) => n !== "");
    for (const name of names) {
      if (!NAME.test(name)) throw new InputError(`line ${index + 1}: bad dependency ${name}`);
    }
    const own = item(target);
    for (const name of names) {
      own.add(name);
      item(name);
    }
  });
  return deps;
}

function select(deps: Map<string, Set<string>>, targets: string[]): Set<string> {
  if (targets.length === 0) return new Set(deps.keys());
  const selected = new Set<string>();
  const pending = [...targets];
  for (let name = pending.pop(); name !== undefined; name = pending.pop()) {
    if (selected.has(name)) continue;
    selected.add(name);
    pending.push(...deps.get(name)!);
  }
  return selected;
}

interface Plan {
  order: string[];
  level: Map<string, number>;
}

// Repeatedly takes the smallest ready item (rule 5), recording levels.
function plan(deps: Map<string, Set<string>>, selected: Set<string>): Plan {
  const remaining = new Map<string, number>();
  const dependents = new Map<string, string[]>();
  for (const name of selected) {
    remaining.set(name, deps.get(name)!.size);
    for (const dep of deps.get(name)!) {
      const list = dependents.get(dep);
      if (list) list.push(name);
      else dependents.set(dep, [name]);
    }
  }
  // Kept sorted descending, so the smallest name is popped from the end.
  const ready: string[] = [];
  const insert = (name: string) => {
    let lo = 0;
    let hi = ready.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (ready[mid] > name) lo = mid + 1;
      else hi = mid;
    }
    ready.splice(lo, 0, name);
  };
  for (const [name, count] of remaining) if (count === 0) insert(name);

  const order: string[] = [];
  const level = new Map<string, number>();
  for (let name = ready.pop(); name !== undefined; name = ready.pop()) {
    order.push(name);
    let own = 0;
    for (const dep of deps.get(name)!) own = Math.max(own, level.get(dep)! + 1);
    level.set(name, own);
    for (const user of dependents.get(name) ?? []) {
      const left = remaining.get(user)! - 1;
      remaining.set(user, left);
      if (left === 0) insert(user);
    }
  }
  return { order, level };
}

function byteOrder(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function main(): number {
  try {
    const options = parseArgs(process.argv.slice(2));
    const deps = parseRules(readFileSync(0).toString("latin1"));
    for (const target of options.targets) {
      if (!deps.has(target)) throw new InputError(`not an item: ${target}`);
    }
    const selected = select(deps, options.targets);
    const { order, level } = plan(deps, selected);

    if (order.length < selected.size) {
      const done = new Set(order);
      const stuck = [...selected].filter((n) => !done.has(n)).sort(byteOrder);
      process.stdout.write(`CYCLE ${stuck.join(" ")}\n`);
      return 1;
    }
    if (options.levels) {
      const groups: string[][] = [];
      for (const name of [...order].sort(byteOrder)) {
        (groups[level.get(name)!] ??= []).push(name);
      }
      process.stdout.write(groups.map((names, n) => `${n}: ${names.join(" ")}\n`).join(""));
    } else {
      process.stdout.write(order.map((n) => n + "\n").join(""));
    }
    return 0;
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`buildorder: ${e.message}\n`);
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
