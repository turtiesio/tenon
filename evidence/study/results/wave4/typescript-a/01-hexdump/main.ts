import fs from 'node:fs';
function fail(message: string, code: number): never { console.error(message); process.exit(code); }
const args = process.argv.slice(2);
let skip = 0, length = Infinity, width = 16, file: string | undefined;
for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (['-s', '-n', '-w'].includes(arg)) {
    const value = args[++i];
    if (value === undefined || !(arg === '-w' ? /^[0-9]{1,2}$/ : /^[0-9]{1,9}$/).test(value)) fail('Invalid option value', 2);
    const n = Number(value);
    if (arg === '-w') { if (n < 1 || n > 32) fail('Invalid width', 2); width = n; }
    else if (arg === '-s') skip = n;
    else length = n;
  } else {
    if ((arg.startsWith('-') && arg !== '-') || file !== undefined) fail('Invalid arguments', 2);
    file = arg;
  }
}
let input: Buffer;
try {
  if (file && file !== '-' && !fs.statSync(file).isFile()) fail('Not a regular file', 1);
  input = fs.readFileSync(!file || file === '-' ? 0 : file);
} catch { fail('Cannot read input', 1); }
const selected = input.subarray(skip, Math.min(input.length, skip + length));
const offset = (n: number) => n.toString(16).padStart(8, '0');
const lines: string[] = [];
for (let i = 0; i < selected.length; i += width) {
  const chunk = selected.subarray(i, i + width);
  const fields = Array.from({length: width}, (_, j) => j < chunk.length ? chunk[j].toString(16).padStart(2, '0') : '  ');
  const ascii = Array.from(chunk, b => b >= 32 && b <= 126 ? String.fromCharCode(b) : '.').join('');
  lines.push(`${offset(skip + i)}  ${fields.join(' ')}  |${ascii}|`);
}
lines.push(offset(skip + selected.length));
process.stdout.write(lines.join('\n') + '\n');
