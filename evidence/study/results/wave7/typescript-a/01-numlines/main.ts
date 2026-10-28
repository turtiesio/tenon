import { readFileSync } from 'node:fs';
let style = 't', width = 6, sep = '\t', current = 1, step = 1, format = 'rn';
let file: string | undefined;
function usage(): never { console.error('Invalid arguments'); process.exit(2); }
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (arg.startsWith('-')) {
    if (!['-b', '-w', '-s', '-v', '-i', '-f'].includes(arg) || i + 1 === args.length) usage();
    const value = args[++i];
    switch (arg) {
      case '-b': if (!['a', 't', 'n'].includes(value)) usage(); style = value; break;
      case '-w': if (!/^[1-9][0-9]?$/.test(value) || Number(value) > 20) usage(); width = Number(value); break;
      case '-s': sep = value; break;
      case '-v': case '-i':
        if (!/^-?[0-9]{1,9}$/.test(value)) usage();
        if (arg === '-v') current = Number(value); else step = Number(value);
        break;
      case '-f': if (!['ln', 'rn', 'rz'].includes(value)) usage(); format = value; break;
    }
  } else { if (file !== undefined) usage(); file = arg; }
}
let input: Buffer;
try { input = readFileSync(file === undefined ? 0 : file); }
catch { console.error('Cannot read input'); process.exit(1); }
const output: Buffer[] = [];
let start = 0;
for (let i = 0; i <= input.length; i++) {
  if (i < input.length && input[i] !== 10) continue;
  if (i === input.length && start === i) break;
  const line = input.subarray(start, i);
  if (style === 'a' || (style === 't' && line.length > 0)) {
    const digits = String(current);
    let field: string;
    if (format === 'ln') field = digits.padEnd(width, ' ');
    else if (format === 'rn') field = digits.padStart(width, ' ');
    else field = current < 0 ? '-' + digits.slice(1).padStart(width - 1, '0') : digits.padStart(width, '0');
    output.push(Buffer.from(field + sep)); current += step;
  }
  output.push(line, Buffer.from('\n')); start = i + 1;
}
process.stdout.write(Buffer.concat(output));
