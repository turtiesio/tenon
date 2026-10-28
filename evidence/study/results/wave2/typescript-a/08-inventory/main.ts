if (process.argv.length !== 2) {
  console.error('No arguments expected');
  process.exit(2);
}
type Stock = { onHand: bigint; held: bigint };
type Hold = { stock: Stock; qty: bigint; expiry: number; state: 'active' | 'committed' | 'expired' | 'released' };
const stocks = new Map<string, Stock>();
const holds: Hold[] = [];
const heap: Hold[] = [];
let clock = 0, active = 0, committed = 0, expired = 0, released = 0;
function enqueue(hold: Hold): void {
  let i = heap.length;
  heap.push(hold);
  while (i > 0) {
    const parent = Math.floor((i - 1) / 2);
    if (heap[parent].expiry <= hold.expiry) break;
    heap[i] = heap[parent];
    i = parent;
  }
  heap[i] = hold;
}
function dequeue(): Hold {
  const first = heap[0];
  const last = heap.pop()!;
  if (heap.length) {
    let i = 0;
    while (i * 2 + 1 < heap.length) {
      let child = i * 2 + 1;
      if (child + 1 < heap.length && heap[child + 1].expiry < heap[child].expiry) child++;
      if (heap[child].expiry >= last.expiry) break;
      heap[i] = heap[child];
      i = child;
    }
    heap[i] = last;
  }
  return first;
}
const prefix = '([0-9]{1,12}) ';
const sku = '([A-Z0-9-]{1,20})';
const qty = '([0-9]{1,9})';
const patterns = [
  new RegExp(`^${prefix}(ADD|REMOVE) ${sku} ${qty}$`),
  new RegExp(`^${prefix}(RESERVE) ${sku} ${qty} ${qty}$`),
  new RegExp(`^${prefix}(COMMIT|RELEASE) ${qty}$`),
  new RegExp(`^${prefix}(AVAIL) ${sku}$`),
  new RegExp(`^${prefix}(STATS)$`),
];
function respond(line: string): string {
  const match = patterns.map(pattern => pattern.exec(line)).find(Boolean);
  if (!match) return 'ERR bad command';
  const command = match[2];
  if (['ADD', 'REMOVE', 'RESERVE'].includes(command) && (BigInt(match[4]) === 0n || (command === 'RESERVE' && BigInt(match[5]) === 0n))) return 'ERR bad command';
  const time = Number(match[1]);
  if (time < clock) return 'ERR time went backwards';
  clock = time;
  while (heap.length && heap[0].expiry <= time) {
    const hold = dequeue();
    if (hold.state !== 'active') continue;
    hold.state = 'expired';
    hold.stock.held -= hold.qty;
    active--;
    expired++;
  }
  if (command === 'STATS') return `holds=${active} committed=${committed} expired=${expired} released=${released}`;
  if (command === 'COMMIT' || command === 'RELEASE') {
    const hold = holds[Number(match[3]) - 1];
    if (hold?.state === 'expired') return 'ERR expired';
    if (hold?.state !== 'active') return 'ERR no such hold';
    hold.stock.held -= hold.qty;
    active--;
    if (command === 'COMMIT') {
      hold.stock.onHand -= hold.qty;
      hold.state = 'committed';
      committed++;
    } else {
      hold.state = 'released';
      released++;
    }
    return 'OK';
  }
  const name = match[3];
  const stock = stocks.get(name) ?? { onHand: 0n, held: 0n };
  stocks.set(name, stock);
  const available = stock.onHand - stock.held;
  if (command === 'AVAIL') return `${name} on_hand=${stock.onHand} held=${stock.held} available=${available}`;
  const quantity = BigInt(match[4]);
  if (command === 'ADD') { stock.onHand += quantity; return `OK ${stock.onHand}`; }
  if (quantity > available) return `ERR insufficient ${available}`;
  if (command === 'REMOVE') { stock.onHand -= quantity; return `OK ${stock.onHand}`; }
  const hold: Hold = { stock, qty: quantity, expiry: time + Number(match[5]), state: 'active' };
  holds.push(hold);
  enqueue(hold);
  stock.held += quantity;
  active++;
  return `HOLD ${holds.length}`;
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
