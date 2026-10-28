if (process.argv.length > 2) { console.error('Usage: locks'); process.exit(2); }
type Mode = 'S' | 'X';
type Request = { client: string; mode: Mode };
type Resource = { holders: Map<string, Mode>; queue: Request[] };
const resources = new Map<string, Resource>();
function resource(name: string): Resource {
  let value = resources.get(name);
  if (!value) { value = { holders: new Map(), queue: [] }; resources.set(name, value); }
  return value;
}
function compatible(res: Resource, mode: Mode): boolean {
  return res.holders.size === 0 || (mode === 'S' && [...res.holders.values()].every(m => m === 'S'));
}
function pump(name: string): string[] {
  const res = resource(name), grants: string[] = [];
  while (res.queue.length && compatible(res, res.queue[0].mode)) {
    const request = res.queue.shift()!;
    res.holders.set(request.client, request.mode);
    grants.push(`${request.client}:${name}:${request.mode}`);
  }
  return grants;
}
const namePattern = '[a-z0-9]{1,12}';
const lockPattern = new RegExp(`^LOCK (${namePattern}) (${namePattern}) (S|X)$`);
const unlockPattern = new RegExp(`^UNLOCK (${namePattern}) (${namePattern})$`);
const singlePattern = new RegExp(`^(DROP|STATUS|HELD) (${namePattern})$`);
function handle(line: string): string {
  let match = lockPattern.exec(line);
  if (match) {
    const [, client, name, modeText] = match, mode = modeText as Mode, res = resource(name);
    if (res.holders.has(client)) return 'ERR already held';
    if (res.queue.some(r => r.client === client)) return 'ERR already waiting';
    if (!res.queue.length && compatible(res, mode)) { res.holders.set(client, mode); return 'GRANTED'; }
    res.queue.push({ client, mode }); return 'WAITING';
  }
  match = unlockPattern.exec(line);
  if (match) {
    const [, client, name] = match, res = resources.get(name);
    if (!res || !res.holders.delete(client)) return 'ERR not held';
    return ['OK', ...pump(name)].join(' ');
  }
  match = singlePattern.exec(line);
  if (!match) return 'ERR bad command';
  const [, command, name] = match;
  if (command === 'STATUS') {
    const res = resources.get(name);
    const holders = res ? [...res.holders.keys()].sort().map(c => `${c}:${res.holders.get(c)}`).join(',') : '';
    const queue = res?.queue.map(r => `${r.client}:${r.mode}`).join(',');
    return `${name} holders=${holders || '-'} queue=${queue || '-'}`;
  }
  if (command === 'HELD') {
    return [...resources.keys()].sort().filter(r => resources.get(r)!.holders.has(name)).map(r => `${r}:${resources.get(r)!.holders.get(name)}`).join(',') || '-';
  }
  let released = 0, cancelled = 0;
  const affected: string[] = [];
  for (const [resName, res] of resources) {
    const before = res.queue.length;
    res.queue = res.queue.filter(r => r.client !== name);
    const removed = before - res.queue.length;
    const held = res.holders.delete(name);
    cancelled += removed; if (held) released++;
    if (removed || held) affected.push(resName);
  }
  const grants = affected.sort().flatMap(pump);
  return [`OK released=${released} cancelled=${cancelled}`, ...grants].join(' ');
}
let pending = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk: string) => {
  pending += chunk;
  let newline: number;
  while ((newline = pending.indexOf('\n')) !== -1) {
    const line = pending.slice(0, newline).replace(/\r$/, '');
    pending = pending.slice(newline + 1);
    process.stdout.write(handle(line) + '\n');
  }
});
process.stdin.on('end', () => {
  if (pending.length) process.stdout.write(handle(pending.replace(/\r$/, '')) + '\n');
});
