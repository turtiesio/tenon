import { createInterface } from 'node:readline';
if (process.argv.length !== 2) { console.error('No arguments allowed'); process.exit(2); }
const buffer: string[] = [];
type Change = { index: number; before: string[]; after: string[] };
const undo: Change[] = [], redo: Change[] = [];
const ok = () => 'OK ' + buffer.length;
function change(index: number, count: number, after: string[]): string {
  const before = buffer.splice(index, count, ...after);
  undo.push({ index, before, after }); redo.length = 0; return ok();
}
function command(line: string): string {
  if (line === 'COUNT') return String(buffer.length);
  if (line === 'UNDO' || line === 'REDO') {
    const source = line === 'UNDO' ? undo : redo, destination = line === 'UNDO' ? redo : undo;
    const edit = source.pop();
    if (!edit) return 'ERR nothing to ' + line.toLowerCase();
    const from = line === 'UNDO' ? edit.after : edit.before, to = line === 'UNDO' ? edit.before : edit.after;
    buffer.splice(edit.index, from.length, ...to); destination.push(edit); return ok();
  }
  let match: RegExpMatchArray | null;
  if ((match = line.match(/^APPEND (.*)$/))) return change(buffer.length, 0, [match[1]]);
  if ((match = line.match(/^(INSERT|REPLACE) ([0-9]{1,9}) (.*)$/))) {
    const n = Number(match[2]), insert = match[1] === 'INSERT';
    if (n < 1 || n > buffer.length + (insert ? 1 : 0)) return 'ERR bad line';
    return change(n - 1, insert ? 0 : 1, [match[3]]);
  }
  if ((match = line.match(/^DELETE ([0-9]{1,9})(?: ([0-9]{1,9}))?$/))) {
    const a = Number(match[1]), b = match[2] === undefined ? a : Number(match[2]);
    if (a < 1 || a > b || b > buffer.length) return 'ERR bad line';
    return change(a - 1, b - a + 1, []);
  }
  if ((match = line.match(/^PRINT ([0-9]{1,9})$/))) {
    const n = Number(match[1]); if (n < 1 || n > buffer.length) return 'ERR bad line';
    return n + '|' + buffer[n - 1];
  }
  if ((match = line.match(/^FIND (.+)$/))) {
    const found: number[] = [];
    buffer.forEach((text, i) => { if (text.includes(match![1])) found.push(i + 1); });
    return found.length ? found.join(' ') : 'NONE';
  }
  return 'ERR bad command';
}
const input = createInterface({ input: process.stdin, crlfDelay: Infinity });
input.on('line', line => process.stdout.write(command(line) + '\n'));
