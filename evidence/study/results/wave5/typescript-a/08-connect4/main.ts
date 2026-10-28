if (process.argv.length !== 2) { console.error('No arguments expected'); process.exit(2); }
let columns: string[][] = Array.from({length: 7}, () => []);
let history: number[] = [];
let outcome: string | undefined;
function respond(line: string): string {
  if (line === 'NEW') { columns = Array.from({length: 7}, () => []); history = []; outcome = undefined; return 'OK'; }
  if (line === 'BOARD') return Array.from({length: 6}, (_, i) => columns.map(column => column[5-i] ?? '.').join('')).join('/');
  if (line === 'STATUS') return outcome ?? `TURN ${history.length % 2 === 0 ? 'X' : 'O'}`;
  if (line === 'UNDO') {
    if (!history.length) return 'ERR nothing to undo';
    const column = history.pop()!; columns[column].pop(); outcome = undefined;
    return `UNDONE ${column + 1}`;
  }
  if (!/^DROP [1-7]$/.test(line)) return 'ERR bad command';
  if (outcome) return 'ERR game over';
  const c = Number(line[5]) - 1, r = columns[c].length;
  if (r === 6) return 'ERR column full';
  const player = history.length % 2 === 0 ? 'X' : 'O';
  columns[c].push(player); history.push(c);
  let win = false;
  for (const [dc, dr] of [[1,0], [0,1], [1,1], [1,-1]]) {
    let count = 1;
    for (const sign of [-1, 1]) {
      let x = c + sign * dc, y = r + sign * dr;
      while (x >= 0 && x < 7 && y >= 0 && y < 6 && columns[x][y] === player) { count++; x += sign * dc; y += sign * dr; }
    }
    if (count >= 4) win = true;
  }
  if (win) outcome = `WIN ${player}`;
  else if (history.length === 42) outcome = 'DRAW';
  return `PLAYED ${player} ${r + 1}${win ? ' WIN' : outcome === 'DRAW' ? ' DRAW' : ''}`;
}
process.stdin.setEncoding('utf8');
let pending = '';
for await (const chunk of process.stdin) {
  pending += chunk;
  let end: number;
  while ((end = pending.indexOf('\n')) !== -1) {
    process.stdout.write(respond(pending.slice(0, end).replace(/\r$/, '')) + '\n');
    pending = pending.slice(end + 1);
  }
}
if (pending !== '') process.stdout.write(respond(pending.replace(/\r$/, '')) + '\n');
