import * as fs from "node:fs";

const DENOMINATIONS = [5, 10, 20, 50, 100, 200] as const;
type Coins = Map<number, number>; // denomination -> count

interface Slot {
  name: string;
  price: number;
  count: number;
}

const SLOT = "([A-F][1-9])";

function emptyCoins(): Coins {
  return new Map(DENOMINATIONS.map((d) => [d, 0]));
}

function addCoins(into: Coins, from: Coins): void {
  for (const [d, n] of from) into.set(d, (into.get(d) ?? 0) + n);
}

function total(coins: Coins): number {
  let sum = 0;
  for (const [d, n] of coins) sum += d * n;
  return sum;
}

/** Greedy change from the available coins, largest first; null if it cannot be paid exactly. */
function makeChange(amount: number, available: Coins): Coins | null {
  const change = emptyCoins();
  let owed = amount;
  for (const d of [...DENOMINATIONS].reverse()) {
    const take = Math.min(available.get(d) ?? 0, Math.floor(owed / d));
    change.set(d, take);
    owed -= take * d;
  }
  return owed === 0 ? change : null;
}

function coinList(coins: Coins): string {
  const parts = [...DENOMINATIONS]
    .reverse()
    .filter((d) => (coins.get(d) ?? 0) > 0)
    .map((d) => `${d}x${coins.get(d)}`);
  return parts.length === 0 ? "-" : parts.join(" ");
}

class Machine {
  private tubes: Coins = emptyCoins();
  private escrow: Coins = emptyCoins();
  private slots = new Map<string, Slot>();

  handle(line: string): string {
    let m: RegExpExecArray | null;
    if ((m = new RegExp(`^LOAD ${SLOT} ([a-z]{1,12}) ([1-9][0-9]{0,3}) (0|[1-9][0-9]?)$`).exec(line))) {
      const price = Number(m[3]);
      if (price % 5 !== 0) return "ERR bad command";
      this.slots.set(m[1], { name: m[2], price, count: Number(m[4]) });
      return "OK";
    }
    if ((m = /^FILL (5|10|20|50|100|200) ([1-9][0-9]{0,2})$/.exec(line))) {
      const d = Number(m[1]);
      this.tubes.set(d, this.tubes.get(d)! + Number(m[2]));
      return "OK";
    }
    if ((m = /^INSERT ([1-9][0-9]{0,5})$/.exec(line))) {
      const coin = Number(m[1]);
      if (!this.escrow.has(coin)) return `REJECT ${m[1]}`;
      this.escrow.set(coin, this.escrow.get(coin)! + 1);
      return `CREDIT ${total(this.escrow)}`;
    }
    if ((m = new RegExp(`^SELECT ${SLOT}$`).exec(line))) return this.select(m[1]);
    if (line === "REFUND") {
      const response = `REFUND ${total(this.escrow)} ${coinList(this.escrow)}`;
      this.escrow = emptyCoins();
      return response;
    }
    if ((m = new RegExp(`^STOCK ${SLOT}$`).exec(line))) {
      const slot = this.slots.get(m[1]);
      if (slot === undefined) return "ERR no such slot";
      return `${m[1]} ${slot.name} ${slot.price} ${slot.count}`;
    }
    if (line === "COINS") {
      return DENOMINATIONS.map((d) => `${d}x${this.tubes.get(d)}`).join(" ");
    }
    return "ERR bad command";
  }

  private select(slotName: string): string {
    const slot = this.slots.get(slotName);
    if (slot === undefined) return "ERR no such slot";
    if (slot.count === 0) return "ERR sold out";
    const credit = total(this.escrow);
    if (credit < slot.price) return `ERR need ${slot.price - credit}`;

    const tubes = new Map(this.tubes);
    addCoins(tubes, this.escrow);
    const changeAmount = credit - slot.price;
    const change = makeChange(changeAmount, tubes);
    if (change === null) return "ERR no change";

    for (const [d, n] of change) tubes.set(d, tubes.get(d)! - n);
    this.tubes = tubes;
    this.escrow = emptyCoins();
    slot.count -= 1;
    return `VEND ${slot.name} ${changeAmount} ${coinList(change)}`;
  }
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("usage: vending (commands on stdin)\n");
    process.exit(2);
  }

  const machine = new Machine();
  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    fs.writeSync(1, machine.handle(line) + "\n");
  };

  // Lines are split on "\n" only (readline would also split on a lone "\r").
  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let nl: number;
    while ((nl = pending.indexOf("\n")) !== -1) {
      respond(pending.slice(0, nl));
      pending = pending.slice(nl + 1);
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") respond(pending);
  });
}

main();
