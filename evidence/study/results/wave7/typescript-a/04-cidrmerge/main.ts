import { readFileSync } from 'node:fs';
const args = process.argv.slice(2);
if (args.length && (args.length !== 1 || args[0] !== '-r')) { console.error('Invalid arguments'); process.exit(2); }
const ranges: [number, number][] = [];
let failed = false;
const lines = readFileSync(0, 'utf8').split('\n');
if (lines.at(-1) === '') lines.pop();
for (let line of lines) {
  line = line.replace(/\r$/, '');
  if (!line || line.startsWith('#')) continue;
  const match = /^(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})(?:\/(0|[1-9][0-9]?))?$/.exec(line);
  if (match) {
    const octets = match.slice(1, 5).map(Number), prefix = match[5] === undefined ? 32 : Number(match[5]);
    const address = octets.reduce((n, x) => n * 256 + x, 0), size = 2 ** (32 - prefix);
    if (octets.every(x => x <= 255) && prefix <= 32 && address % size === 0) { ranges.push([address, address + size - 1]); continue; }
  }
  console.error(`Invalid entry: ${line}`); failed = true;
}
ranges.sort((a, b) => a[0] - b[0]);
const merged: [number, number][] = [];
for (const range of ranges) {
  const last = merged.at(-1);
  if (last && range[0] <= last[1] + 1) last[1] = Math.max(last[1], range[1]);
  else merged.push([...range]);
}
function dotted(n: number): string { return [24, 16, 8, 0].map(shift => Math.floor(n / 2 ** shift) % 256).join('.'); }
const output: string[] = [];
for (const [start, end] of merged) {
  if (args.length) output.push(`${dotted(start)}-${dotted(end)} ${end - start + 1}`);
  else for (let address = start; address <= end;) {
    let power = 0;
    while (power < 32 && address % 2 ** (power + 1) === 0 && address + 2 ** (power + 1) - 1 <= end) power++;
    output.push(`${dotted(address)}/${32 - power}`); address += 2 ** power;
  }
}
if (output.length) process.stdout.write(output.join('\n') + '\n');
process.exitCode = failed ? 1 : 0;
