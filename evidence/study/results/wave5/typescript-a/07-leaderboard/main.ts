if (process.argv.length !== 2) { console.error('No arguments expected'); process.exit(2); }
const scores = new Map<string, number>();
const player = '[a-z][a-z0-9_]{0,15}';
const forms = [new RegExp(`^SCORE (${player}) (-?[0-9]{1,6})$`), new RegExp(`^(RANK|REMOVE) (${player})$`), /^TOP ([1-9][0-9]{0,2})$/, new RegExp(`^AROUND (${player}) ([0-9]{1,3})$`), /^COUNT$/];
function respond(line: string): string {
  if (!forms.some(form => form.test(line))) return 'ERR bad command';
  const [command, name, value] = line.split(' ');
  if (command === 'SCORE') { const total = (scores.get(name) ?? 0) + Number(value); scores.set(name, total); return `TOTAL ${total}`; }
  if (command === 'COUNT') return `COUNT ${scores.size}`;
  if (command === 'REMOVE') return scores.delete(name) ? 'OK' : 'ERR unknown player';
  if (command !== 'TOP' && !scores.has(name)) return 'ERR unknown player';
  const ordered = [...scores].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  let rank = 0;
  const entries = ordered.map(([name, total], i) => { if (i === 0 || total !== ordered[i-1][1]) rank = i + 1; return {name, total, rank, text: `${rank}:${name}:${total}`}; });
  if (command === 'TOP') return 'TOP' + entries.slice(0, Number(name)).map(entry => ' ' + entry.text).join('');
  const index = entries.findIndex(entry => entry.name === name);
  if (command === 'RANK') return `RANK ${entries[index].rank} ${entries[index].total}`;
  const distance = Number(value);
  return 'AROUND' + entries.slice(Math.max(0, index - distance), index + distance + 1).map(entry => ' ' + entry.text).join('');
}
process.stdin.setEncoding('utf8');
let pending = '';
for await (const chunk of process.stdin) {
  pending += chunk;
  let end: number;
  while ((end = pending.indexOf('\n')) !== -1) {
    process.stdout.write(respond(pending.slice(0, end).replace(/\r$/, '')) + '\n');
    pending = pending.slice(end + 1);
  }
}
if (pending !== '') process.stdout.write(respond(pending.replace(/\r$/, '')) + '\n');
