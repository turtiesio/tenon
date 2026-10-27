import { readFileSync } from 'node:fs';

const args = process.argv.slice(2);
const paths = args.filter(arg => !arg.startsWith('-'));
if (paths.length !== 2 || args.some(arg => arg.startsWith('-') && !['-i', '-b', '-q', '-s'].includes(arg)) || (args.includes('-q') && args.includes('-s'))) process.exit(2);
function readLines(path: string): string[] {
  const text = readFileSync(path, 'utf8');
  if (!text) return [];
  const lines = text.split('\n');
  if (lines.at(-1) === '') lines.pop();
  return lines;
}
let a: string[], b: string[];
try { a = readLines(paths[0]); b = readLines(paths[1]); } catch { process.exit(2); }
function key(line: string): string {
  if (args.includes('-b')) line = line.replace(/[ \t]+$/, '');
  if (args.includes('-i')) line = line.replace(/[A-Z]/g, char => char.toLowerCase());
  return line;
}
const ak = a.map(key);
const bk = b.map(key);
const table = Array.from({ length: a.length + 1 }, () => new Uint16Array(b.length + 1));
for (let i = a.length - 1; i >= 0; i--) {
  for (let j = b.length - 1; j >= 0; j--) {
    table[i][j] = ak[i] === bk[j] ? 1 + table[i + 1][j + 1] : Math.max(table[i + 1][j], table[i][j + 1]);
  }
}
let i = 0, j = 0, inserted = 0, deleted = 0, common = 0;
const output: string[] = [];
while (i < a.length || j < b.length) {
  if (i < a.length && j < b.length && ak[i] === bk[j]) {
    output.push(`  ${a[i++]}`);
    j++;
    common++;
  } else if (i < a.length && (j === b.length || table[i + 1][j] >= table[i][j + 1])) {
    output.push(`- ${a[i++]}`);
    deleted++;
  } else {
    output.push(`+ ${b[j++]}`);
    inserted++;
  }
}
if (!args.includes('-q')) {
  if (args.includes('-s')) console.log(`+${inserted} -${deleted} =${common}`);
  else if (output.length) process.stdout.write(output.join('\n') + '\n');
}
process.exitCode = inserted + deleted ? 1 : 0;
