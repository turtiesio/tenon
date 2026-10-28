import { readFileSync } from 'node:fs';
let days = 3;
const files: string[] = [], args = process.argv.slice(2);
function usage(): never { console.error('Invalid arguments'); process.exit(2); }
for (let i = 0; i < args.length; i++) {
  if (args[i] === '-d') {
    const value = args[++i];
    if (!value || !/^(0|[1-9][0-9]{0,2})$/.test(value) || Number(value) > 365) usage();
    days = Number(value);
  } else if (args[i].startsWith('-')) usage();
  else files.push(args[i]);
}
if (files.length !== 2) usage();
type Entry = { line: number; date: string; day: number; amount: number; text: string; matched: boolean };
function read(file: string): Entry[] {
  const lines = readFileSync(file, 'utf8').split('\n');
  if (lines.at(-1) === '') lines.pop();
  const entries: Entry[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].replace(/\r$/, '');
    if (!line) continue;
    const match = /^(\d{4}-\d{2}-\d{2}),(-?(?:0|[1-9][0-9]{0,8})\.[0-9]{2}),([\x20-\x7e]{1,40})$/.exec(line);
    if (!match || match[3].includes(',') || match[3].startsWith(' ') || match[3].endsWith(' ')) throw Error('Invalid line');
    const [year, month, date] = match[1].split('-').map(Number);
    const time = Date.UTC(year, month - 1, date), dt = new Date(time);
    if (year < 1970 || year > 2099 || dt.getUTCFullYear() !== year || dt.getUTCMonth() !== month - 1 || dt.getUTCDate() !== date) throw Error('Invalid date');
    const amount = Number(match[2].replace('.', ''));
    entries.push({ line: i + 1, date: match[1], day: time / 86400000, amount, text: match[3], matched: false });
  }
  return entries;
}
function money(cents: number): string { return `${cents < 0 ? '-' : ''}${Math.floor(Math.abs(cents) / 100)}.${String(Math.abs(cents) % 100).padStart(2, '0')}`; }
let bank: Entry[], ledger: Entry[];
try { bank = read(files[0]); ledger = read(files[1]); }
catch (error) { console.error(String(error)); process.exit(1); }
const byAmount = new Map<number, Entry[]>();
for (const entry of ledger) { const group = byAmount.get(entry.amount) ?? []; group.push(entry); byAmount.set(entry.amount, group); }
const output: string[] = [];
let matches = 0;
for (const entry of bank) {
  let best: Entry | undefined, distance = days + 1;
  for (const candidate of byAmount.get(entry.amount) ?? []) {
    const d = Math.abs(entry.day - candidate.day);
    if (!candidate.matched && d < distance) { best = candidate; distance = d; }
  }
  if (best) { entry.matched = best.matched = true; matches++; output.push(`M ${entry.line} ${best.line} ${money(entry.amount)} ${distance}`); }
}
const bankOnly = bank.filter(e => !e.matched), ledgerOnly = ledger.filter(e => !e.matched);
for (const [tag, entries] of [['B', bankOnly], ['L', ledgerOnly]] as const) {
  for (const e of entries) output.push(`${tag} ${e.line} ${e.date} ${money(e.amount)} ${e.text}`);
}
const diff = bankOnly.reduce((s, e) => s + e.amount, 0) - ledgerOnly.reduce((s, e) => s + e.amount, 0);
output.push(`matched=${matches} bank_only=${bankOnly.length} ledger_only=${ledgerOnly.length} diff=${money(diff)}`);
console.log(output.join('\n'));
