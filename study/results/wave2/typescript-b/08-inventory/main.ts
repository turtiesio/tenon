type HoldState = "active" | "committed" | "released" | "expired";

interface Hold {
  id: number;
  sku: string;
  qty: number;
  expiresAt: number;
  state: HoldState;
}

interface Stock {
  onHand: number;
  held: number;
}

type Command =
  | { kind: "ADD" | "REMOVE"; t: number; sku: string; qty: number }
  | { kind: "RESERVE"; t: number; sku: string; qty: number; ttl: number }
  | { kind: "COMMIT" | "RELEASE"; t: number; id: number }
  | { kind: "AVAIL"; t: number; sku: string }
  | { kind: "STATS"; t: number };

const TIME_RE = /^[0-9]{1,12}$/;
const SKU_RE = /^[A-Z0-9-]{1,20}$/;
const COUNT_RE = /^[0-9]{1,9}$/;

function parsePositive(s: string): number | null {
  if (!COUNT_RE.test(s)) {
    return null;
  }
  const n = Number(s);
  return n >= 1 ? n : null;
}

function parseCommand(line: string): Command | null {
  const tokens = line.split(" ");
  if (tokens.length < 2 || !TIME_RE.test(tokens[0])) {
    return null;
  }
  const t = Number(tokens[0]);
  const kind = tokens[1];
  const args = tokens.slice(2);
  switch (kind) {
    case "ADD":
    case "REMOVE": {
      if (args.length !== 2 || !SKU_RE.test(args[0])) {
        return null;
      }
      const qty = parsePositive(args[1]);
      return qty === null ? null : { kind, t, sku: args[0], qty };
    }
    case "RESERVE": {
      if (args.length !== 3 || !SKU_RE.test(args[0])) {
        return null;
      }
      const qty = parsePositive(args[1]);
      const ttl = parsePositive(args[2]);
      return qty === null || ttl === null ? null : { kind, t, sku: args[0], qty, ttl };
    }
    case "COMMIT":
    case "RELEASE":
      if (args.length !== 1 || !COUNT_RE.test(args[0])) {
        return null;
      }
      return { kind, t, id: Number(args[0]) };
    case "AVAIL":
      if (args.length !== 1 || !SKU_RE.test(args[0])) {
        return null;
      }
      return { kind, t, sku: args[0] };
    case "STATS":
      return args.length === 0 ? { kind, t } : null;
    default:
      return null;
  }
}

// Min-heap of holds ordered by expiry time.
class ExpiryHeap {
  private readonly items: Hold[] = [];

  get size(): number {
    return this.items.length;
  }

  peek(): Hold | undefined {
    return this.items[0];
  }

  push(hold: Hold): void {
    const items = this.items;
    items.push(hold);
    let i = items.length - 1;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (items[parent].expiresAt <= items[i].expiresAt) {
        break;
      }
      [items[parent], items[i]] = [items[i], items[parent]];
      i = parent;
    }
  }

  pop(): Hold | undefined {
    const items = this.items;
    const top = items[0];
    const last = items.pop();
    if (items.length > 0 && last !== undefined) {
      items[0] = last;
      let i = 0;
      while (true) {
        const left = 2 * i + 1;
        const right = left + 1;
        let smallest = i;
        if (left < items.length && items[left].expiresAt < items[smallest].expiresAt) {
          smallest = left;
        }
        if (right < items.length && items[right].expiresAt < items[smallest].expiresAt) {
          smallest = right;
        }
        if (smallest === i) {
          break;
        }
        [items[smallest], items[i]] = [items[i], items[smallest]];
        i = smallest;
      }
    }
    return top;
  }
}

class Inventory {
  private clock = 0;
  private nextId = 1;
  private readonly stock = new Map<string, Stock>();
  private readonly holds = new Map<number, Hold>();
  private readonly expiryQueue = new ExpiryHeap();
  private readonly counts: Record<HoldState, number> = { active: 0, committed: 0, released: 0, expired: 0 };

  handle(line: string): string {
    const command = parseCommand(line);
    if (command === null) {
      return "ERR bad command";
    }
    if (command.t < this.clock) {
      return "ERR time went backwards";
    }
    this.clock = command.t;
    this.expireHolds();

    switch (command.kind) {
      case "ADD": {
        const stock = this.stockFor(command.sku);
        stock.onHand += command.qty;
        return `OK ${stock.onHand}`;
      }
      case "REMOVE": {
        const stock = this.stockFor(command.sku);
        const available = stock.onHand - stock.held;
        if (command.qty > available) {
          return `ERR insufficient ${available}`;
        }
        stock.onHand -= command.qty;
        return `OK ${stock.onHand}`;
      }
      case "RESERVE": {
        const stock = this.stockFor(command.sku);
        const available = stock.onHand - stock.held;
        if (command.qty > available) {
          return `ERR insufficient ${available}`;
        }
        const hold: Hold = {
          id: this.nextId++,
          sku: command.sku,
          qty: command.qty,
          expiresAt: command.t + command.ttl,
          state: "active",
        };
        stock.held += hold.qty;
        this.holds.set(hold.id, hold);
        this.expiryQueue.push(hold);
        this.counts.active++;
        return `HOLD ${hold.id}`;
      }
      case "COMMIT":
      case "RELEASE": {
        const hold = this.holds.get(command.id);
        if (hold === undefined || hold.state === "committed" || hold.state === "released") {
          return "ERR no such hold";
        }
        if (hold.state === "expired") {
          return "ERR expired";
        }
        const stock = this.stockFor(hold.sku);
        if (command.kind === "COMMIT") {
          stock.onHand -= hold.qty;
          this.finish(hold, "committed");
        } else {
          this.finish(hold, "released");
        }
        return "OK";
      }
      case "AVAIL": {
        const stock = this.stock.get(command.sku) ?? { onHand: 0, held: 0 };
        return `${command.sku} on_hand=${stock.onHand} held=${stock.held} available=${stock.onHand - stock.held}`;
      }
      case "STATS":
        return `holds=${this.counts.active} committed=${this.counts.committed} expired=${this.counts.expired} released=${this.counts.released}`;
    }
  }

  private stockFor(sku: string): Stock {
    let stock = this.stock.get(sku);
    if (stock === undefined) {
      stock = { onHand: 0, held: 0 };
      this.stock.set(sku, stock);
    }
    return stock;
  }

  private finish(hold: Hold, state: HoldState): void {
    this.stockFor(hold.sku).held -= hold.qty;
    this.counts.active--;
    this.counts[state]++;
    hold.state = state;
  }

  private expireHolds(): void {
    let next = this.expiryQueue.peek();
    while (next !== undefined && next.expiresAt <= this.clock) {
      this.expiryQueue.pop();
      if (next.state === "active") {
        this.finish(next, "expired");
      }
      next = this.expiryQueue.peek();
    }
  }
}

function main(argv: string[]): void {
  if (argv.length > 0) {
    process.stderr.write("usage: inv (takes no arguments)\n");
    process.exitCode = 2;
    return;
  }

  const inventory = new Inventory();
  const respond = (rawLine: string): void => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    process.stdout.write(inventory.handle(line) + "\n");
  };

  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let start = 0;
    let newline = pending.indexOf("\n", start);
    while (newline >= 0) {
      respond(pending.slice(start, newline));
      start = newline + 1;
      newline = pending.indexOf("\n", start);
    }
    pending = pending.slice(start);
  });
  process.stdin.on("end", () => {
    if (pending !== "") {
      respond(pending);
    }
  });
}

main(process.argv.slice(2));
