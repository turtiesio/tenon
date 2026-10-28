import { readFileSync } from 'node:fs';
function usage(): never { console.error('Invalid arguments'); process.exit(2); }
const args = process.argv.slice(2);
let del = false, squeeze = false, index = 0;
while (index < args.length) {
  const arg = args[index];
  if (arg === '--') { index++; break; }
  if (arg === '-d') del = true;
  else if (arg === '-s') squeeze = true;
  else { if (arg.length >= 2 && arg.startsWith('-')) usage(); break; }
  index++;
}
const sets = args.slice(index);
if (del ? sets.length !== (squeeze ? 2 : 1) : squeeze ? sets.length < 1 || sets.length > 2 : sets.length !== 2) usage();
function expand(value: string): string[] {
  const tokens: {char: string; escaped: boolean}[] = [];
  for (let i = 0; i < value.length; i++) {
    if (value[i] !== '\\') tokens.push({char: value[i], escaped: false});
    else {
      const escapes: Record<string, string> = {n: '\n', t: '\t', '\\': '\\', '-': '-'};
      const char = escapes[value[++i]];
      if (char === undefined) usage();
      tokens.push({char, escaped: true});
    }
  }
  const result: string[] = [];
  for (let i = 0; i < tokens.length; i++) {
    if (i + 2 < tokens.length && tokens[i+1].char === '-' && !tokens[i+1].escaped) {
      const start = tokens[i].char.charCodeAt(0), end = tokens[i+2].char.charCodeAt(0);
      if (start > end) usage();
      for (let code = start; code <= end; code++) result.push(String.fromCharCode(code));
      i += 2;
    } else result.push(tokens[i].char);
  }
  return result;
}
const first = expand(sets[0]), second = sets.length === 2 ? expand(sets[1]) : [];
const translate = !del && sets.length === 2;
if (translate && !second.length) usage();
const mapping = new Map<string, string>();
if (translate) first.forEach((char, i) => mapping.set(char, second[Math.min(i, second.length - 1)]));
const deletion = new Set(first), squeezed = new Set(sets.length === 1 ? first : second);
const output: string[] = [];
let previous: string | undefined;
for (const input of readFileSync(0, 'utf8')) {
  if (del && deletion.has(input)) continue;
  const char = mapping.get(input) ?? input;
  if (!(squeeze && previous === char && squeezed.has(char))) output.push(char);
  previous = char;
}
process.stdout.write(output.join(''));
