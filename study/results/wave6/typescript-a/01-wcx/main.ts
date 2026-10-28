import { readFileSync, statSync } from 'node:fs';
const args = process.argv.slice(2);
const selected = new Set<string>();
const files: string[] = [];
for (const arg of args) {
  if (['-l', '-w', '-m', '-c'].includes(arg)) selected.add(arg);
  else if (arg.startsWith('-')) { console.error(`Invalid option: ${arg}`); process.exit(2); }
  else files.push(arg);
}
if (!selected.size) ['-l', '-w', '-c'].forEach(x => selected.add(x));
const columns = ['-l', '-w', '-m', '-c'].filter(x => selected.has(x));
function count(data: Buffer): number[] {
  let lines = 0, words = 0, inWord = false;
  for (const byte of data) {
    if (byte === 10) lines++;
    const whitespace = byte === 32 || (byte >= 9 && byte <= 13);
    if (!whitespace && !inWord) words++;
    inWord = !whitespace;
  }
  const counts = [lines, words, selected.has('-m') ? [...data.toString('utf8')].length : 0, data.length];
  return columns.map(c => counts[['-l', '-w', '-m', '-c'].indexOf(c)]);
}
const rows: { counts: number[]; name?: string }[] = [];
if (!files.length) rows.push({ counts: count(readFileSync(0)) });
else {
  for (const file of files) {
    try {
      if (statSync(file).isDirectory()) throw new Error('Is a directory');
      rows.push({ counts: count(readFileSync(file)), name: file });
    } catch { console.error(`Cannot read: ${file}`); process.exitCode = 1; }
  }
  if (files.length >= 2) rows.push({ counts: columns.map((_, i) => rows.reduce((sum, row) => sum + row.counts[i], 0)), name: 'total' });
}
const width = Math.max(1, ...rows.flatMap(row => row.counts.map(n => String(n).length)));
for (const row of rows) console.log(row.counts.map(n => String(n).padStart(width)).join(' ') + (row.name === undefined ? '' : ` ${row.name}`));
