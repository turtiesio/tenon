const COLS = 7;
const ROWS = 6;

type Player = "X" | "O";
type Cell = Player | ".";
type Outcome = { kind: "running" } | { kind: "win"; player: Player } | { kind: "draw" };

class Game {
  // grid[col][row], both 0-based, row 0 at the bottom.
  private grid: Cell[][] = [];
  private moves: number[] = [];
  private outcome: Outcome = { kind: "running" };

  constructor() {
    this.reset();
  }

  reset(): void {
    this.grid = Array.from({ length: COLS }, () => Array<Cell>(ROWS).fill("."));
    this.moves = [];
    this.outcome = { kind: "running" };
  }

  private get turn(): Player {
    return this.moves.length % 2 === 0 ? "X" : "O";
  }

  private height(col: number): number {
    return this.grid[col].indexOf(".") === -1 ? ROWS : this.grid[col].indexOf(".");
  }

  private cell(col: number, row: number): Cell | null {
    return col >= 0 && col < COLS && row >= 0 && row < ROWS ? this.grid[col][row] : null;
  }

  private wins(col: number, row: number, player: Player): boolean {
    const directions = [[1, 0], [0, 1], [1, 1], [1, -1]];
    return directions.some(([dc, dr]) => {
      let run = 1;
      for (const sign of [1, -1]) {
        let c = col + sign * dc;
        let r = row + sign * dr;
        while (this.cell(c, r) === player) {
          run++;
          c += sign * dc;
          r += sign * dr;
        }
      }
      return run >= 4;
    });
  }

  drop(col: number): string {
    if (this.outcome.kind !== "running") return "ERR game over";
    const row = this.height(col);
    if (row === ROWS) return "ERR column full";
    const player = this.turn;
    this.grid[col][row] = player;
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
    this.grid[col][this.height(col) - 1] = ".";
    this.outcome = { kind: "running" };
    return `UNDONE ${col + 1}`;
  }

  status(): string {
    switch (this.outcome.kind) {
      case "running": return `TURN ${this.turn}`;
      case "win": return `WIN ${this.outcome.player}`;
      case "draw": return "DRAW";
    }
  }

  board(): string {
    const rows: string[] = [];
    for (let r = ROWS - 1; r >= 0; r--) {
      rows.push(this.grid.map((column) => column[r]).join(""));
    }
    return rows.join("/");
  }
}

function handle(game: Game, line: string): string {
  const drop = /^DROP ([1-7])$/.exec(line);
  if (drop) return game.drop(Number(drop[1]) - 1);
  switch (line) {
    case "UNDO": return game.undo();
    case "BOARD": return game.board();
    case "STATUS": return game.status();
    case "NEW":
      game.reset();
      return "OK";
    default:
      return "ERR bad command";
  }
}

function main(argv: string[]): void {
  if (argv.length > 0) {
    process.stderr.write("usage: connect4 < commands\n");
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
