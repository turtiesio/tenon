import { readFileSync } from 'node:fs';
function fail(code: number): never { console.error('Invalid usage or input'); process.exit(code); }
const args = process.argv.slice(2), targets: string[] = [];
let levelsOnly = false;
for (let i = 0; i < args.length; i++) {
  if (args[i] === '-l') levelsOnly = true;
  else if (args[i] === '-t') { if (i + 1 === args.length) fail(2); targets.push(args[++i]); }
  else fail(2);
}
const graph = new Map<string, Set<string>>();
function ensure(name: string): Set<string> { if (!graph.has(name)) graph.set(name, new Set()); return graph.get(name)!; }
const trimSpaces = (s: string) => s.replace(/^ +| +$/g, '');
for (const raw of readFileSync(0, 'utf8').split('\n')) {
  const line = raw.endsWith('\r') ? raw.slice(0, -1) : raw;
  if (/^ *(#.*)?$/.test(line)) continue;
  const colon = line.indexOf(':');
  if (colon < 0) fail(3);
  const target = trimSpaces(line.slice(0, colon)), rest = trimSpaces(line.slice(colon + 1));
  const deps = rest ? rest.split(/ +/) : [];
  if (![target, ...deps].every(name => /^[A-Za-z0-9_./-]+$/.test(name))) fail(3);
  const set = ensure(target);
  for (const dep of deps) { set.add(dep); ensure(dep); }
}
if (targets.some(target => !graph.has(target))) fail(3);
const selected = new Set<string>();
const stack = targets.length ? [...targets] : [...graph.keys()];
while (stack.length) { const name = stack.pop()!; if (selected.has(name)) continue; selected.add(name); stack.push(...graph.get(name)!); }
const remaining = new Map<string, number>(), dependents = new Map<string, string[]>(), levels = new Map<string, number>();
const heap: string[] = [];
function push(name: string) {
  let i = heap.length; heap.push(name);
  while (i > 0) { const parent = (i - 1) >> 1; if (heap[parent] <= name) break; heap[i] = heap[parent]; i = parent; } heap[i] = name;
}
function pop(): string {
  const first = heap[0], last = heap.pop()!;
  if (heap.length) { let i = 0; while (i * 2 + 1 < heap.length) { let child = i * 2 + 1; if (child + 1 < heap.length && heap[child + 1] < heap[child]) child++; if (heap[child] >= last) break; heap[i] = heap[child]; i = child; } heap[i] = last; }
  return first;
}
for (const name of selected) {
  const deps = graph.get(name)!; remaining.set(name, deps.size); levels.set(name, 0);
  if (!deps.size) push(name);
  for (const dep of deps) { const list = dependents.get(dep) ?? []; list.push(name); dependents.set(dep, list); }
}
const order: string[] = [];
while (heap.length) {
  const name = pop(); order.push(name);
  for (const dependent of dependents.get(name) ?? []) {
    levels.set(dependent, Math.max(levels.get(dependent)!, levels.get(name)! + 1));
    const count = remaining.get(dependent)! - 1; remaining.set(dependent, count); if (!count) push(dependent);
  }
}
if (order.length !== selected.size) {
  console.log('CYCLE ' + [...selected].filter(name => remaining.get(name)! > 0).sort().join(' ')); process.exitCode = 1;
} else if (levelsOnly) {
  const groups: string[][] = [];
  for (const name of order) { const level = levels.get(name)!; (groups[level] ??= []).push(name); }
  if (groups.length) console.log(groups.map((names, i) => i + ': ' + names.sort().join(' ')).join('\n'));
} else if (order.length) console.log(order.join('\n'));
