import fs from 'node:fs';
import path from 'node:path';
const args = process.argv.slice(2);
if (args.length !== 1) { console.error('Expected data directory'); process.exit(2); }
function ioFailure(): never { console.error('Data directory or journal is unusable'); process.exit(1); }
type Link = {url: string; hits: number};
const links = new Map<string, Link>();
let nextId = 1, records = 0, journal: number;
try {
  if (!fs.existsSync(args[0])) fs.mkdirSync(args[0]);
  if (!fs.statSync(args[0]).isDirectory()) ioFailure();
  journal = fs.openSync(path.join(args[0], 'journal'), 'a+');
  const contents = fs.readFileSync(journal).toString('latin1');
  let offset = 0;
  while (offset < contents.length) {
    const end = contents.indexOf('\n', offset);
    if (end === -1) break;
    const line = contents.slice(offset, end);
    const match = /^([1-9][0-9]{0,8}) ([PHD]) (.*)$/.exec(line);
    if (!match || Number(match[1]) !== records + 1) break;
    const [, , operation, value] = match;
    if (operation === 'P') {
      if (!/^[!-~]{1,200}$/.test(value)) break;
      links.set((nextId++).toString(36), {url: value, hits: 0});
    } else {
      if (!/^[0-9a-z]{1,8}$/.test(value) || !links.has(value)) break;
      if (operation === 'H') links.get(value)!.hits++;
      else links.delete(value);
    }
    records++; offset = end + 1;
  }
  fs.ftruncateSync(journal, offset);
} catch { ioFailure(); }
function append(operation: string, value: string): void {
  try { fs.writeFileSync(journal, `${records + 1} ${operation} ${value}\n`); }
  catch { ioFailure(); }
  records++;
}
function command(line: string): string {
  if (line === 'INFO') return `links=${links.size} next=${nextId.toString(36)} records=${records}`;
  const put = /^PUT ([!-~]{1,200})$/.exec(line);
  if (put) {
    append('P', put[1]);
    const code = (nextId++).toString(36);
    links.set(code, {url: put[1], hits: 0});
    return `CODE ${code}`;
  }
  const match = /^(GET|HITS|DEL) ([0-9a-z]{1,8})$/.exec(line);
  if (!match) return 'ERR bad command';
  const [, action, code] = match, link = links.get(code);
  if (!link) return 'ERR not found';
  if (action === 'HITS') return `HITS ${link.hits}`;
  if (action === 'GET') { append('H', code); link.hits++; return `URL ${link.url}`; }
  append('D', code); links.delete(code); return 'OK';
}
let pending = '';
function respond(line: string): void { process.stdout.write(command(line.replace(/\r$/, '')) + '\n'); }
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk: string) => {
  pending += chunk;
  let start = 0, end: number;
  while ((end = pending.indexOf('\n', start)) !== -1) { respond(pending.slice(start, end)); start = end + 1; }
  pending = pending.slice(start);
});
process.stdin.on('end', () => { if (pending.length) respond(pending); fs.closeSync(journal); });
