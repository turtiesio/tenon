import fs from 'node:fs';
if (process.argv.length > 2) { console.error('No arguments expected'); process.exit(2); }
const lines = fs.readFileSync(0, 'utf8').split('\n').map(s => s.replace(/\r$/, '')).filter(s => !/^ *$/.test(s) && !s.startsWith('#'));
const header = lines.shift();
function badHeader(): never { console.error('Invalid candidates line'); process.exit(1); }
if (header === undefined || !/^candidates:( [A-Za-z][A-Za-z0-9_]{0,19}){1,20}$/.test(header)) badHeader();
const names = header.slice(12).split(' ');
if (new Set(names).size !== names.length) badHeader();
const indices = new Map(names.map((name, i) => [name, i]));
const ballots: number[][] = [];
let invalid = 0;
for (const line of lines) {
  const items = line.split('>');
  if (items.some(name => !indices.has(name)) || new Set(items).size !== items.length) { invalid++; continue; }
  ballots.push(items.map(name => indices.get(name)!));
}
console.log(`ballots=${ballots.length} invalid=${invalid}`);
const continuing = new Set(names.map((_, i) => i));
for (let round = 1; ; round++) {
  const votes = names.map(() => 0);
  let exhausted = 0;
  for (const ballot of ballots) {
    const choice = ballot.find(i => continuing.has(i));
    if (choice === undefined) exhausted++; else votes[choice]++;
  }
  const candidates = [...continuing];
  console.log(`round ${round}: ${candidates.map(i => `${names[i]}=${votes[i]}`).join(' ')} exhausted=${exhausted}`);
  const winner = candidates.find(i => 2 * votes[i] > ballots.length - exhausted);
  if (winner !== undefined || candidates.length === 1) { console.log(`winner: ${names[winner ?? candidates[0]]}`); break; }
  let eliminated = candidates[0];
  for (const i of candidates) if (votes[i] <= votes[eliminated]) eliminated = i;
  continuing.delete(eliminated);
  console.log(`eliminated: ${names[eliminated]}`);
}
