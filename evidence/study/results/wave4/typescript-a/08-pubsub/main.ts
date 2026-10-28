if (process.argv.length > 2) { console.error('No arguments expected'); process.exit(2); }
type Client = {subscriptions: Map<string, string[]>; mailbox: string[]; dropped: number};
const clients = new Map<string, Client>();
const validClient = (s: string) => /^[a-z][a-z0-9]{0,15}$/.test(s);
function validTopic(s: string, pattern: boolean): boolean {
  const parts = s.split('.');
  return parts.length <= 8 && parts.every((p, i) => /^[a-z0-9]{1,16}$/.test(p) || (pattern && (p === '*' || (p === '#' && i === parts.length - 1))));
}
function getClient(name: string): Client {
  let client = clients.get(name);
  if (!client) { client = {subscriptions: new Map(), mailbox: [], dropped: 0}; clients.set(name, client); }
  return client;
}
function matches(pattern: string[], topic: string[]): boolean {
  const hash = pattern.at(-1) === '#';
  const length = pattern.length - (hash ? 1 : 0);
  if (hash ? topic.length < length : topic.length !== length) return false;
  for (let i = 0; i < length; i++) if (pattern[i] !== '*' && pattern[i] !== topic[i]) return false;
  return true;
}
function command(line: string): string {
  const tokens = line.split(' '), [action, name, value] = tokens;
  if ((action === 'SUB' || action === 'UNSUB') && tokens.length === 3 && validClient(name) && validTopic(value, true)) {
    const client = getClient(name);
    if (action === 'SUB') {
      if (client.subscriptions.has(value)) return 'ERR already subscribed';
      client.subscriptions.set(value, value.split('.')); return 'OK';
    }
    return client.subscriptions.delete(value) ? 'OK' : 'ERR not subscribed';
  }
  if (action === 'PUB' && tokens.length === 3 && validTopic(name, false) && /^[A-Za-z0-9_.!?-]{1,32}$/.test(value)) {
    const topic = name.split('.');
    let delivered = 0;
    for (const client of clients.values()) {
      if (![...client.subscriptions.values()].some(pattern => matches(pattern, topic))) continue;
      if (client.mailbox.length === 3) { client.mailbox.shift(); client.dropped++; }
      client.mailbox.push(`${name}=${value}`); delivered++;
    }
    return `DELIVERED ${delivered}`;
  }
  if (action === 'POLL' && tokens.length === 3 && validClient(name) && /^[1-9][0-9]{0,2}$/.test(value)) {
    const messages = getClient(name).mailbox.splice(0, Number(value));
    return `MSGS ${messages.length}${messages.length ? ' ' + messages.join(' ') : ''}`;
  }
  if (action === 'STATS' && tokens.length === 2 && validClient(name)) {
    const client = getClient(name);
    return `subs=${client.subscriptions.size} queued=${client.mailbox.length} dropped=${client.dropped}`;
  }
  return 'ERR bad command';
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
process.stdin.on('end', () => { if (pending.length) respond(pending); });
