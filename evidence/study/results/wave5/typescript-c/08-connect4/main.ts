const COLS = 7;
const ROWS = 6;

type Player = "X" | "O";
type Outcome = { kind: "win"; player: Player } | { kind: "draw" } | null;

class Game {
  /** columns[c] holds the discs of column c from the bottom up. */
  private columns: Player[][] = [];
  private moves: number[] = [];
  private outcome: Outcome = null;

  constructor() {
    this.reset();
  }

  reset(): void {
    this.columns = Array.from({ length: COLS }, () => []);
    this.moves = [];
    this.outcome = null;
  }

  private get toMove(): Player {
    return this.moves.length % 2 === 0 ? "X" : "O";
  }

  private cell(col: number, row: number): Player | null {
    if (col < 0 || col >= COLS || row < 0) return null;
    return this.columns[col][row] ?? null;
  }

  private wins(col: number, row: number, player: Player): boolean {
    const directions = [[1, 0], [0, 1], [1, 1], [1, -1]];
    return directions.some(([dc, dr]) => {
      let count = 1;
      for (const sign of [1, -1]) {
        let c = col + sign * dc;
        let r = row + sign * dr;
        while (this.cell(c, r) === player) {
          count++;
          c += sign * dc;
          r += sign * dr;
        }
      }
      return count >= 4;
    });
  }

  drop(col: number): string {
    if (this.outcome !== null) return "ERR game over";
    if (this.columns[col].length >= ROWS) return "ERR column full";
    const player = this.toMove;
    const row = this.columns[col].length;
    this.columns[col].push(player);
    this.moves.push(col);

    let suffix = "";
    if (this.wins(col, row, player)) {
      this.outcome = { kind: "win", player };
      suffix = " WIN";
    } else if (this.moves.length === COLS * ROWS) {
      this.outcome = { kind: "draw" };
      suffix = " DRAW";
    }
    return `PLAYED ${player} ${row + 1}${suffix}`;
  }

  undo(): string {
    const col = this.moves.pop();
    if (col === undefined) return "ERR nothing to undo";
    this.columns[col].pop();
    this.outcome = null;
    return `UNDONE ${col + 1}`;
  }

  board(): string {
    const rows: string[] = [];
    for (let r = ROWS - 1; r >= 0; r--) {
      let line = "";
      for (let c = 0; c < COLS; c++) line += this.cell(c, r) ?? ".";
      rows.push(line);
    }
    return rows.join("/");
  }

  status(): string {
    if (this.outcome === null) return `TURN ${this.toMove}`;
    return this.outcome.kind === "win" ? `WIN ${this.outcome.player}` : "DRAW";
  }
}

function handle(game: Game, line: string): string {
  const m = /^DROP ([1-7])$/.exec(line);
  if (m !== null) return game.drop(Number(m[1]) - 1);
  switch (line) {
    case "UNDO":
      return game.undo();
    case "BOARD":
      return game.board();
    case "STATUS":
      return game.status();
    case "NEW":
      game.reset();
      return "OK";
    default:
      return "ERR bad command";
  }
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("connect4: takes no arguments\n");
    process.exit(2);
  }
  const game = new Game();
  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    process.stdout.write(handle(game, line) + "\n");
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
