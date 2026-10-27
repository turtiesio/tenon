import { mkdirSync, statSync, unlinkSync, readFileSync, writeFileSync, renameSync } from 'node:fs';
import { join } from 'node:path';
function fatal(code: number, message: string): never { console.error(message); process.exit(code); }
if (process.argv.length !== 3) fatal(2, 'Expected directory');
const directory = process.argv[2], database = join(directory, 'todo.db'), temporary = join(directory, 'todo.db.tmp');
type Item = { id: number; priority: number; done: boolean; text: string };
const items = new Map<number, Item>();
let next = 1;
function missing(error: unknown): boolean { return (error as NodeJS.ErrnoException).code === 'ENOENT'; }
try {
  try { if (!statSync(directory).isDirectory()) throw new Error('Not a directory'); }
  catch (error) { if (!missing(error)) throw error; mkdirSync(directory); }
  try { unlinkSync(temporary); } catch (error) { if (!missing(error)) throw error; }
  let text: string | undefined;
  try { text = readFileSync(database, 'latin1'); } catch (error) { if (!missing(error)) throw error; }
  if (text !== undefined) {
    const lines = text.split('\n');
    if (lines.pop() !== '' || lines[0] !== 'TODO 1' || !/^next [1-9][0-9]{0,8}$/.test(lines[1] ?? '')) throw new Error('Invalid state');
    next = Number(lines[1].slice(5));
    let previous = 0;
    for (const line of lines.slice(2)) {
      const match = line.match(/^([1-9][0-9]{0,8}) ([1-9]) ([od]) ([\x20-\x7e]+)$/);
      if (!match) throw new Error('Invalid item');
      const id = Number(match[1]);
      if (id <= previous || id >= next) throw new Error('Invalid id order');
      items.set(id, { id, priority: Number(match[2]), done: match[3] === 'd', text: match[4] }); previous = id;
    }
  }
} catch (error) { fatal(1, String(error)); }
function save() {
  const lines = ['TODO 1', 'next ' + next, ...[...items.values()].sort((a, b) => a.id - b.id).map(item => `${item.id} ${item.priority} ${item.done ? 'd' : 'o'} ${item.text}`)];
  writeFileSync(temporary, lines.join('\n') + '\n'); renameSync(temporary, database);
}
const show = (item: Item) => `${item.id} ${item.priority} ${item.done ? 'done' : 'open'} ${item.text}`;
const openItems = () => [...items.values()].filter(item => !item.done).sort((a, b) => a.priority - b.priority || a.id - b.id);
function command(line: string): string {
  if (/[^\x20-\x7e]/.test(line)) return 'ERR bad command';
  let match: RegExpMatchArray | null;
  if ((match = line.match(/^ADD ([1-9]) (.+)$/))) {
    const id = next++; items.set(id, { id, priority: Number(match[1]), done: false, text: match[2] }); save(); return 'ADDED ' + id;
  }
  if ((match = line.match(/^(DONE|SHOW) ([0-9]{1,9})$/))) {
    const item = items.get(Number(match[2])); if (!item) return 'ERR no such item';
    if (match[1] === 'SHOW') return show(item);
    if (item.done) return 'ERR already done';
    item.done = true; save(); return 'OK';
  }
  if (line === 'LIST') { const ids = openItems().map(item => item.id); return 'OPEN' + (ids.length ? ' ' + ids.join(' ') : ''); }
  if (line === 'NEXT') { const item = openItems()[0]; return item ? show(item) : 'NONE'; }
  if (line === 'STATS') { const open = openItems().length; return `open=${open} done=${items.size - open} next_id=${next}`; }
  if (line === 'PURGE') {
    let count = 0; for (const [id, item] of items) if (item.done) { items.delete(id); count++; }
    if (count) save(); return 'PURGED ' + count;
  }
  return 'ERR bad command';
}
let pending = '';
function respond(raw: string) {
  const line = raw.endsWith('\r') ? raw.slice(0, -1) : raw;
  try { process.stdout.write(command(line) + '\n'); } catch (error) { fatal(1, String(error)); }
}
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk: string) => {
  pending += chunk;
  let start = 0, end: number;
  while ((end = pending.indexOf('\n', start)) !== -1) { respond(pending.slice(start, end)); start = end + 1; }
  pending = pending.slice(start);
});
process.stdin.on('end', () => { if (pending.length) respond(pending); });
