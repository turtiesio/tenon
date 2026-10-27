import { readFileSync } from "node:fs";

class InputError extends Error {}

type Robot = {
  letter: string;
  x: number;
  y: number;
  program: string;
  moves: number;
  bumps: number;
  coins: number;
};

type World = { grid: string[][]; robots: Robot[] };

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
  const rows = blank === -1 ? lines : lines.slice(0, blank);
  const programLines = blank === -1 ? [] : lines.slice(blank + 1);

  if (rows.length === 0) throw new InputError("missing grid");
  if (rows.length > 50) throw new InputError("too many rows");
  const width = rows[0].length;
  if (width > 50) throw new InputError("rows too long");

  // The grid stores only terrain; robots are tracked separately.
  const grid: string[][] = [];
  const robots = new Map<string, Robot>();
  rows.forEach((row, y) => {
    if (row.length !== width) throw new InputError(`row ${y + 1} has a different length`);
    grid.push(
      [...row].map((ch, x) => {
        if (ch === "." || ch === "#" || ch === "*") return ch;
        if (/^[A-Z]$/.test(ch)) {
          if (robots.has(ch)) throw new InputError(`robot ${ch} appears twice`);
          robots.set(ch, { letter: ch, x, y, program: "", moves: 0, bumps: 0, coins: 0 });
          return ".";
        }
        throw new InputError(`unknown grid character ${ch}`);
      }),
    );
  });

  const programmed = new Set<string>();
  for (const line of programLines) {
    const m = /^([A-Z]):([NESW.]{0,100})$/.exec(line);
    if (!m) throw new InputError(`malformed program line: ${line}`);
    const robot = robots.get(m[1]);
    if (!robot) throw new InputError(`no robot ${m[1]} on the grid`);
    if (programmed.has(m[1])) throw new InputError(`two programs for robot ${m[1]}`);
    programmed.add(m[1]);
    robot.program = m[2];
  }

  const sorted = [...robots.values()].sort((a, b) => (a.letter < b.letter ? -1 : 1));
  return { grid, robots: sorted };
}

function simulate(world: World, ticks: number): void {
  const { grid, robots } = world;
  const height = grid.length;
  const width = grid[0].length;
  const occupied = (x: number, y: number) => robots.some((r) => r.x === x && r.y === y);

  for (let t = 0; t < ticks; t++) {
    for (const robot of robots) {
      if (robot.program === "") continue;
      const instr = robot.program[t % robot.program.length];
      if (instr === ".") continue;
      const [dx, dy] = DELTAS[instr];
      const nx = robot.x + dx;
      const ny = robot.y + dy;
      if (nx < 0 || ny < 0 || nx >= width || ny >= height || grid[ny][nx] === "#" || occupied(nx, ny)) {
        robot.bumps++;
        continue;
      }
      robot.x = nx;
      robot.y = ny;
      robot.moves++;
      if (grid[ny][nx] === "*") {
        robot.coins++;
        grid[ny][nx] = ".";
      }
    }
  }
}

function main(argv: string[]): void {
  if (argv.length !== 1 || !/^[0-9]{1,5}$/.test(argv[0])) {
    process.stderr.write("usage: robots TICKS\n");
    process.exit(2);
  }
  let world: World;
  try {
    world = parseWorld(readLines());
  } catch (e) {
    if (e instanceof InputError) {
      process.stderr.write(`robots: ${e.message}\n`);
      process.exit(1);
    }
    throw e;
  }

  simulate(world, Number(argv[0]));

  const view = world.grid.map((row) => [...row]);
  for (const r of world.robots) view[r.y][r.x] = r.letter;
  const out = view.map((row) => row.join(""));
  for (const r of world.robots) {
    out.push(`${r.letter} ${r.x} ${r.y} moves=${r.moves} bumps=${r.bumps} coins=${r.coins}`);
  }
  process.stdout.write(out.join("\n") + "\n");
}

main(process.argv.slice(2));
