import { readFileSync } from "node:fs";

type Grid = string[][];

const MAX_SIZE = 30;
const EMPTY = ".";
const GRAIN = "o";
const SOURCE = "S";

function readStdin(): string {
  try {
    return readFileSync(0, "utf8");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "EOF") return "";
    throw e;
  }
}

/** Parses the grid; null if it is invalid. */
function parseGrid(text: string): Grid | null {
  if (text === "") return null;
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  const rows = lines.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line));
  if (rows.length < 1 || rows.length > MAX_SIZE) return null;
  const width = rows[0].length;
  if (width < 1 || width > MAX_SIZE) return null;
  for (const row of rows) {
    if (row.length !== width || !/^[.#oS]+$/.test(row)) return null;
  }
  return rows.map((row) => [...row]);
}

interface TickResult {
  changed: boolean;
  lost: number;
}

function tick(grid: Grid): TickResult {
  const height = grid.length;
  const width = grid[0].length;
  let changed = false;
  let lost = 0;

  for (let y = height - 1; y >= 0; y--) {
    for (let x = 0; x < width; x++) {
      if (grid[y][x] !== GRAIN) continue;
      if (y === height - 1) {
        grid[y][x] = EMPTY;
        lost++;
        changed = true;
        continue;
      }
      for (const nx of [x, x - 1, x + 1]) {
        if (nx >= 0 && nx < width && grid[y + 1][nx] === EMPTY) {
          grid[y][x] = EMPTY;
          grid[y + 1][nx] = GRAIN;
          changed = true;
          break;
        }
      }
    }
  }

  for (let y = 0; y < height - 1; y++) {
    for (let x = 0; x < width; x++) {
      if (grid[y][x] === SOURCE && grid[y + 1][x] === EMPTY) {
        grid[y + 1][x] = GRAIN;
        changed = true;
      }
    }
  }
  return { changed, lost };
}

function main(): number {
  const args = process.argv.slice(2);
  if (args.length !== 1 || !/^[0-9]{1,4}$/.test(args[0])) {
    process.stderr.write("usage: sand TICKS\n");
    return 2;
  }
  const maxTicks = Number(args[0]);

  const grid = parseGrid(readStdin());
  if (!grid) {
    process.stderr.write("sand: invalid grid\n");
    return 1;
  }

  let ticks = 0;
  let lost = 0;
  let stable = false;
  while (ticks < maxTicks && !stable) {
    const result = tick(grid);
    ticks++;
    lost += result.lost;
    stable = !result.changed;
  }

  const grains = grid.reduce((n, row) => n + row.filter((c) => c === GRAIN).length, 0);
  const lines = grid.map((row) => row.join("") + "\n");
  lines.push(`ticks=${ticks} grains=${grains} lost=${lost} stable=${stable ? "yes" : "no"}\n`);
  process.stdout.write(lines.join(""));
  return 0;
}

process.exitCode = main();
