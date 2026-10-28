import { writeSync } from "node:fs";

const DENOMINATIONS = [5, 10, 20, 50, 100, 200] as const;
const DESCENDING = [...DENOMINATIONS].reverse();

type Coins = Map<number, number>; // denomination -> count

interface Slot {
  name: string;
  price: number;
  count: number;
}

const tubes: Coins = new Map(DENOMINATIONS.map((d) => [d, 0]));
let escrow: Coins = new Map();
const slots = new Map<string, Slot>();

const SLOT = /^[A-F][1-9]$/;
const NAME = /^[a-z]{1,12}$/;
const PRICE = /^[1-9][0-9]{0,3}$/;
const COUNT = /^(0|[1-9][0-9]?)$/;
const FILL_COUNT = /^[1-9][0-9]{0,2}$/;
const COIN = /^[1-9][0-9]{0,5}$/;

function isDenomination(n: number): boolean {
  return (DENOMINATIONS as readonly number[]).includes(n);
}

function credit(): number {
  let sum = 0;
  for (const [d, n] of escrow) sum += d * n;
  return sum;
}

// Coin list, largest first: "100x1 50x2", or "-" when empty.
function coinList(coins: Coins): string {
  const parts = DESCENDING.filter((d) => (coins.get(d) ?? 0) > 0).map((d) => `${d}x${coins.get(d)}`);
  return parts.length === 0 ? "-" : parts.join(" ");
}

// The fixed greedy change rule; null if the amount cannot be paid.
function makeChange(amount: number, available: Coins): Coins | null {
  const change: Coins = new Map();
  let owed = amount;
  for (const d of DESCENDING) {
    const take = Math.min(available.get(d) ?? 0, Math.floor(owed / d));
    if (take > 0) {
      change.set(d, take);
      owed -= take * d;
    }
  }
  return owed === 0 ? change : null;
}

function select(slotName: string): string {
  const slot = slots.get(slotName);
  if (slot === undefined) return "ERR no such slot";
  if (slot.count === 0) return "ERR sold out";
  const inserted = credit();
  if (inserted < slot.price) return `ERR need ${slot.price - inserted}`;

  const pool: Coins = new Map(DENOMINATIONS.map((d) => [d, (tubes.get(d) ?? 0) + (escrow.get(d) ?? 0)]));
  const owed = inserted - slot.price;
  const change = makeChange(owed, pool);
  if (change === null) return "ERR no change";

  for (const d of DENOMINATIONS) tubes.set(d, pool.get(d)! - (change.get(d) ?? 0));
  escrow = new Map();
  slot.count -= 1;
  return `VEND ${slot.name} ${owed} ${coinList(change)}`;
}

function handle(line: string): string {
  const bad = "ERR bad command";
  const t = line.split(" ");
  switch (t[0]) {
    case "LOAD": {
      if (t.length !== 5) return bad;
      const [, slot, name, price, count] = t;
      if (!SLOT.test(slot) || !NAME.test(name) || !PRICE.test(price) || !COUNT.test(count)) return bad;
      if (Number(price) % 5 !== 0) return bad;
      slots.set(slot, { name, price: Number(price), count: Number(count) });
      return "OK";
    }
    case "FILL": {
      if (t.length !== 3 || !COIN.test(t[1]) || !FILL_COUNT.test(t[2])) return bad;
      const coin = Number(t[1]);
      if (!isDenomination(coin)) return bad;
      tubes.set(coin, tubes.get(coin)! + Number(t[2]));
      return "OK";
    }
    case "INSERT": {
      if (t.length !== 2 || !COIN.test(t[1])) return bad;
      const coin = Number(t[1]);
      if (!isDenomination(coin)) return `REJECT ${coin}`;
      escrow.set(coin, (escrow.get(coin) ?? 0) + 1);
      return `CREDIT ${credit()}`;
    }
    case "SELECT":
      if (t.length !== 2 || !SLOT.test(t[1])) return bad;
      return select(t[1]);
    case "REFUND": {
      if (t.length !== 1) return bad;
      const response = `REFUND ${credit()} ${coinList(escrow)}`;
      escrow = new Map();
      return response;
    }
    case "STOCK": {
      if (t.length !== 2 || !SLOT.test(t[1])) return bad;
      const slot = slots.get(t[1]);
      return slot === undefined ? "ERR no such slot" : `${t[1]} ${slot.name} ${slot.price} ${slot.count}`;
    }
    case "COINS":
      if (t.length !== 1) return bad;
      return DENOMINATIONS.map((d) => `${d}x${tubes.get(d)}`).join(" ");
    default:
      return bad;
  }
}

// Synchronous write so every response is flushed immediately.
function writeLine(text: string): void {
  const buf = Buffer.from(text + "\n", "latin1");
  let offset = 0;
  while (offset < buf.length) {
    try {
      offset += writeSync(1, buf, offset);
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "EAGAIN") throw e;
    }
  }
}

function processLine(raw: string): void {
  writeLine(handle(raw.endsWith("\r") ? raw.slice(0, -1) : raw));
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("usage: vending (commands on stdin)\n");
    process.exitCode = 2;
    return;
  }
  // Split on "\n" only (readline would also split on a lone "\r").
  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let newline: number;
    while ((newline = pending.indexOf("\n")) !== -1) {
      processLine(pending.slice(0, newline));
      pending = pending.slice(newline + 1);
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") processLine(pending);
  });
}

main();
