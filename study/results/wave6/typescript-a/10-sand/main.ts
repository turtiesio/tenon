import { readFileSync } from 'node:fs';
const args = process.argv.slice(2);
if (args.length !== 1 || !/^[0-9]{1,4}$/.test(args[0])) { console.error('Usage: sand TICKS'); process.exit(2); }
const input = readFileSync(0, 'utf8');
const rows = input === '' ? [] : input.split('\n');
if (input.endsWith('\n')) rows.pop();
const grid = rows.map(row => [...row.replace(/\r$/, '')]);
const height = grid.length, width = grid[0]?.length ?? 0;
if (height < 1 || height > 30 || width < 1 || width > 30 || grid.some(row => row.length !== width || row.some(cell => !'.#oS'.includes(cell)))) {
  console.error('Invalid grid'); process.exit(1);
}
const sources: { x: number; y: number }[] = [];
for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) if (grid[y][x] === 'S') sources.push({ x, y });
let ticks = 0, lost = 0, stable = false;
for (let tick = 0; tick < Number(args[0]); tick++) {
  let changed = false;
  for (let y = height - 1; y >= 0; y--) {
    for (let x = 0; x < width; x++) {
      if (grid[y][x] !== 'o') continue;
      if (y === height - 1) { grid[y][x] = '.'; lost++; changed = true; continue; }
      for (const targetX of [x, x - 1, x + 1]) {
        if (targetX >= 0 && targetX < width && grid[y + 1][targetX] === '.') {
          grid[y][x] = '.'; grid[y + 1][targetX] = 'o'; changed = true; break;
        }
      }
    }
  }
  for (const { x, y } of sources) {
    if (y < height - 1 && grid[y + 1][x] === '.') { grid[y + 1][x] = 'o'; changed = true; }
  }
  ticks++;
  if (!changed) { stable = true; break; }
}
const grains = grid.reduce((sum, row) => sum + row.filter(cell => cell === 'o').length, 0);
console.log(grid.map(row => row.join('')).join('\n'));
console.log(`ticks=${ticks} grains=${grains} lost=${lost} stable=${stable ? 'yes' : 'no'}`);
