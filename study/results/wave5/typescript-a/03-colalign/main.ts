import { readFileSync } from 'node:fs';
function usage(): never { console.error('Invalid arguments'); process.exit(2); }
let separator: string | undefined, outsep = '  ';
let right = new Set<number>();
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  const option = args[i];
  if (!['-s', '-o', '-r'].includes(option) || i + 1 === args.length) usage();
  const value = args[++i];
  if (option === '-s') { if ([...value].length !== 1) usage(); separator = value; }
  else if (option === '-o') outsep = value;
  else {
    if (!/^[1-9][0-9]{0,2}(,[1-9][0-9]{0,2})*$/.test(value)) usage();
    right = new Set(value.split(',').map(Number));
  }
}
const input = readFileSync(0, 'utf8');
const lines = input === '' ? [] : input.split('\n');
if (input.endsWith('\n')) lines.pop();
const rows = lines.map(line => {
  line = line.replace(/\r$/, '');
  return separator === undefined ? line.match(/[^ \t]+/g) ?? [] : line === '' ? [] : line.split(separator);
});
const widths: number[] = [];
for (const row of rows) row.forEach((field, i) => widths[i] = Math.max(widths[i] ?? 0, [...field].length));
for (const row of rows) {
  const fields = row.map((field, i) => {
    const padding = ' '.repeat(widths[i] - [...field].length);
    return right.has(i + 1) ? padding + field : i === row.length - 1 ? field : field + padding;
  });
  process.stdout.write(fields.join(outsep) + '\n');
}
