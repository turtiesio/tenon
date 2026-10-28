import { readFileSync } from 'node:fs';
function fail(code: number, message: string): never { console.error(message); process.exit(code); }
let leftJoin = false, key = 'id';
const paths: string[] = [], args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  if (args[i] === '-l') leftJoin = true;
  else if (args[i] === '-k') { key = args[++i]; if (!key) fail(2, 'Missing key'); }
  else if (args[i].startsWith('-')) fail(2, 'Unknown option');
  else paths.push(args[i]);
}
if (paths.length !== 2) fail(2, 'Expected two files');
function parse(text: string): string[][] {
  const records: string[][] = [];
  let i = 0;
  const terminator = () => text[i] === '\n' || text[i] === '\r' && text[i + 1] === '\n';
  const advance = () => { i += text[i] === '\r' ? 2 : 1; };
  while (i < text.length) {
    if (terminator()) { advance(); continue; }
    const row: string[] = [];
    while (true) {
      let field = '';
      if (text[i] === '"') {
        i++; let closed = false;
        while (i < text.length) {
          if (text[i] === '"') {
            i++;
            if (text[i] === '"') { field += '"'; i++; }
            else { closed = true; break; }
          } else field += text[i++];
        }
        if (!closed) throw new Error('Unclosed quote');
      } else {
        while (i < text.length && text[i] !== ',' && !terminator()) {
          if (text[i] === '"' || text[i] === '\r') throw new Error('Invalid field');
          field += text[i++];
        }
      }
      row.push(field);
      if (i === text.length) break;
      if (text[i] === ',') { i++; continue; }
      if (terminator()) { advance(); break; }
      throw new Error('Invalid field ending');
    }
    records.push(row);
  }
  if (!records.length) throw new Error('Missing header');
  const header = records[0];
  if (new Set(header).size !== header.length || !header.includes(key) || records.some(row => row.length !== header.length)) throw new Error('Invalid columns');
  return records;
}
try {
  const [left, right] = paths.map(path => parse(readFileSync(path, 'utf8')));
  const lh = left[0], rh = right[0], li = lh.indexOf(key), ri = rh.indexOf(key);
  const withoutKey = (row: string[]) => row.filter((_, i) => i !== ri);
  const header = [...lh, ...withoutKey(rh).map(name => lh.includes(name) ? 'r.' + name : name)];
  const index = new Map<string, string[][]>();
  for (const row of right.slice(1)) {
    const matches = index.get(row[ri]) ?? []; matches.push(row); index.set(row[ri], matches);
  }
  const output: string[][] = [header];
  for (const row of left.slice(1)) {
    const matches = index.get(row[li]);
    if (matches) for (const match of matches) output.push([...row, ...withoutKey(match)]);
    else if (leftJoin) output.push([...row, ...Array(rh.length - 1).fill('')]);
  }
  const quote = (field: string) => /[,"\r\n]/.test(field) ? '"' + field.replaceAll('"', '""') + '"' : field;
  process.stdout.write(output.map(row => row.map(quote).join(',')).join('\n') + '\n');
} catch (error) { fail(1, String(error)); }
