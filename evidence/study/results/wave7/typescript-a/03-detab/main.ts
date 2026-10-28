import { readFileSync } from 'node:fs';
let stops = [8], leadingOnly = false;
const files: string[] = [];
function usage(): never { console.error('Invalid arguments'); process.exit(2); }
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (arg === '-i') leadingOnly = true;
  else if (arg === '-t') {
    const value = args[++i];
    if (!value || !/^[1-9][0-9]{0,3}(,[1-9][0-9]{0,3})*$/.test(value)) usage();
    stops = value.split(',').map(Number);
    if (stops.some((s, j) => j > 0 && s <= stops[j - 1])) usage();
  } else if (arg.startsWith('-')) usage();
  else files.push(arg);
}
const chunks: Buffer[] = [];
let failed = false;
if (!files.length) chunks.push(readFileSync(0));
else for (const file of files) {
  try { chunks.push(readFileSync(file)); }
  catch { console.error(`Cannot read ${file}`); failed = true; }
}
let column = 0, leading = true;
const output: string[] = [];
for (const ch of Buffer.concat(chunks).toString('utf8')) {
  if (ch === '\n') { output.push(ch); column = 0; leading = true; }
  else if (ch === '\t' && (!leadingOnly || leading)) {
    const count = stops.length === 1 ? stops[0] - column % stops[0] : (stops.find(s => s > column) ?? column + 1) - column;
    output.push(' '.repeat(count)); column += count;
  } else {
    output.push(ch); column++;
    if (ch !== ' ' && ch !== '\t') leading = false;
  }
}
process.stdout.write(output.join(''));
process.exitCode = failed ? 1 : 0;
