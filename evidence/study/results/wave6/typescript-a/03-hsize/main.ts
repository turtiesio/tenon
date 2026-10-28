import { readFileSync } from 'node:fs';
let si = false, precision = 1;
const sizes: string[] = [], args = process.argv.slice(2);
function usage(): never { console.error('Invalid arguments'); process.exit(2); }
for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (arg === '-s') si = true;
  else if (arg === '-p') {
    const p = args[++i];
    if (!/^[012]$/.test(p ?? '')) usage();
    precision = Number(p);
  } else if (/^[0-9]{1,16}$/.test(arg)) sizes.push(arg);
  else usage();
}
const base = si ? 1000n : 1024n, scale = 10n ** BigInt(precision);
const units = si ? ['B', 'kB', 'MB', 'GB', 'TB', 'PB'] : ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'];
function format(text: string): string {
  const value = BigInt(text);
  if (value < base) return `${value} B`;
  let k = 1;
  while (k < 5 && value >= base ** BigInt(k + 1)) k++;
  let rounded: bigint;
  while (true) {
    const divisor = base ** BigInt(k);
    rounded = (2n * value * scale + divisor) / (2n * divisor);
    if (rounded < base * scale || k === 5) break;
    k++;
  }
  return `${rounded / scale}${precision ? '.' + String(rounded % scale).padStart(precision, '0') : ''} ${units[k]}`;
}
let lines = sizes;
if (!sizes.length) {
  const input = readFileSync(0, 'utf8');
  lines = input === '' ? [] : input.split('\n');
  if (input.endsWith('\n')) lines.pop();
  lines = lines.map(line => line.replace(/\r$/, ''));
}
for (const line of lines) {
  if (/^[0-9]{1,16}$/.test(line)) console.log(format(line));
  else { console.log('?'); process.exitCode = 1; }
}
