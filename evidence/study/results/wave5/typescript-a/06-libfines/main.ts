import { readFileSync } from 'node:fs';
function fail(code: number): never { console.error('Invalid file or arguments'); process.exit(code); }
const args = process.argv.slice(2), integer = /^[0-9]{1,6}$/, id = /^[A-Za-z0-9-]{1,12}$/;
if (args.length !== 3 || !integer.test(args[2])) fail(2);
function records(path: string): string[][] {
  let text: string;
  try { text = readFileSync(path, 'utf8'); } catch { fail(1); }
  return text.split('\n').map(line => line.replace(/\r$/, '')).filter(line => line !== '' && !line.startsWith('#')).map(line => line.split('|'));
}
type Book = {title: string; rate: number; cap: number};
const books = new Map<string, Book>();
for (const fields of records(args[0])) {
  const [key, title, rate, cap] = fields;
  if (fields.length !== 4 || !id.test(key) || !title || !integer.test(rate) || !integer.test(cap) || books.has(key)) fail(1);
  books.set(key, {title, rate: Number(rate), cap: Number(cap)});
}
type Member = {name: string; loans: number; late: number; fine: number; details: string[]};
const members = new Map<string, Member>();
const money = (cents: number) => `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, '0')}`;
let skipped = 0, total = 0;
for (const fields of records(args[1])) {
  const [name, key, out, due, returned] = fields;
  if (fields.length !== 5 || !/^[a-z][a-z0-9]{0,11}$/.test(name) || !id.test(key) || !integer.test(out) || !integer.test(due) || Number(due) < Number(out) || (returned !== '-' && (!integer.test(returned) || Number(returned) < Number(out)))) fail(1);
  const book = books.get(key);
  if (!book) { skipped++; continue; }
  let member = members.get(name);
  if (!member) { member = {name, loans: 0, late: 0, fine: 0, details: []}; members.set(name, member); }
  const days = Math.max(0, Number(returned === '-' ? args[2] : returned) - Number(due));
  const fine = Math.min(days * book.rate, book.cap);
  member.loans++; member.fine += fine; total += fine;
  if (days > 0) { member.late++; member.details.push(`  ${key} ${book.title} days=${days} fine=${money(fine)}`); }
}
const output: string[] = [];
for (const member of [...members.values()].sort((a,b) => b.fine - a.fine || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))) {
  output.push(`${member.name} loans=${member.loans} late=${member.late} fine=${money(member.fine)}`, ...member.details);
}
output.push(`total=${money(total)} skipped=${skipped}`);
process.stdout.write(output.join('\n') + '\n');
