import { readFileSync } from 'node:fs';
let max = 1000, quiet = false;
const args = process.argv.slice(2);
function usage(): never { console.error('Invalid arguments'); process.exit(2); }
for (let i = 0; i < args.length; i++) {
  if (args[i] === '-q') quiet = true;
  else if (args[i] === '-n') {
    const value = args[++i];
    if (!value || !/^[1-9][0-9]{0,5}$/.test(value)) usage();
    max = Number(value);
  } else usage();
}
const lines = readFileSync(0, 'utf8').split('\n');
if (lines.at(-1) === '') lines.pop();
const decks = lines.map(line => line.replace(/\r$/, ''));
if (decks.length !== 2 || decks.some(deck => !/^[2-9TJQKA]{1,52}$/.test(deck))) { console.error('Invalid input'); process.exit(1); }
const a = [...decks[0]], b = [...decks[1]];
const ranks = '23456789TJQKA';
const output: string[] = [];
let result = `stopped at round ${max}`;
for (let round = 1; round <= max; round++) {
  const pile: string[] = [], facesA: string[] = [], facesB: string[] = [];
  let cardA = a.shift()!, cardB = b.shift()!, incomplete = false;
  pile.push(cardA, cardB); facesA.push(cardA); facesB.push(cardB);
  while (cardA === cardB) {
    if (a.length < 4 || b.length < 4) { incomplete = true; break; }
    for (let i = 0; i < 4; i++) { cardA = a.shift()!; pile.push(cardA); }
    for (let i = 0; i < 4; i++) { cardB = b.shift()!; pile.push(cardB); }
    facesA.push(cardA); facesB.push(cardB);
  }
  const winner = incomplete ? '-' : ranks.indexOf(cardA) > ranks.indexOf(cardB) ? 'A' : 'B';
  if (winner === 'A') a.push(...pile);
  if (winner === 'B') b.push(...pile);
  if (!quiet) output.push(`${round} ${facesA.join('/')} ${facesB.join('/')} ${winner} ${a.length} ${b.length}`);
  if (incomplete || !a.length || !b.length) {
    const finalWinner = incomplete ? (a.length === b.length ? '-' : a.length > b.length ? 'A' : 'B') : a.length ? 'A' : 'B';
    result = finalWinner === '-' ? `draw in round ${round}` : `${finalWinner} wins in round ${round}`;
    break;
  }
}
output.push(result);
console.log(output.join('\n'));
