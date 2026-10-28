const PLAYER = "[a-z][a-z0-9_]{0,15}";
const COMMANDS: [string, RegExp][] = [
  ["SCORE", new RegExp(`^SCORE (${PLAYER}) (-?[0-9]{1,6})$`)],
  ["RANK", new RegExp(`^RANK (${PLAYER})$`)],
  ["TOP", /^TOP ([1-9][0-9]{0,2})$/],
  ["AROUND", new RegExp(`^AROUND (${PLAYER}) ([0-9]{1,3})$`)],
  ["REMOVE", new RegExp(`^REMOVE (${PLAYER})$`)],
  ["COUNT", /^COUNT$/],
];

class Leaderboard {
  private totals = new Map<string, number>();
  // All existing players in leaderboard order, kept sorted incrementally.
  private order: string[] = [];

  private before(a: string, b: string): boolean {
    const ta = this.total(a);
    const tb = this.total(b);
    return ta !== tb ? ta > tb : a < b;
  }

  private insert(player: string): void {
    let lo = 0;
    let hi = this.order.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (this.before(this.order[mid], player)) lo = mid + 1;
      else hi = mid;
    }
    this.order.splice(lo, 0, player);
  }

  score(player: string, points: number): number {
    if (this.totals.has(player)) this.order.splice(this.order.indexOf(player), 1);
    const total = (this.totals.get(player) ?? 0) + points;
    this.totals.set(player, total);
    this.insert(player);
    return total;
  }

  remove(player: string): boolean {
    if (!this.totals.has(player)) return false;
    this.order.splice(this.order.indexOf(player), 1);
    this.totals.delete(player);
    return true;
  }

  has(player: string): boolean {
    return this.totals.has(player);
  }

  get count(): number {
    return this.totals.size;
  }

  total(player: string): number {
    return this.totals.get(player)!;
  }

  rank(player: string): number {
    const total = this.total(player);
    let higher = 0;
    for (const t of this.totals.values()) if (t > total) higher++;
    return higher + 1;
  }

  sorted(): readonly string[] {
    return this.order;
  }

  // Entries for positions [from, to) of the leaderboard order, with shared ranks.
  entries(from: number, to: number): string[] {
    const order = this.sorted();
    const result: string[] = [];
    // The rank at a position is 1 + the position of the first player with the same total.
    let first = from;
    while (first > 0 && this.total(order[first - 1]) === this.total(order[from])) first--;
    for (let i = from; i < to; i++) {
      const name = order[i];
      if (this.total(name) !== this.total(order[first])) first = i;
      result.push(`${first + 1}:${name}:${this.total(name)}`);
    }
    return result;
  }
}

function handle(board: Leaderboard, line: string): string {
  for (const [name, re] of COMMANDS) {
    const m = re.exec(line);
    if (!m) continue;
    switch (name) {
      case "SCORE":
        return `TOTAL ${board.score(m[1], Number(m[2]))}`;
      case "RANK":
        return board.has(m[1]) ? `RANK ${board.rank(m[1])} ${board.total(m[1])}` : "ERR unknown player";
      case "TOP": {
        const k = Math.min(Number(m[1]), board.count);
        return ["TOP", ...board.entries(0, k)].join(" ");
      }
      case "AROUND": {
        if (!board.has(m[1])) return "ERR unknown player";
        const d = Number(m[2]);
        const i = board.sorted().indexOf(m[1]);
        return ["AROUND", ...board.entries(Math.max(0, i - d), Math.min(board.count, i + d + 1))].join(" ");
      }
      case "REMOVE":
        return board.remove(m[1]) ? "OK" : "ERR unknown player";
      case "COUNT":
        return `COUNT ${board.count}`;
    }
  }
  return "ERR bad command";
}

function main(argv: string[]): void {
  if (argv.length > 0) {
    process.stderr.write("usage: leaderboard < commands\n");
    process.exit(2);
  }
  const board = new Leaderboard();
  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    process.stdout.write(handle(board, line) + "\n");
  };

  let pending = "";
  process.stdin.setEncoding("utf8");
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

main(process.argv.slice(2));
