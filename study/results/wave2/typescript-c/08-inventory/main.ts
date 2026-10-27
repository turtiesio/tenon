type HoldState = "active" | "expired" | "committed" | "released";

interface Hold {
  sku: string;
  qty: number;
  expiresAt: number;
  state: HoldState;
}

interface Stock {
  onHand: number;
  held: number;
}

const TIME_RE = /^[0-9]{1,12}$/;
const SKU_RE = /^[A-Z0-9-]{1,20}$/;
const NUMBER_RE = /^[0-9]{1,9}$/;

const BAD_COMMAND = "ERR bad command";

// Min-heap of [expiresAt, holdId] used to expire holds in time order.
class ExpiryHeap {
  private items: [number, number][] = [];

  get top(): [number, number] | undefined {
    return this.items[0];
  }

  push(item: [number, number]): void {
    const items = this.items;
    items.push(item);
    let i = items.length - 1;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (items[parent][0] <= items[i][0]) {
        break;
      }
      [items[parent], items[i]] = [items[i], items[parent]];
      i = parent;
    }
  }

  pop(): void {
    const items = this.items;
    const last = items.pop()!;
    if (items.length === 0) {
      return;
    }
    items[0] = last;
    let i = 0;
    while (true) {
      const left = 2 * i + 1;
      const right = left + 1;
      let smallest = i;
      if (left < items.length && items[left][0] < items[smallest][0]) {
        smallest = left;
      }
      if (right < items.length && items[right][0] < items[smallest][0]) {
        smallest = right;
      }
      if (smallest === i) {
        break;
      }
      [items[smallest], items[i]] = [items[i], items[smallest]];
      i = smallest;
    }
  }
}

class Inventory {
  private clock = 0;
  private stocks = new Map<string, Stock>();
  private holds = new Map<number, Hold>();
  private expiry = new ExpiryHeap();
  private nextId = 1;
  private counts = { active: 0, committed: 0, expired: 0, released: 0 };

  handle(line: string): string {
    const tokens = line.split(" ");
    if (tokens.length < 2 || !TIME_RE.test(tokens[0])) {
      return BAD_COMMAND;
    }
    const args = tokens.slice(2);
    const parsed = this.parse(tokens[1], args);
    if (parsed === null) {
      return BAD_COMMAND;
    }

    const time = Number(tokens[0]);
    if (time < this.clock) {
      return "ERR time went backwards";
    }
    this.clock = time;
    this.expireHolds(time);
    return parsed();
  }

  // Validates the arguments of a command and returns the action to run, or
  // null if the command is malformed.
  private parse(command: string, args: string[]): (() => string) | null {
    switch (command) {
      case "ADD":
      case "REMOVE": {
        if (args.length !== 2 || !SKU_RE.test(args[0]) || !NUMBER_RE.test(args[1])) {
          return null;
        }
        const qty = Number(args[1]);
        if (qty < 1) {
          return null;
        }
        return () => (command === "ADD" ? this.add(args[0], qty) : this.remove(args[0], qty));
      }
      case "RESERVE": {
        if (
          args.length !== 3 ||
          !SKU_RE.test(args[0]) ||
          !NUMBER_RE.test(args[1]) ||
          !NUMBER_RE.test(args[2])
        ) {
          return null;
        }
        const qty = Number(args[1]);
        const ttl = Number(args[2]);
        if (qty < 1 || ttl < 1) {
          return null;
        }
        return () => this.reserve(args[0], qty, ttl);
      }
      case "COMMIT":
      case "RELEASE": {
        if (args.length !== 1 || !NUMBER_RE.test(args[0])) {
          return null;
        }
        const id = Number(args[0]);
        return () => this.finish(id, command === "COMMIT");
      }
      case "AVAIL":
        if (args.length !== 1 || !SKU_RE.test(args[0])) {
          return null;
        }
        return () => this.avail(args[0]);
      case "STATS":
        return args.length === 0 ? () => this.stats() : null;
      default:
        return null;
    }
  }

  private stock(sku: string): Stock {
    let stock = this.stocks.get(sku);
    if (stock === undefined) {
      stock = { onHand: 0, held: 0 };
      this.stocks.set(sku, stock);
    }
    return stock;
  }

  private expireHolds(now: number): void {
    for (let top = this.expiry.top; top !== undefined && top[0] <= now; top = this.expiry.top) {
      this.expiry.pop();
      const hold = this.holds.get(top[1])!;
      if (hold.state === "active") {
        hold.state = "expired";
        this.stock(hold.sku).held -= hold.qty;
        this.counts.active--;
        this.counts.expired++;
      }
    }
  }

  private add(sku: string, qty: number): string {
    const stock = this.stock(sku);
    stock.onHand += qty;
    return `OK ${stock.onHand}`;
  }

  private remove(sku: string, qty: number): string {
    const stock = this.stock(sku);
    const available = stock.onHand - stock.held;
    if (qty > available) {
      return `ERR insufficient ${available}`;
    }
    stock.onHand -= qty;
    return `OK ${stock.onHand}`;
  }

  private reserve(sku: string, qty: number, ttl: number): string {
    const stock = this.stock(sku);
    const available = stock.onHand - stock.held;
    if (qty > available) {
      return `ERR insufficient ${available}`;
    }
    const id = this.nextId++;
    const expiresAt = this.clock + ttl;
    this.holds.set(id, { sku, qty, expiresAt, state: "active" });
    this.expiry.push([expiresAt, id]);
    stock.held += qty;
    this.counts.active++;
    return `HOLD ${id}`;
  }

  private finish(id: number, commit: boolean): string {
    const hold = this.holds.get(id);
    if (hold === undefined || hold.state === "committed" || hold.state === "released") {
      return "ERR no such hold";
    }
    if (hold.state === "expired") {
      return "ERR expired";
    }
    const stock = this.stock(hold.sku);
    stock.held -= hold.qty;
    this.counts.active--;
    if (commit) {
      stock.onHand -= hold.qty;
      hold.state = "committed";
      this.counts.committed++;
    } else {
      hold.state = "released";
      this.counts.released++;
    }
    return "OK";
  }

  private avail(sku: string): string {
    const stock = this.stock(sku);
    return `${sku} on_hand=${stock.onHand} held=${stock.held} available=${stock.onHand - stock.held}`;
  }

  private stats(): string {
    const c = this.counts;
    return `holds=${c.active} committed=${c.committed} expired=${c.expired} released=${c.released}`;
  }
}

function main(): void {
  if (process.argv.length > 2) {
    console.error("usage: inv (no arguments)");
    process.exitCode = 2;
    return;
  }

  const inventory = new Inventory();
  let pending = "";

  const respond = (rawLine: string) => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    process.stdout.write(inventory.handle(line) + "\n");
  };

  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let newline = pending.indexOf("\n");
    while (newline >= 0) {
      respond(pending.slice(0, newline));
      pending = pending.slice(newline + 1);
      newline = pending.indexOf("\n");
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") {
      respond(pending);
    }
  });
}

main();
