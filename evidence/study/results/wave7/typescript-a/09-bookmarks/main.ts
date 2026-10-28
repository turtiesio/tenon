import { appendFileSync, closeSync, mkdirSync, openSync, readFileSync, renameSync, statSync, truncateSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
if (process.argv.length !== 3) { console.error('Expected data directory'); process.exit(2); }
const directory = process.argv[2];
const journalPath = join(directory, 'journal'), snapshotPath = join(directory, 'snapshot');
type Bookmark = { url: string; tags: Set<string> };
type Command = { op: string; name?: string; url?: string; tag?: string };
const bookmarks = new Map<string, Bookmark>();
let sequence = 0n;
function parse(line: string): Command | undefined {
  let m: RegExpExecArray | null;
  if ((m = /^ADD ([a-z0-9-]{1,20}) ([\x21-\x7e]{1,200})$/.exec(line))) return { op: 'ADD', name: m[1], url: m[2] };
  if ((m = /^(DEL|GET) ([a-z0-9-]{1,20})$/.exec(line))) return { op: m[1], name: m[2] };
  if ((m = /^(TAG|UNTAG) ([a-z0-9-]{1,20}) ([a-z0-9]{1,12})$/.exec(line))) return { op: m[1], name: m[2], tag: m[3] };
  if ((m = /^FIND ([a-z0-9]{1,12})$/.exec(line))) return { op: 'FIND', tag: m[1] };
  if (line === 'COMPACT') return { op: 'COMPACT' };
}
function tags(bookmark: Bookmark): string { return [...bookmark.tags].sort().join(',') || '-'; }
function apply(command: Command): string {
  const { op, name, url, tag } = command;
  if (op === 'FIND') return [...bookmarks.keys()].sort().filter(n => bookmarks.get(n)!.tags.has(tag!)).join(' ') || '-';
  const bookmark = bookmarks.get(name!);
  if (op === 'ADD') {
    if (bookmark) return 'ERR exists';
    bookmarks.set(name!, { url: url!, tags: new Set() }); return 'OK';
  }
  if (!bookmark) return 'ERR no such bookmark';
  if (op === 'GET') return `${name} ${bookmark.url} ${tags(bookmark)}`;
  if (op === 'DEL') { bookmarks.delete(name!); return 'OK'; }
  if (op === 'TAG') { if (bookmark.tags.has(tag!)) return 'UNCHANGED'; bookmark.tags.add(tag!); return 'OK'; }
  if (!bookmark.tags.delete(tag!)) return 'UNCHANGED';
  return 'OK';
}
function readOptional(path: string): Buffer | undefined {
  try { return readFileSync(path); }
  catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined; throw error; }
}
function load(): void {
  try { if (!statSync(directory).isDirectory()) throw Error('Not a directory'); }
  catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') mkdirSync(directory); else throw error; }
  let snapshotSequence = 0n;
  const snapshot = readOptional(snapshotPath);
  if (snapshot !== undefined) {
    const content = snapshot.toString('latin1');
    if (!content.endsWith('\n')) throw Error('Invalid snapshot');
    const lines = content.slice(0, -1).split('\n');
    const header = /^bookmarks (0|[1-9][0-9]*)$/.exec(lines.shift()!);
    if (!header) throw Error('Invalid snapshot header');
    snapshotSequence = BigInt(header[1]);
    let previous = '';
    for (const line of lines) {
      const m = /^([a-z0-9-]{1,20}) ([\x21-\x7e]{1,200}) (-|[a-z0-9]{1,12}(?:,[a-z0-9]{1,12})*)$/.exec(line);
      if (!m || m[1] <= previous) throw Error('Invalid snapshot entry');
      const tagList = m[3] === '-' ? [] : m[3].split(',');
      if (tagList.some((tag, i) => i > 0 && tag <= tagList[i - 1])) throw Error('Invalid snapshot tags');
      bookmarks.set(m[1], { url: m[2], tags: new Set(tagList) }); previous = m[1];
    }
  }
  const journal = readOptional(journalPath);
  let completeLength = 0, last: bigint | undefined;
  if (journal !== undefined) {
    completeLength = journal.lastIndexOf(10) + 1;
    const complete = journal.subarray(0, completeLength).toString('latin1');
    const lines = completeLength ? complete.slice(0, -1).split('\n') : [];
    for (const line of lines) {
      const m = /^([1-9][0-9]*) (.+)$/.exec(line);
      if (!m) throw Error('Invalid journal record');
      const seq = BigInt(m[1]), command = parse(m[2]);
      if (!command || !['ADD', 'DEL', 'TAG', 'UNTAG'].includes(command.op)) throw Error('Invalid journal command');
      if (last === undefined ? seq > snapshotSequence + 1n : seq !== last + 1n) throw Error('Journal gap');
      if (seq > snapshotSequence && apply(command) !== 'OK') throw Error('Invalid replay');
      last = seq;
    }
    if (last !== undefined && last < snapshotSequence) throw Error('Incomplete journal');
  }
  sequence = last !== undefined && last > snapshotSequence ? last : snapshotSequence;
  // Defer repair until every complete record and the snapshot have validated.
  if (journal !== undefined && journal.length !== completeLength) truncateSync(journalPath, completeLength);
}
try { load(); }
catch (error) { console.error(String(error)); process.exit(1); }
function compact(): string {
  const lines = [`bookmarks ${sequence}`];
  for (const name of [...bookmarks.keys()].sort()) { const b = bookmarks.get(name)!; lines.push(`${name} ${b.url} ${tags(b)}`); }
  const temporary = join(directory, 'snapshot.tmp');
  const fd = openSync(temporary, 'w');
  try { writeFileSync(fd, lines.join('\n') + '\n'); } finally { closeSync(fd); }
  renameSync(temporary, snapshotPath);
  writeFileSync(journalPath, '');
  return `OK ${sequence}`;
}
function respond(raw: string): void {
  const line = raw.replace(/\r$/, ''), command = parse(line);
  let response = 'ERR bad command';
  if (command) {
    if (command.op === 'COMPACT') response = compact();
    else {
      response = apply(command);
      if (response === 'OK') {
        const next = sequence + 1n;
        appendFileSync(journalPath, `${next} ${line}\n`);
        sequence = next;
      }
    }
  }
  process.stdout.write(response + '\n');
}
try {
  process.stdin.setEncoding('utf8');
  let pending = '';
  for await (const chunk of process.stdin) {
    pending += chunk;
    let end: number;
    while ((end = pending.indexOf('\n')) >= 0) { respond(pending.slice(0, end)); pending = pending.slice(end + 1); }
  }
  if (pending.length) respond(pending);
} catch (error) { console.error(String(error)); process.exit(1); }
