import { readFileSync } from 'node:fs';
function fail(code: number): never { console.error('Invalid input or arguments'); process.exit(code); }
if (process.argv.length > 2) fail(2);
const balances = new Map<string, number>();
function add(name: string, amount: number) { balances.set(name, (balances.get(name) ?? 0) + amount); }
function money(value: string): number {
  if (!/^[0-9]{1,7}\.[0-9]{2}$/.test(value)) fail(1);
  const cents = Number(value.replace('.', ''));
  if (!cents) fail(1);
  return cents;
}
const validName = (name: string) => /^[a-z][a-z0-9_]{0,15}$/.test(name);
for (const line of readFileSync(0, 'utf8').split('\n')) {
  const tokens = line.replace(/\r$/, '').match(/[^ \t]+/g) ?? [];
  if (!tokens.length || tokens[0].startsWith('#')) continue;
  if (tokens[0] === 'expense') {
    if (tokens.length < 4) fail(1);
    const payer = tokens[1], participants = tokens.slice(3);
    if (!validName(payer) || !participants.every(validName) || new Set(participants).size !== participants.length) fail(1);
    const amount = money(tokens[2]);
    add(payer, amount);
    const share = Math.floor(amount / participants.length), remainder = amount % participants.length;
    participants.forEach((name, i) => add(name, -share - (i < remainder ? 1 : 0)));
  } else if (tokens[0] === 'transfer') {
    if (tokens.length !== 4 || !validName(tokens[1]) || !validName(tokens[2]) || tokens[1] === tokens[2]) fail(1);
    const amount = money(tokens[3]);
    add(tokens[1], amount); add(tokens[2], -amount);
  } else fail(1);
}
function format(amount: number): string { return `${Math.floor(Math.abs(amount) / 100)}.${String(Math.abs(amount) % 100).padStart(2, '0')}`; }
const names = [...balances.keys()].sort();
const lines = names.map(name => { const amount = balances.get(name)!; return `${name} ${amount > 0 ? '+' : amount < 0 ? '-' : ''}${format(amount)}`; });
lines.push('--');
while (true) {
  let debtor: string | undefined, creditor: string | undefined;
  for (const name of names) {
    const amount = balances.get(name)!;
    if (amount < 0 && (debtor === undefined || amount < balances.get(debtor)!)) debtor = name;
    if (amount > 0 && (creditor === undefined || amount > balances.get(creditor)!)) creditor = name;
  }
  if (debtor === undefined) break;
  const amount = Math.min(-balances.get(debtor)!, balances.get(creditor!)!);
  lines.push(`${debtor} pays ${creditor} ${format(amount)}`);
  add(debtor, amount); add(creditor!, -amount);
}
process.stdout.write(lines.join('\n') + '\n');
