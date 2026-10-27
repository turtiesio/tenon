import { readFileSync } from 'node:fs';
function fail(code: number): never { console.error('Invalid input or arguments'); process.exit(code); }
const args = process.argv.slice(2);
if (args.length !== 1 || !/^[+-]?[0-9]{1,9}$/.test(args[0])) fail(2);
const offset = Number(args[0]);
const input = readFileSync(0, 'utf8');
const lines = input === '' ? [] : input.split('\n');
if (input.endsWith('\n')) lines.pop();
const blocks: string[][] = [];
let block: string[] = [];
for (const raw of lines) {
  const line = raw.replace(/\r$/, '');
  if (/^[ \t]*$/.test(line)) { if (block.length) blocks.push(block); block = []; }
  else block.push(line);
}
if (block.length) blocks.push(block);
function parse(time: string): number {
  const [h, m, s, ms] = time.split(/[:,]/).map(Number);
  return ((h * 60 + m) * 60 + s) * 1000 + ms;
}
function format(time: number): string {
  const ms = time % 1000, seconds = Math.floor(time / 1000);
  return `${String(Math.floor(seconds / 3600)).padStart(2, '0')}:${String(Math.floor(seconds / 60) % 60).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
}
const cues: {start: number; end: number; text: string[]}[] = [];
for (const block of blocks) {
  if (block.length < 3 || !/^[0-9]{1,9}$/.test(block[0])) fail(1);
  const match = /^([0-9]{2}:[0-5][0-9]:[0-5][0-9],[0-9]{3}) --> ([0-9]{2}:[0-5][0-9]:[0-5][0-9],[0-9]{3})$/.exec(block[1]);
  if (!match) fail(1);
  const start = parse(match[1]), end = parse(match[2]);
  if (end <= start) fail(1);
  if (end + offset > 0) cues.push({start: Math.max(0, start + offset), end: end + offset, text: block.slice(2)});
}
cues.sort((a, b) => a.start - b.start);
process.stdout.write(cues.map((cue, i) => `${i + 1}\n${format(cue.start)} --> ${format(cue.end)}\n${cue.text.join('\n')}\n\n`).join(''));
