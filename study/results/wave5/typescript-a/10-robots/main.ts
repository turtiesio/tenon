import { readFileSync } from 'node:fs';
function fail(code: number): never { console.error('Invalid world or arguments'); process.exit(code); }
const args = process.argv.slice(2);
if (args.length !== 1 || !/^[0-9]{1,5}$/.test(args[0])) fail(2);
const input = readFileSync(0, 'utf8');
const lines = input === '' ? [] : input.split('\n');
if (input.endsWith('\n')) lines.pop();
for (let i = 0; i < lines.length; i++) lines[i] = lines[i].replace(/\r$/, '');
const separator = lines.indexOf('');
const rows = separator === -1 ? lines : lines.slice(0, separator);
const programs = separator === -1 ? [] : lines.slice(separator + 1);
if (rows.length < 1 || rows.length > 50 || rows[0].length < 1 || rows[0].length > 50 || rows.some(row => row.length !== rows[0].length || !/^[.#*A-Z]+$/.test(row))) fail(1);
type Robot = {letter: string; x: number; y: number; program: string; moves: number; bumps: number; coins: number};
const robots = new Map<string, Robot>();
const grid = rows.map(row => row.split(''));
for (let y = 0; y < grid.length; y++) for (let x = 0; x < grid[y].length; x++) {
  const letter = grid[y][x];
  if (/^[A-Z]$/.test(letter)) {
    if (robots.has(letter)) fail(1);
    robots.set(letter, {letter, x, y, program: '', moves: 0, bumps: 0, coins: 0});
  }
}
const assigned = new Set<string>();
for (const line of programs) {
  const match = /^([A-Z]):([NESW.]{0,100})$/.exec(line);
  if (!match || !robots.has(match[1]) || assigned.has(match[1])) fail(1);
  assigned.add(match[1]); robots.get(match[1])!.program = match[2];
}
const ordered = [...robots.values()].sort((a, b) => a.letter < b.letter ? -1 : 1);
const directions: Record<string, [number, number]> = {N: [0,-1], E: [1,0], S: [0,1], W: [-1,0]};
for (let tick = 0; tick < Number(args[0]); tick++) for (const robot of ordered) {
  if (!robot.program.length) continue;
  const move = robot.program[tick % robot.program.length];
  if (move === '.') continue;
  const [dx, dy] = directions[move], x = robot.x + dx, y = robot.y + dy;
  if (y < 0 || y >= grid.length || x < 0 || x >= grid[0].length || grid[y][x] === '#' || /^[A-Z]$/.test(grid[y][x])) { robot.bumps++; continue; }
  if (grid[y][x] === '*') robot.coins++;
  grid[robot.y][robot.x] = '.'; grid[y][x] = robot.letter;
  robot.x = x; robot.y = y; robot.moves++;
}
const output = grid.map(row => row.join(''));
for (const robot of ordered) output.push(`${robot.letter} ${robot.x} ${robot.y} moves=${robot.moves} bumps=${robot.bumps} coins=${robot.coins}`);
process.stdout.write(output.join('\n') + '\n');
