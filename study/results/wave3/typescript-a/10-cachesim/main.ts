import { readFileSync } from 'node:fs';
function fail(code: number, message: string): never { console.error(message); process.exit(code); }
let blockSize = 16;
const geometries: Record<string, [number, number]> = { '-1': [4, 2], '-2': [16, 4] };
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  const option = args[i];
  if (!['-b', '-1', '-2'].includes(option) || i + 1 === args.length) fail(2, 'Invalid option');
  const value = args[++i];
  if (option === '-b') {
    if (!/^[0-9]{1,4}$/.test(value)) fail(2, 'Invalid block size');
    blockSize = Number(value);
    if (blockSize < 1 || blockSize > 4096 || (blockSize & (blockSize - 1)) !== 0) fail(2, 'Invalid block size');
  } else {
    const match = value.match(/^([0-9]{1,4}):([0-9]{1,2})$/);
    if (!match) fail(2, 'Invalid geometry');
    const sets = Number(match[1]), ways = Number(match[2]);
    if (sets < 1 || sets > 4096 || ways < 1 || ways > 64) fail(2, 'Invalid geometry');
    geometries[option] = [sets, ways];
  }
}
const trace = readFileSync(0, 'utf8').split('\n').map(line => line.endsWith('\r') ? line.slice(0, -1) : line).filter(line => !/^ *$/.test(line));
if (trace.some(line => !/^[RW] 0x[0-9a-fA-F]{1,8}$/.test(line))) fail(1, 'Invalid trace');
type Entry = { block: number; dirty: boolean };
class Cache {
  sets: Entry[][];
  ways: number;
  hits = 0;
  misses = 0;
  writebacks = 0;
  constructor(geometry: [number, number]) {
    this.sets = Array.from({ length: geometry[0] }, () => []); this.ways = geometry[1];
  }
  touch(block: number, dirty: boolean): boolean {
    const set = this.sets[block % this.sets.length], index = set.findIndex(entry => entry.block === block);
    if (index < 0) return false;
    const [entry] = set.splice(index, 1); entry.dirty ||= dirty; set.push(entry); return true;
  }
  install(block: number, dirty: boolean, evict: (entry: Entry) => void) {
    const set = this.sets[block % this.sets.length];
    if (set.length === this.ways) evict(set.shift()!);
    set.push({ block, dirty });
  }
  summary(name: string) { return `${name} hits=${this.hits} misses=${this.misses} writebacks=${this.writebacks}`; }
}
const l1 = new Cache(geometries['-1']), l2 = new Cache(geometries['-2']);
const l2Victim = (entry: Entry) => { if (entry.dirty) l2.writebacks++; };
const l1Victim = (entry: Entry) => {
  if (!entry.dirty) return;
  l1.writebacks++;
  if (!l2.touch(entry.block, true)) l2.install(entry.block, true, l2Victim);
};
const output: string[] = [];
for (const line of trace) {
  const block = Math.floor(Number.parseInt(line.slice(4), 16) / blockSize), write = line[0] === 'W';
  let result: string;
  if (l1.touch(block, write)) { l1.hits++; result = 'L1'; }
  else {
    l1.misses++;
    if (l2.touch(block, false)) { l2.hits++; result = 'L2'; }
    else { l2.misses++; l2.install(block, false, l2Victim); result = 'MEM'; }
    l1.install(block, write, l1Victim);
  }
  output.push(line + ' ' + result);
}
output.push(l1.summary('L1'), l2.summary('L2'));
process.stdout.write(output.join('\n') + '\n');
