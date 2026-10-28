import { readFileSync } from "node:fs";

const NAME = /^[a-z][a-z0-9_]{0,15}$/;
const AMOUNT = /^[0-9]{1,7}\.[0-9]{2}$/;

class InvalidInput extends Error {}

function parseName(tok: string, lineNo: number): string {
  if (!NAME.test(tok)) throw new InvalidInput(`line ${lineNo}: bad name '${tok}'`);
  return tok;
}

function parseAmount(tok: string, lineNo: number): number {
  if (!AMOUNT.test(tok)) throw new InvalidInput(`line ${lineNo}: bad amount '${tok}'`);
  const cents = Number(tok.replace(".", ""));
  if (cents === 0) throw new InvalidInput(`line ${lineNo}: zero amount`);
  return cents;
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
  const add = (name: string, delta: number) => balances.set(name, (balances.get(name) ?? 0) + delta);

  lines.forEach((line, idx) => {
    const lineNo = idx + 1;
    const tokens = line.split(/[ \t]+/).filter((t) => t !== "");
    if (tokens.length === 0 || tokens[0].startsWith("#")) return;

    if (tokens[0] === "expense") {
      if (tokens.length < 4) throw new InvalidInput(`line ${lineNo}: expense needs at least 4 tokens`);
      const payer = parseName(tokens[1], lineNo);
      const amount = parseAmount(tokens[2], lineNo);
      const parts = tokens.slice(3).map((t) => parseName(t, lineNo));
      if (new Set(parts).size !== parts.length) {
        throw new InvalidInput(`line ${lineNo}: duplicate participant`);
      }
      const q = Math.floor(amount / parts.length);
      const r = amount % parts.length;
      add(payer, amount);
      parts.forEach((p, i) => add(p, -(q + (i < r ? 1 : 0))));
    } else if (tokens[0] === "transfer") {
      if (tokens.length !== 4) throw new InvalidInput(`line ${lineNo}: transfer needs 4 tokens`);
      const from = parseName(tokens[1], lineNo);
      const to = parseName(tokens[2], lineNo);
      const amount = parseAmount(tokens[3], lineNo);
      if (from === to) throw new InvalidInput(`line ${lineNo}: transfer to self`);
      add(from, amount);
      add(to, -amount);
    } else {
      throw new InvalidInput(`line ${lineNo}: unknown record '${tokens[0]}'`);
    }
  });
  return balances;
}

function money(cents: number, signed: boolean): string {
  const abs = Math.abs(cents);
  const body = `${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
  if (!signed || cents === 0) return body;
  return (cents > 0 ? "+" : "-") + body;
}

function settle(balances: Map<string, number>, names: string[]): string[] {
  const work = new Map(balances);
  const payments: string[] = [];
  for (;;) {
    let debtor: string | null = null;
    let creditor: string | null = null;
    for (const n of names) {
      const b = work.get(n)!;
      if (b < 0 && (debtor === null || b < work.get(debtor)!)) debtor = n;
      if (b > 0 && (creditor === null || b > work.get(creditor)!)) creditor = n;
    }
    if (debtor === null || creditor === null) break;
    const x = Math.min(-work.get(debtor)!, work.get(creditor)!);
    work.set(debtor, work.get(debtor)! + x);
    work.set(creditor, work.get(creditor)! - x);
    payments.push(`${debtor} pays ${creditor} ${money(x, false)}`);
  }
  return payments;
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("splitbill: takes no arguments\n");
    process.exit(2);
  }
  let balances: Map<string, number>;
  try {
    balances = computeBalances(readLines());
  } catch (e) {
    if (!(e instanceof InvalidInput)) throw e;
    process.stderr.write(`splitbill: ${e.message}\n`);
    process.exit(1);
  }
  const names = [...balances.keys()].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  const out = names.map((n) => `${n} ${money(balances.get(n)!, true)}`);
  out.push("--", ...settle(balances, names));
  process.stdout.write(out.join("\n") + "\n");
}

main();
