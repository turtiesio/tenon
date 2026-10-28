import * as fs from "node:fs";

const EMPTY = ".";
const GRAIN = "o";
const SOURCE = "S";
const MAX_SIZE = 30;

class GridError extends Error {}

function parseGrid(text: string): string[][] {
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  const rows = lines.map((l) => (l.endsWith("\r") ? l.slice(0, -1) : l));
  if (rows.length === 0) throw new GridError("the grid has no rows");
  if (rows.length > MAX_SIZE) throw new GridError(`more than ${MAX_SIZE} rows`);
  const width = rows[0].length;
  if (width === 0) throw new GridError("empty row");
  if (width > MAX_SIZE) throw new GridError(`more than ${MAX_SIZE} columns`);
  return rows.map((row, y) => {
    if (row.length !== width) throw new GridError(`row ${y + 1} has a different length`);
    if (!/^[.#oS]*$/.test(row)) throw new GridError(`row ${y + 1} has an invalid character`);
    return [...row];
  });
}

/** Runs one tick in place; returns whether anything changed and how many grains fell out. */
function tick(grid: string[][]): { changed: boolean; lost: number } {
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
  let grid: string[][];
  try {
    grid = parseGrid(fs.readFileSync(0, "utf8"));
  } catch (e) {
    if (!(e instanceof GridError)) throw e;
    process.stderr.write(`sand: invalid grid: ${e.message}\n`);
    return 1;
  }

  let ticks = 0;
  let lost = 0;
  let stable = false;
  while (ticks < maxTicks) {
    ticks++;
    const result = tick(grid);
    lost += result.lost;
    if (!result.changed) {
      stable = true;
      break;
    }
  }

  const grains = grid.reduce((n, row) => n + row.filter((c) => c === GRAIN).length, 0);
  const out = grid.map((row) => row.join("") + "\n").join("") +
    `ticks=${ticks} grains=${grains} lost=${lost} stable=${stable ? "yes" : "no"}\n`;
  process.stdout.write(out);
  return 0;
}

process.exitCode = main();
