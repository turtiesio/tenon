if (process.argv.length > 2) { console.error('No arguments allowed'); process.exit(2); }
const coins = [5, 10, 20, 50, 100, 200];
let tubes = coins.map(() => 0), escrow = coins.map(() => 0), credit = 0;
type Slot = { name: string; price: number; count: number };
const slots = new Map<string, Slot>();
function coinList(counts: number[]): string { return coins.map((coin, i) => counts[i] ? `${coin}x${counts[i]}` : '').reverse().filter(Boolean).join(' ') || '-'; }
function command(line: string): string {
  let match: RegExpExecArray | null;
  if ((match = /^LOAD ([A-F][1-9]) ([a-z]{1,12}) ([1-9][0-9]{0,3}) (0|[1-9][0-9]?)$/.exec(line))) {
    const price = Number(match[3]);
    if (price % 5) return 'ERR bad command';
    slots.set(match[1], { name: match[2], price, count: Number(match[4]) }); return 'OK';
  }
  if ((match = /^FILL (5|10|20|50|100|200) ([1-9][0-9]{0,2})$/.exec(line))) {
    tubes[coins.indexOf(Number(match[1]))] += Number(match[2]); return 'OK';
  }
  if ((match = /^INSERT ([1-9][0-9]{0,5})$/.exec(line))) {
    const coin = Number(match[1]), index = coins.indexOf(coin);
    if (index < 0) return `REJECT ${coin}`;
    escrow[index]++; credit += coin; return `CREDIT ${credit}`;
  }
  if ((match = /^(SELECT|STOCK) ([A-F][1-9])$/.exec(line))) {
    const slot = slots.get(match[2]);
    if (!slot) return 'ERR no such slot';
    if (match[1] === 'STOCK') return `${match[2]} ${slot.name} ${slot.price} ${slot.count}`;
    if (!slot.count) return 'ERR sold out';
    if (credit < slot.price) return `ERR need ${slot.price - credit}`;
    const available = tubes.map((n, i) => n + escrow[i]), change = coins.map(() => 0);
    let owed = credit - slot.price;
    for (let i = coins.length - 1; i >= 0; i--) {
      change[i] = Math.min(available[i], Math.floor(owed / coins[i]));
      available[i] -= change[i]; owed -= change[i] * coins[i];
    }
    if (owed) return 'ERR no change';
    const response = `VEND ${slot.name} ${credit - slot.price} ${coinList(change)}`;
    tubes = available; escrow.fill(0); credit = 0; slot.count--; return response;
  }
  if (line === 'REFUND') {
    const response = `REFUND ${credit} ${coinList(escrow)}`;
    escrow.fill(0); credit = 0; return response;
  }
  if (line === 'COINS') return coins.map((coin, i) => `${coin}x${tubes[i]}`).join(' ');
  return 'ERR bad command';
}
function respond(line: string): void { process.stdout.write(command(line.replace(/\r$/, '')) + '\n'); }
process.stdin.setEncoding('utf8');
let pending = '';
for await (const chunk of process.stdin) {
  pending += chunk;
  let end: number;
  while ((end = pending.indexOf('\n')) >= 0) { respond(pending.slice(0, end)); pending = pending.slice(end + 1); }
}
if (pending.length) respond(pending);
