import { readFileSync } from 'node:fs';
function usage(): never { console.error('Invalid usage or pattern'); process.exit(2); }
let insensitive = false, invert = false, countOnly = false, ended = false;
let pattern: string | undefined;
for (const arg of process.argv.slice(2)) {
  if (pattern !== undefined) usage();
  if (ended) pattern = arg;
  else if (arg === '--') ended = true;
  else if (arg === '-i') insensitive = true;
  else if (arg === '-v') invert = true;
  else if (arg === '-c') countOnly = true;
  else if (arg.startsWith('-')) usage();
  else pattern = arg;
}
if (pattern === undefined) usage();
type Token = { kind: 'star' } | { kind: 'char', test: (char: string) => boolean };
const tokens: Token[] = [];
const lower = (s: string) => s.replace(/[A-Z]/g, c => c.toLowerCase());
let p = 0;
function character(): string {
  if (p >= pattern!.length) usage();
  const c = pattern![p++];
  if (c !== '\\') return c;
  if (p >= pattern!.length) usage();
  return pattern![p++];
}
while (p < pattern.length) {
  const c = pattern[p++];
  if (c === '*') tokens.push({ kind: 'star' });
  else if (c === '?') tokens.push({ kind: 'char', test: () => true });
  else if (c === '[') {
    const negate = pattern[p] === '!';
    if (negate) p++;
    const set = new Set<string>();
    let first = true;
    while (p < pattern.length && (first || pattern[p] !== ']')) {
      const start = character(); first = false;
      if (pattern[p] === '-' && p + 1 < pattern.length && pattern[p + 1] !== ']') {
        p++; const end = character();
        if (start.charCodeAt(0) > end.charCodeAt(0)) usage();
        for (let code = start.charCodeAt(0); code <= end.charCodeAt(0); code++) set.add(String.fromCharCode(code));
      } else set.add(start);
    }
    if (pattern[p] !== ']') usage();
    p++;
    tokens.push({ kind: 'char', test: char => {
      const member = set.has(char) || (insensitive && (set.has(lower(char)) || set.has(char.toUpperCase())));
      return negate ? !member : member;
    } });
  } else {
    let literal = c;
    if (c === '\\') literal = character();
    tokens.push({ kind: 'char', test: char => insensitive ? lower(char) === lower(literal) : char === literal });
  }
}
function matches(line: string): boolean {
  let previous = new Uint8Array(line.length + 1); previous[0] = 1;
  for (const token of tokens) {
    const next = new Uint8Array(line.length + 1);
    if (token.kind === 'star') {
      next[0] = previous[0];
      for (let i = 1; i <= line.length; i++) next[i] = previous[i] || next[i - 1];
    } else for (let i = 1; i <= line.length; i++) next[i] = previous[i - 1] && token.test(line[i - 1]) ? 1 : 0;
    previous = next;
  }
  return previous[line.length] === 1;
}
const input = readFileSync(0, 'utf8');
const lines = input === '' ? [] : input.split('\n');
if (input.endsWith('\n')) lines.pop();
const selected = lines.map(line => line.endsWith('\r') ? line.slice(0, -1) : line).filter(line => matches(line) !== invert);
if (countOnly) console.log(selected.length);
else if (selected.length) process.stdout.write(selected.join('\n') + '\n');
process.exitCode = selected.length ? 0 : 1;
