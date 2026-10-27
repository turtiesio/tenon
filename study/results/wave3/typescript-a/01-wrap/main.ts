import { readFileSync } from 'node:fs';
function fail(code: number, message: string): never { console.error(message); process.exit(code); }
const args = process.argv.slice(2);
let width = 72, indent = 0, justify = false;
const seen = new Set<string>();
for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (!['-w', '-i', '-j'].includes(arg) || seen.has(arg)) fail(2, 'Invalid option');
  seen.add(arg);
  if (arg === '-j') { justify = true; continue; }
  const value = args[++i];
  if (value === undefined || !/^[0-9]{1,4}$/.test(value)) fail(2, 'Invalid number');
  if (arg === '-w') width = Number(value); else indent = Number(value);
}
if (width < 1 || width > 1000 || indent >= width) fail(2, 'Invalid width or indent');
const lines = readFileSync(0, 'latin1').split('\n').map(line => line.endsWith('\r') ? line.slice(0, -1) : line);
if (lines.some(line => /[^\x20-\x7e]/.test(line))) fail(1, 'Invalid input');
const paragraphs: string[][] = [];
let words: string[] = [];
for (const line of [...lines, '']) {
  if (/^ *$/.test(line)) { if (words.length) paragraphs.push(words); words = []; }
  else words.push(...line.trim().split(/ +/));
}
const output = paragraphs.map(paragraph => {
  const result: string[] = [];
  let index = 0;
  while (index < paragraph.length) {
    const padding = result.length === 0 ? indent : 0;
    const row = [paragraph[index++]];
    let length = padding + row[0].length;
    while (index < paragraph.length && length + 1 + paragraph[index].length <= width) {
      length += 1 + paragraph[index].length; row.push(paragraph[index++]);
    }
    let text = ' '.repeat(padding);
    const gaps = row.length - 1;
    const spaces = width - padding - row.reduce((n, word) => n + word.length, 0);
    row.forEach((word, i) => {
      if (i) text += ' '.repeat(justify && index < paragraph.length && gaps > 0 ? Math.floor(spaces / gaps) + (i <= spaces % gaps ? 1 : 0) : 1);
      text += word;
    });
    result.push(text);
  }
  return result.join('\n');
});
if (output.length) process.stdout.write(output.join('\n\n') + '\n');
