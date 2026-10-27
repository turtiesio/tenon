import { appendFileSync, existsSync, mkdirSync, readFileSync, renameSync, statSync, unlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const args = process.argv.slice(2);
if (args.length !== 1) {
  console.error('Expected a directory');
  process.exit(2);
}
const dir = args[0];
const log = join(dir, 'tally.log');
const temporary = join(dir, 'tally.log.tmp');
const counters = new Map<string, bigint>();
let records = 0;
const recordPattern = /^(?:([SA]) ([a-z][a-z0-9_]{0,31}) (-?[0-9]{1,15})|D ([a-z][a-z0-9_]{0,31}))$/;
try {
  if (!existsSync(dir)) mkdirSync(dir);
  if (!statSync(dir).isDirectory()) throw new Error('Not a directory');
  if (existsSync(temporary)) unlinkSync(temporary);
  const data = existsSync(log) ? readFileSync(log) : Buffer.alloc(0);
  let offset = 0;
  while (offset < data.length) {
    const end = data.indexOf(10, offset);
    if (end < 0) break;
    const match = recordPattern.exec(data.subarray(offset, end).toString('utf8'));
    if (!match) break;
    if (match[4]) counters.delete(match[4]);
    else {
      const value = BigInt(match[3]);
      counters.set(match[2], match[1] === 'S' ? value : (counters.get(match[2]) ?? 0n) + value);
    }
    records++;
    offset = end + 1;
  }
  writeFileSync(log, data.subarray(0, offset));
} catch (error) {
  console.error(String(error));
  process.exit(1);
}
function append(record: string): void {
  appendFileSync(log, record + '\n');
  records++;
}
function sorted(): [string, bigint][] {
  return [...counters].sort((a, b) => a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0);
}
function respond(line: string): string {
  if (line === 'LIST') return [String(counters.size), ...sorted().map(([name, value]) => `${name}=${value}`)].join(' ');
  if (line === 'INFO') return `counters=${counters.size} log_records=${records}`;
  if (line === 'COMPACT') {
    const snapshot = sorted().map(([name, value]) => `S ${name} ${value}\n`).join('');
    writeFileSync(temporary, snapshot);
    renameSync(temporary, log);
    records = counters.size;
    return `OK ${records}`;
  }
  const match = /^(?:(SET|ADD) ([a-z][a-z0-9_]{0,31}) (-?[0-9]{1,15})|(GET|DEL) ([a-z][a-z0-9_]{0,31}))$/.exec(line);
  if (!match) return 'ERR bad command';
  if (match[1]) {
    const name = match[2];
    const delta = BigInt(match[3]);
    const value = match[1] === 'SET' ? delta : (counters.get(name) ?? 0n) + delta;
    append(`${match[1] === 'SET' ? 'S' : 'A'} ${name} ${delta}`);
    counters.set(name, value);
    return match[1] === 'SET' ? 'OK' : String(value);
  }
  const name = match[5];
  if (match[4] === 'GET') return counters.has(name) ? String(counters.get(name)) : 'NONE';
  if (!counters.has(name)) return 'NONE';
  append(`D ${name}`);
  counters.delete(name);
  return 'OK';
}
process.stdin.setEncoding('utf8');
let pending = '';
for await (const chunk of process.stdin) {
  pending += chunk;
  let end: number;
  while ((end = pending.indexOf('\n')) >= 0) {
    process.stdout.write(respond(pending.slice(0, end).replace(/\r$/, '')) + '\n');
    pending = pending.slice(end + 1);
  }
}
if (pending) process.stdout.write(respond(pending.replace(/\r$/, '')) + '\n');
