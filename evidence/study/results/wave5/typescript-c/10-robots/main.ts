import { readFileSync } from "node:fs";

const TICKS = /^[0-9]{1,5}$/;
const PROGRAM_LINE = /^([A-Z]):([NESW.]{0,100})$/;
const MAX_SIZE = 50;

class InvalidInput extends Error {}

interface Robot {
  letter: string;
  x: number;
  y: number;
  program: string;
  moves: number;
  bumps: number;
  coins: number;
}

interface World {
  /** Terrain only: '#', '*' or '.'. Robots are tracked separately. */
  cells: string[][];
  robots: Robot[];
}

const DELTAS: Record<string, [number, number]> = { N: [0, -1], S: [0, 1], E: [1, 0], W: [-1, 0] };

function readLines(): string[] {
  const text = readFileSync(0, "utf8");
  if (text === "") return [];
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  return lines.map((l) => (l.endsWith("\r") ? l.slice(0, -1) : l));
}

function parseWorld(lines: string[]): World {
  const blank = lines.indexOf("");
  const gridLines = blank < 0 ? lines : lines.slice(0, blank);
  const programLines = blank < 0 ? [] : lines.slice(blank + 1);

  if (gridLines.length === 0 || gridLines.length > MAX_SIZE) throw new InvalidInput("bad number of grid rows");
  const width = gridLines[0].length;
  if (width < 1 || width > MAX_SIZE) throw new InvalidInput("bad grid width");

  const robots = new Map<string, Robot>();
  const cells = gridLines.map((row, y) => {
    if (row.length !== width) throw new InvalidInput(`row ${y + 1} has a different length`);
    return Array.from(row, (ch, x) => {
      if (ch === "." || ch === "#" || ch === "*") return ch;
      if (ch >= "A" && ch <= "Z") {
        if (robots.has(ch)) throw new InvalidInput(`robot ${ch} appears twice`);
        robots.set(ch, { letter: ch, x, y, program: "", moves: 0, bumps: 0, coins: 0 });
        return ".";
      }
      throw new InvalidInput(`unknown grid character '${ch}'`);
    });
  });

  const programmed = new Set<string>();
  for (const line of programLines) {
    const m = PROGRAM_LINE.exec(line);
    if (m === null) throw new InvalidInput(`malformed program line '${line}'`);
    const robot = robots.get(m[1]);
    if (robot === undefined) throw new InvalidInput(`no robot ${m[1]} on the grid`);
    if (programmed.has(m[1])) throw new InvalidInput(`two programs for robot ${m[1]}`);
    programmed.add(m[1]);
    robot.program = m[2];
  }

  return { cells, robots: [...robots.values()].sort((a, b) => (a.letter < b.letter ? -1 : 1)) };
}

function simulate(world: World, ticks: number): void {
  const { cells, robots } = world;
  const height = cells.length;
  const width = cells[0].length;
  const occupied = cells.map((row) => row.map(() => false));
  for (const r of robots) occupied[r.y][r.x] = true;

  for (let t = 0; t < ticks; t++) {
    for (const r of robots) {
      if (r.program === "") continue;
      const move = r.program[t % r.program.length];
      if (move === ".") continue;
      const [dx, dy] = DELTAS[move];
      const nx = r.x + dx;
      const ny = r.y + dy;
      const blocked = nx < 0 || ny < 0 || nx >= width || ny >= height || cells[ny][nx] === "#" || occupied[ny][nx];
      if (blocked) {
        r.bumps++;
        continue;
      }
      occupied[r.y][r.x] = false;
      occupied[ny][nx] = true;
      r.x = nx;
      r.y = ny;
      r.moves++;
      if (cells[ny][nx] === "*") {
        cells[ny][nx] = ".";
        r.coins++;
      }
    }
  }
}

function render(world: World): string {
  const rows = world.cells.map((row) => [...row]);
  for (const r of world.robots) rows[r.y][r.x] = r.letter;
  const stats = world.robots.map((r) => `${r.letter} ${r.x} ${r.y} moves=${r.moves} bumps=${r.bumps} coins=${r.coins}`);
  return [...rows.map((row) => row.join("")), ...stats].join("\n") + "\n";
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1 || !TICKS.test(args[0])) {
    process.stderr.write("robots: usage: robots TICKS\n");
    process.exit(2);
  }
  let world: World;
  try {
    world = parseWorld(readLines());
  } catch (e) {
    if (!(e instanceof InvalidInput)) throw e;
    process.stderr.write(`robots: ${e.message}\n`);
    process.exit(1);
  }
  simulate(world, Number(args[0]));
  process.stdout.write(render(world));
}

main();
