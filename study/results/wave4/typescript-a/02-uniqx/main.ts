import fs from 'node:fs';
const args = process.argv.slice(2);
let count = false, repeated = false, unique = false, insensitive = false, fields = 0, chars = 0;
function usage(): never { console.error('Invalid arguments'); process.exit(2); }
for (let i = 0; i < args.length; i++) {
  switch (args[i]) {
    case '-c': count = true; break;
    case '-d': repeated = true; break;
    case '-u': unique = true; break;
    case '-i': insensitive = true; break;
    case '-f': case '-s': {
      const option = args[i], value = args[++i];
      if (value === undefined || !/^[0-9]{1,4}$/.test(value)) usage();
      if (option === '-f') fields = Number(value); else chars = Number(value);
      break;
    }
    default: usage();
  }
}
function key(line: string): string {
  let pos = 0;
  for (let i = 0; i < fields && pos < line.length; i++) {
    while (line[pos] === ' ' || line[pos] === '\t') pos++;
    while (pos < line.length && line[pos] !== ' ' && line[pos] !== '\t') pos++;
  }
  const result = line.slice(pos + chars);
  return insensitive ? result.replace(/[A-Z]/g, c => c.toLowerCase()) : result;
}
const input = fs.readFileSync(0, 'utf8');
const lines = input === '' ? [] : input.split('\n');
if (input.endsWith('\n')) lines.pop();
const groups: {line: string; key: string; size: number}[] = [];
for (const raw of lines) {
  const line = raw.replace(/\r$/, ''), k = key(line), previous = groups.at(-1);
  if (previous && previous.key === k) previous.size++;
  else groups.push({line, key: k, size: 1});
}
for (const group of groups) {
  if ((repeated && group.size < 2) || (unique && group.size !== 1)) continue;
  process.stdout.write((count ? String(group.size).padStart(7) + ' ' : '') + group.line + '\n');
}
