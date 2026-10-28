import { appendFileSync, mkdirSync, readFileSync, statSync, truncateSync } from 'node:fs';
import { join } from 'node:path';
const args = process.argv.slice(2);
if (args.length !== 1) { console.error('Usage: helpdesk DIR'); process.exit(2); }
const logPath = join(args[0], 'tickets.log');
type Ticket = { customer: string; title: string; agent: string; closed: boolean };
const tickets = new Map<string, Ticket>();
let next = 1;
const name = '[a-z0-9]{1,12}', id = 'T[1-9][0-9]{0,8}';
const openPattern = new RegExp(`^OPEN (${name}) ([\\x21-\\x7E](?:[\\x20-\\x7E]{0,58}[\\x21-\\x7E])?)$`);
const assignPattern = new RegExp(`^ASSIGN (${id}) (${name})$`);
const ticketPattern = new RegExp(`^(CLOSE|REOPEN|SHOW) (${id})$`);
const queuePattern = new RegExp(`^QUEUE (${name}|-)$`);
function command(line: string, persist: boolean): string {
  function record(text: string): void { if (persist) appendFileSync(logPath, text + '\n', 'ascii'); }
  let match = openPattern.exec(line);
  if (match) {
    const ticketId = `T${next}`;
    record(`OPEN ${ticketId} ${match[1]} ${match[2]}`);
    tickets.set(ticketId, { customer: match[1], title: match[2], agent: '-', closed: false });
    next++; return ticketId;
  }
  match = queuePattern.exec(line);
  if (match) return [...tickets].filter(([, t]) => !t.closed && t.agent === match![1]).map(([id]) => id).join(' ') || '-';
  match = assignPattern.exec(line);
  let operation: string, ticketId: string, agent = '';
  if (match) { operation = 'ASSIGN'; ticketId = match[1]; agent = match[2]; }
  else {
    match = ticketPattern.exec(line);
    if (!match) return 'ERR bad command';
    operation = match[1]; ticketId = match[2];
  }
  const ticket = tickets.get(ticketId);
  if (!ticket) return 'ERR no such ticket';
  if (operation === 'SHOW') return `${ticketId} ${ticket.closed ? 'closed' : 'open'} ${ticket.customer} ${ticket.agent} ${ticket.title}`;
  if ((operation === 'ASSIGN' || operation === 'CLOSE') && ticket.closed) return 'ERR closed';
  if (operation === 'REOPEN' && !ticket.closed) return 'ERR not closed';
  if (operation === 'ASSIGN' && ticket.agent === agent) return 'UNCHANGED';
  record(line);
  if (operation === 'ASSIGN') ticket.agent = agent;
  else ticket.closed = operation === 'CLOSE';
  return 'OK';
}
try {
  try { if (!statSync(args[0]).isDirectory()) throw new Error('Not a directory'); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    mkdirSync(args[0]);
  }
  let data: Buffer;
  try { data = readFileSync(logPath); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; data = Buffer.alloc(0); }
  const completeLength = data.lastIndexOf(10) + 1;
  const complete = data.subarray(0, completeLength).toString('latin1');
  const records = completeLength ? complete.slice(0, -1).split('\n') : [];
  const journalOpen = new RegExp(`^OPEN (${id}) (${name}) (.*)$`);
  for (const line of records) {
    const match = journalOpen.exec(line);
    if (match) {
      if (match[1] !== `T${next}` || command(`OPEN ${match[2]} ${match[3]}`, false) !== match[1]) throw new Error('Invalid OPEN record');
    } else {
      if (!assignPattern.test(line) && !/^(CLOSE|REOPEN) T[1-9][0-9]{0,8}$/.test(line)) throw new Error('Invalid journal record');
      if (command(line, false) !== 'OK') throw new Error('Invalid journal transition');
    }
  }
  if (completeLength !== data.length) truncateSync(logPath, completeLength);
} catch (error) { console.error(String(error)); process.exit(1); }
function respond(line: string): void {
  try { process.stdout.write(command(line, true) + '\n'); }
  catch (error) { console.error(String(error)); process.exit(1); }
}
let pending = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk: string) => {
  pending += chunk;
  let newline: number;
  while ((newline = pending.indexOf('\n')) !== -1) {
    const line = pending.slice(0, newline).replace(/\r$/, '');
    pending = pending.slice(newline + 1);
    respond(line);
  }
});
process.stdin.on('end', () => { if (pending.length) respond(pending.replace(/\r$/, '')); });
