import { readFileSync } from "node:fs";

class InputError extends Error {}

const NAME_RE = /^[a-z][a-z0-9_]{0,15}$/;
const AMOUNT_RE = /^[0-9]{1,7}\.[0-9]{2}$/;

function parseName(token: string, lineNo: number): string {
  if (!NAME_RE.test(token)) throw new InputError(`line ${lineNo}: bad name ${token}`);
  return token;
}

function parseAmount(token: string, lineNo: number): number {
  if (!AMOUNT_RE.test(token)) throw new InputError(`line ${lineNo}: bad amount ${token}`);
  const cents = Number(token.replace(".", ""));
  if (cents === 0) throw new InputError(`line ${lineNo}: zero amount`);
  return cents;
}

function formatMoney(cents: number): string {
  const abs = Math.abs(cents);
  return `${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

function formatBalance(cents: number): string {
  const sign = cents > 0 ? "+" : cents < 0 ? "-" : "";
  return sign + formatMoney(cents);
}

function readLines(): string[] {
  const text = readFileSync(0, "utf8");
  if (text === "") return [];
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  return lines.map((l) => (l.endsWith("\r") ? l.slice(0, -1) : l));
}

function computeBalances(lines: string[]): Map<string, number> {
  const balances = new Map<string, number>();
  const adjust = (name: string, delta: number) => balances.set(name, (balances.get(name) ?? 0) + delta);

  lines.forEach((line, idx) => {
    const lineNo = idx + 1;
    const tokens = line.split(/[ \t]+/).filter((t) => t !== "");
    if (tokens.length === 0 || tokens[0].startsWith("#")) return;

    if (tokens[0] === "expense") {
      if (tokens.length < 4) throw new InputError(`line ${lineNo}: expense needs a payer, amount and participants`);
      const payer = parseName(tokens[1], lineNo);
      const amount = parseAmount(tokens[2], lineNo);
      const participants = tokens.slice(3).map((t) => parseName(t, lineNo));
      if (new Set(participants).size !== participants.length) {
        throw new InputError(`line ${lineNo}: participant listed twice`);
      }
      const n = participants.length;
      const q = Math.floor(amount / n);
      const r = amount % n;
      adjust(payer, amount);
      participants.forEach((p, i) => adjust(p, -(i < r ? q + 1 : q)));
    } else if (tokens[0] === "transfer") {
      if (tokens.length !== 4) throw new InputError(`line ${lineNo}: transfer needs from, to and amount`);
      const from = parseName(tokens[1], lineNo);
      const to = parseName(tokens[2], lineNo);
      const amount = parseAmount(tokens[3], lineNo);
      if (from === to) throw new InputError(`line ${lineNo}: transfer to self`);
      adjust(from, amount);
      adjust(to, -amount);
    } else {
      throw new InputError(`line ${lineNo}: unknown record ${tokens[0]}`);
    }
  });
  return balances;
}

function settle(balances: Map<string, number>): string[] {
  const work = new Map(balances);
  const payments: string[] = [];
  for (;;) {
    let debtor: string | null = null;
    let creditor: string | null = null;
    for (const [name, bal] of work) {
      if (bal < 0) {
        const best = debtor === null ? 0 : work.get(debtor)!;
        if (debtor === null || bal < best || (bal === best && name < debtor)) debtor = name;
      } else if (bal > 0) {
        const best = creditor === null ? 0 : work.get(creditor)!;
        if (creditor === null || bal > best || (bal === best && name < creditor)) creditor = name;
      }
    }
    if (debtor === null || creditor === null) break;
    const x = Math.min(-work.get(debtor)!, work.get(creditor)!);
    work.set(debtor, work.get(debtor)! + x);
    work.set(creditor, work.get(creditor)! - x);
    payments.push(`${debtor} pays ${creditor} ${formatMoney(x)}`);
  }
  return payments;
}

function main(argv: string[]): void {
  if (argv.length > 0) {
    process.stderr.write("usage: splitbill < records\n");
    process.exit(2);
  }
  let balances: Map<string, number>;
  try {
    balances = computeBalances(readLines());
  } catch (e) {
    if (e instanceof InputError) {
      process.stderr.write(`splitbill: ${e.message}\n`);
      process.exit(1);
    }
    throw e;
  }

  const names = [...balances.keys()].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  const out = names.map((n) => `${n} ${formatBalance(balances.get(n)!)}`);
  out.push("--", ...settle(balances));
  process.stdout.write(out.join("\n") + "\n");
}

main(process.argv.slice(2));
