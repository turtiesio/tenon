import { readFileSync } from 'node:fs';

const args = process.argv.slice(2);
if (args.length < 1 || args.length > 2 || args.some(arg => !/^[A-Za-z_][A-Za-z0-9_.]*$/.test(arg))) process.exit(2);
function parse(line: string): Map<string, string> | undefined {
  const pairs = new Map<string, string>();
  let i = 0;
  while (i < line.length) {
    while (line[i] === ' ') i++;
    if (i === line.length) break;
    const match = /^[A-Za-z_][A-Za-z0-9_.]*/.exec(line.slice(i));
    if (!match) return;
    const key = match[0];
    i += key.length;
    let value = 'true';
    if (line[i] === '=') {
      i++;
      value = '';
      if (line[i] === '"') {
        i++;
        let closed = false;
        while (i < line.length) {
          const char = line[i++];
          if (char === '"') { closed = true; break; }
          if (char === '\\') {
            if (line[i] !== '"' && line[i] !== '\\') return;
            value += line[i++];
          } else value += char;
        }
        if (!closed || (i < line.length && line[i] !== ' ')) return;
      } else {
        while (i < line.length && line[i] !== ' ') value += line[i++];
        if (/["=]/.test(value)) return;
      }
    } else if (i < line.length && line[i] !== ' ') return;
    if (pairs.has(key)) return;
    pairs.set(key, value);
  }
  return pairs;
}
type Group = { count: number; n: number; sum: bigint; min?: bigint; max?: bigint };
const groups = new Map<string, Group>();
let valid = 0, malformed = 0, nokey = 0;
for (let line of readFileSync(0, 'utf8').split('\n')) {
  line = line.replace(/\r$/, '');
  if (/^ *$/.test(line)) continue;
  const pairs = parse(line);
  if (!pairs) { malformed++; continue; }
  valid++;
  const name = pairs.get(args[0]);
  if (name === undefined) { nokey++; continue; }
  const group = groups.get(name) ?? { count: 0, n: 0, sum: 0n };
  groups.set(name, group);
  group.count++;
  const value = pairs.get(args[1]);
  if (args.length === 2 && value !== undefined && /^-?[0-9]{1,15}$/.test(value)) {
    const number = BigInt(value);
    group.n++;
    group.sum += number;
    if (group.min === undefined || number < group.min) group.min = number;
    if (group.max === undefined || number > group.max) group.max = number;
  }
}
function average(sum: bigint, n: number): string {
  const absolute = sum < 0n ? -sum : sum;
  const divisor = BigInt(n);
  const cents = (absolute * 200n + divisor) / (2n * divisor);
  return `${sum < 0n && cents > 0n ? '-' : ''}${cents / 100n}.${String(cents % 100n).padStart(2, '0')}`;
}
for (const [name, group] of [...groups].sort((a, b) => b[1].count - a[1].count || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))) {
  let line = `${name || '""'} count=${group.count}`;
  if (args.length === 2) line += group.n ? ` n=${group.n} sum=${group.sum} min=${group.min} max=${group.max} avg=${average(group.sum, group.n)}` : ' n=0 sum=0 min=- max=- avg=-';
  console.log(line);
}
console.log(`lines=${valid} malformed=${malformed} nokey=${nokey}`);
