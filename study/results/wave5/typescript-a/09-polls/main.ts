import { closeSync, existsSync, mkdirSync, openSync, readFileSync, statSync, truncateSync, writeSync } from 'node:fs';
import { join } from 'node:path';
function fail(code: number): never { console.error('Invalid directory, journal, or arguments'); process.exit(code); }
const args = process.argv.slice(2);
if (args.length !== 1) fail(2);
const journal = join(args[0], 'polls.log');
type Poll = {options: string[]; votes: Map<string, string>; closed: boolean};
const polls = new Map<string, Poll>();
function apply(line: string): {response: string; changed: boolean} {
  const tokens = line.split(' '), [command, name] = tokens;
  const validTokens = tokens.slice(1).every(token => /^[a-z0-9]{1,12}$/.test(token));
  const valid = validTokens && (command === 'CREATE' ? tokens.length >= 4 && tokens.length <= 11 && new Set(tokens.slice(2)).size === tokens.length - 2 : command === 'VOTE' ? tokens.length === 4 : (command === 'CLOSE' || command === 'RESULT') && tokens.length === 2);
  const reply = (response: string, changed = false) => ({response, changed});
  if (!valid) return reply('ERR bad command');
  if (command === 'CREATE') {
    if (polls.has(name)) return reply('ERR poll exists');
    polls.set(name, {options: tokens.slice(2), votes: new Map(), closed: false});
    return reply('OK', true);
  }
  const poll = polls.get(name);
  if (!poll) return reply('ERR no such poll');
  if (command === 'RESULT') {
    const counts = new Map(poll.options.map(option => [option, 0]));
    for (const option of poll.votes.values()) counts.set(option, counts.get(option)! + 1);
    return reply(`${name} ${poll.closed ? 'closed' : 'open'}${poll.options.map(option => ` ${option}=${counts.get(option)}`).join('')}`);
  }
  if (poll.closed) return reply('ERR poll closed');
  if (command === 'CLOSE') { poll.closed = true; return reply('OK', true); }
  const [, , voter, option] = tokens;
  if (!poll.options.includes(option)) return reply('ERR no such option');
  const previous = poll.votes.get(voter);
  if (previous === option) return reply('UNCHANGED');
  poll.votes.set(voter, option);
  return reply(previous === undefined ? 'VOTED' : 'CHANGED', true);
}
try {
  if (!existsSync(args[0])) mkdirSync(args[0]);
  if (!statSync(args[0]).isDirectory()) fail(1);
  if (existsSync(journal)) {
    const bytes = readFileSync(journal);
    const end = bytes.lastIndexOf(10) + 1;
    const complete = bytes.subarray(0, end).toString('utf8');
    const records = complete === '' ? [] : complete.slice(0, -1).split('\n');
    for (const record of records) if (!apply(record).changed) fail(1);
    if (end !== bytes.length) truncateSync(journal, end);
  }
} catch { fail(1); }
let descriptor: number | undefined;
function respond(raw: string) {
  const line = raw.replace(/\r$/, '');
  const result = apply(line);
  if (result.changed) {
    try {
      descriptor ??= openSync(journal, 'a');
      const bytes = Buffer.from(line + '\n');
      let offset = 0;
      while (offset < bytes.length) offset += writeSync(descriptor, bytes, offset, bytes.length - offset);
    } catch { fail(1); }
  }
  process.stdout.write(result.response + '\n');
}
process.stdin.setEncoding('utf8');
let pending = '';
for await (const chunk of process.stdin) {
  pending += chunk;
  let end: number;
  while ((end = pending.indexOf('\n')) !== -1) { respond(pending.slice(0, end)); pending = pending.slice(end + 1); }
}
if (pending !== '') respond(pending);
if (descriptor !== undefined) closeSync(descriptor);
