const PLAYER = /^[a-z][a-z0-9_]{0,15}$/;
const POINTS = /^-?[0-9]{1,6}$/;
const TOP_K = /^[1-9][0-9]{0,2}$/;
const DEPTH = /^[0-9]{1,3}$/;

interface Entry {
  rank: number;
  player: string;
  total: number;
}

const BAD = "ERR bad command";
const UNKNOWN = "ERR unknown player";

class Leaderboard {
  private totals = new Map<string, number>();

  /** All players in leaderboard order, with their shared ranks. */
  private entries(): Entry[] {
    const sorted = [...this.totals.entries()].sort(([an, at], [bn, bt]) =>
      bt !== at ? bt - at : an < bn ? -1 : an > bn ? 1 : 0,
    );
    const result: Entry[] = [];
    sorted.forEach(([player, total], i) => {
      const rank = i > 0 && result[i - 1].total === total ? result[i - 1].rank : i + 1;
      result.push({ rank, player, total });
    });
    return result;
  }

  private static show(entries: Entry[]): string {
    return entries.map((e) => ` ${e.rank}:${e.player}:${e.total}`).join("");
  }

  handle(line: string): string {
    const parts = line.split(" ");
    const [cmd, a, b] = parts;
    switch (cmd) {
      case "SCORE": {
        if (parts.length !== 3 || !PLAYER.test(a) || !POINTS.test(b)) return BAD;
        const total = (this.totals.get(a) ?? 0) + Number(b);
        this.totals.set(a, total);
        return `TOTAL ${total}`;
      }
      case "RANK": {
        if (parts.length !== 2 || !PLAYER.test(a)) return BAD;
        const e = this.entries().find((x) => x.player === a);
        return e === undefined ? UNKNOWN : `RANK ${e.rank} ${e.total}`;
      }
      case "TOP": {
        if (parts.length !== 2 || !TOP_K.test(a)) return BAD;
        return "TOP" + Leaderboard.show(this.entries().slice(0, Number(a)));
      }
      case "AROUND": {
        if (parts.length !== 3 || !PLAYER.test(a) || !DEPTH.test(b)) return BAD;
        const all = this.entries();
        const i = all.findIndex((x) => x.player === a);
        if (i < 0) return UNKNOWN;
        const d = Number(b);
        return "AROUND" + Leaderboard.show(all.slice(Math.max(0, i - d), Math.min(all.length - 1, i + d) + 1));
      }
      case "REMOVE": {
        if (parts.length !== 2 || !PLAYER.test(a)) return BAD;
        return this.totals.delete(a) ? "OK" : UNKNOWN;
      }
      case "COUNT":
        return parts.length === 1 ? `COUNT ${this.totals.size}` : BAD;
      default:
        return BAD;
    }
  }
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("leaderboard: takes no arguments\n");
    process.exit(2);
  }
  const board = new Leaderboard();
  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    process.stdout.write(board.handle(line) + "\n");
  };

  let pending = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let nl: number;
    while ((nl = pending.indexOf("\n")) >= 0) {
      respond(pending.slice(0, nl));
      pending = pending.slice(nl + 1);
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") respond(pending);
  });
}

main();
