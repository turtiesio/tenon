import { createInterface } from 'node:readline';
if (process.argv.length !== 2) { console.error('No arguments allowed'); process.exit(2); }
const cellPattern = '[A-Z][1-9][0-9]?';
const cellRegex = new RegExp('^' + cellPattern + '$');
type Part = { sign: bigint; value: bigint | string };
type Contents = { text: string; parts: Part[]; refs: Set<string> };
const sheet = new Map<string, Contents>();
const cache = new Map<string, bigint | null>();
function parse(text: string): Contents | undefined {
  const parts: Part[] = [], refs = new Set<string>();
  if (/^-?[0-9]{1,9}$/.test(text)) return { text, parts: [{ sign: 1n, value: BigInt(text) }], refs };
  if (!text.startsWith('=')) return;
  let index = 1, sign = 1n;
  if (text[index] === '-') { sign = -1n; index++; }
  const term = new RegExp('^(?:SUM\\((' + cellPattern + '):(' + cellPattern + ')\\)|(' + cellPattern + ')|([0-9]{1,9}))');
  while (index < text.length) {
    const match = text.slice(index).match(term);
    if (!match) return;
    index += match[0].length;
    if (match[1]) {
      const c1 = match[1].charCodeAt(0), c2 = match[2].charCodeAt(0), r1 = Number(match[1].slice(1)), r2 = Number(match[2].slice(1));
      for (let c = Math.min(c1, c2); c <= Math.max(c1, c2); c++) for (let r = Math.min(r1, r2); r <= Math.max(r1, r2); r++) {
        const name = String.fromCharCode(c) + r; refs.add(name); parts.push({ sign, value: name });
      }
    } else if (match[3]) { refs.add(match[3]); parts.push({ sign, value: match[3] }); }
    else parts.push({ sign, value: BigInt(match[4]) });
    if (index === text.length) return { text, parts, refs };
    if (text[index] !== '+' && text[index] !== '-') return;
    sign = text[index++] === '+' ? 1n : -1n;
  }
}
function cycles(cell: string, contents: Contents): boolean {
  const stack = [...contents.refs], visited = new Set<string>();
  while (stack.length) {
    const name = stack.pop()!;
    if (name === cell) return true;
    if (visited.has(name)) continue;
    visited.add(name); const stored = sheet.get(name); if (stored) stack.push(...stored.refs);
  }
  return false;
}
function evaluate(cell: string): bigint | null {
  const stack: [string, boolean][] = [[cell, false]];
  while (stack.length) {
    const [name, ready] = stack.pop()!;
    if (cache.has(name)) continue;
    const contents = sheet.get(name);
    if (!contents) { cache.set(name, 0n); continue; }
    if (!ready) {
      stack.push([name, true]);
      for (const ref of contents.refs) if (!cache.has(ref)) stack.push([ref, false]);
      continue;
    }
    let total = 0n, overflow = false;
    for (const part of contents.parts) {
      const value = typeof part.value === 'bigint' ? part.value : cache.get(part.value)!;
      if (value === null) { overflow = true; break; }
      total += part.sign * value;
    }
    cache.set(name, overflow || total > 1000000000000n || total < -1000000000000n ? null : total);
  }
  return cache.get(cell)!;
}
function command(line: string): string {
  const tokens = line.split(' '), [op, cell, text] = tokens;
  if (!cell || !cellRegex.test(cell)) return 'ERR bad command';
  if (op === 'SET' && tokens.length === 3) {
    const contents = parse(text); if (!contents) return 'ERR bad command';
    if (cycles(cell, contents)) return 'ERR cycle';
    sheet.set(cell, contents); cache.clear(); return 'OK';
  }
  if (tokens.length !== 2) return 'ERR bad command';
  if (op === 'CLEAR') { sheet.delete(cell); cache.clear(); return 'OK'; }
  if (op === 'SHOW') return sheet.get(cell)?.text ?? 'EMPTY';
  if (op === 'GET') { const value = evaluate(cell); return value === null ? 'ERR overflow' : String(value); }
  return 'ERR bad command';
}
createInterface({ input: process.stdin, crlfDelay: Infinity }).on('line', line => process.stdout.write(command(line) + '\n'));
