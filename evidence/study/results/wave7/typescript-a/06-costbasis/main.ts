import { readFileSync } from 'node:fs';
if (process.argv.length > 2) { console.error('No arguments allowed'); process.exit(2); }
type Lot = { quantity: bigint; cost: bigint };
const holdings = new Map<string, Lot[]>();
function money(cents: bigint): string { const n = cents < 0n ? -cents : cents; return `${cents < 0n ? '-' : ''}${n / 100n}.${String(n % 100n).padStart(2, '0')}`; }
const lines = readFileSync(0, 'utf8').split('\n');
if (lines.at(-1) === '') lines.pop();
let total = 0n, failed = false;
const output: string[] = [];
for (let i = 0; i < lines.length; i++) {
  const line = lines[i].replace(/\r$/, ''), prefix = `${i + 1}: `;
  if (!line || line.startsWith('#')) continue;
  const trade = /^(BUY|SELL) ([A-Z]{1,5}) ([1-9][0-9]{0,5}) ((?:0|[1-9][0-9]{0,5})\.[0-9]{2})$/.exec(line);
  const split = /^SPLIT ([A-Z]{1,5}) ([2-9]|10)$/.exec(line);
  if (!trade && !split) { output.push(prefix + 'ERR bad line'); failed = true; continue; }
  const symbol = trade ? trade[2] : split![1];
  const lots = holdings.get(symbol) ?? [];
  const held = lots.reduce((sum, lot) => sum + lot.quantity, 0n);
  if (split) {
    if (!lots.length) { output.push(prefix + `ERR not held ${symbol}`); failed = true; }
    else { const ratio = BigInt(split[2]); for (const lot of lots) lot.quantity *= ratio; output.push(prefix + `SPLIT ${symbol} ${ratio} held=${held * ratio}`); }
    continue;
  }
  const quantity = BigInt(trade![3]), price = BigInt(trade![4].replace('.', ''));
  if (trade![1] === 'BUY') { lots.push({ quantity, cost: quantity * price }); holdings.set(symbol, lots); continue; }
  if (quantity > held) { output.push(prefix + `ERR insufficient ${symbol} held=${held}`); failed = true; continue; }
  let remaining = quantity, cost = 0n;
  while (remaining > 0n) {
    const lot = lots[0];
    if (remaining >= lot.quantity) { remaining -= lot.quantity; cost += lot.cost; lots.shift(); }
    else {
      const part = (2n * lot.cost * remaining + lot.quantity) / (2n * lot.quantity);
      lot.quantity -= remaining; lot.cost -= part; cost += part; remaining = 0n;
    }
  }
  const proceeds = quantity * price, gain = proceeds - cost;
  total += gain;
  output.push(prefix + `SELL ${symbol} ${quantity} proceeds=${money(proceeds)} cost=${money(cost)} gain=${money(gain)}`);
}
for (const symbol of [...holdings.keys()].sort()) {
  const lots = holdings.get(symbol)!;
  if (lots.length) output.push(`HOLD ${symbol} ${lots.reduce((s, l) => s + l.quantity, 0n)} cost=${money(lots.reduce((s, l) => s + l.cost, 0n))} lots=${lots.length}`);
}
output.push(`TOTAL gain=${money(total)}`);
console.log(output.join('\n'));
process.exitCode = failed ? 1 : 0;
