import { readFileSync } from "node:fs";

interface Entry {
  line: number;
  date: string;
  day: number; // days since 1970-01-01
  cents: number;
  text: string;
}

class UsageError extends Error {}
class InputError extends Error {}

function isLeap(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}

function daysInMonth(year: number, month: number): number {
  if (month === 2) return isLeap(year) ? 29 : 28;
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}

// Days since 1970-01-01, or null if `date` is not a valid YYYY-MM-DD in 1970..2099.
function parseDate(date: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (m === null) return null;
  const [year, month, day] = [Number(m[1]), Number(m[2]), Number(m[3])];
  if (year < 1970 || year > 2099 || month < 1 || month > 12) return null;
  if (day < 1 || day > daysInMonth(year, month)) return null;
  return Date.UTC(year, month - 1, day) / 86_400_000;
}

function parseCents(amount: string): number | null {
  const m = /^(-?)(0|[1-9][0-9]{0,8})\.([0-9]{2})$/.exec(amount);
  if (m === null) return null;
  const cents = Number(m[2]) * 100 + Number(m[3]);
  return m[1] === "-" ? -cents : cents;
}

function formatCents(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const frac = String(abs % 100).padStart(2, "0");
  return `${sign}${Math.floor(abs / 100)}.${frac}`;
}

function parseText(text: string): boolean {
  return /^[\x20-\x2B\x2D-\x7E]{1,40}$/.test(text) && !text.startsWith(" ") && !text.endsWith(" ");
}

function loadFile(path: string): Entry[] {
  let content: string;
  try {
    content = readFileSync(path, "latin1");
  } catch (e) {
    throw new InputError(`cannot read ${path}: ${(e as Error).message}`);
  }
  const lines = content.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();

  const entries: Entry[] = [];
  lines.forEach((raw, index) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line === "") return;
    const fail = (): never => {
      throw new InputError(`${path}: line ${index + 1}: invalid line`);
    };
    const fields = line.split(",");
    if (fields.length !== 3) fail();
    const [date, amount, text] = fields;
    const day = parseDate(date);
    const cents = parseCents(amount);
    if (day === null || cents === null || !parseText(text)) fail();
    entries.push({ line: index + 1, date, day: day!, cents: cents!, text });
  });
  return entries;
}

function parseArgs(argv: string[]): { days: number; bank: string; ledger: string } {
  let days = 3;
  const files: string[] = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "-d") {
      if (i + 1 >= argv.length) throw new UsageError("-d needs a value");
      const value = argv[++i];
      if (!/^(0|[1-9][0-9]{0,2})$/.test(value) || Number(value) > 365) {
        throw new UsageError(`bad DAYS: ${value}`);
      }
      days = Number(value);
    } else if (arg.startsWith("-")) {
      throw new UsageError(`unknown argument: ${arg}`);
    } else {
      files.push(arg);
    }
  }
  if (files.length !== 2) throw new UsageError("expected exactly two files: BANK LEDGER");
  return { days, bank: files[0], ledger: files[1] };
}

function main(): number {
  let args: ReturnType<typeof parseArgs>;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`reconcile: ${e.message}\n`);
      return 2;
    }
    throw e;
  }

  let bank: Entry[];
  let ledger: Entry[];
  try {
    bank = loadFile(args.bank);
    ledger = loadFile(args.ledger);
  } catch (e) {
    if (e instanceof InputError) {
      process.stderr.write(`reconcile: ${e.message}\n`);
      return 1;
    }
    throw e;
  }

  // Unmatched ledger lines grouped by amount, in line order.
  const byAmount = new Map<number, Entry[]>();
  for (const l of ledger) {
    const group = byAmount.get(l.cents);
    if (group === undefined) byAmount.set(l.cents, [l]);
    else group.push(l);
  }

  const matches: string[] = [];
  const bankOnly: Entry[] = [];
  const matchedLedger = new Set<Entry>();
  for (const b of bank) {
    let best: Entry | undefined;
    let bestDistance = Infinity;
    for (const l of byAmount.get(b.cents) ?? []) {
      if (matchedLedger.has(l)) continue;
      const distance = Math.abs(l.day - b.day);
      // Strict '<' keeps the smallest line number among equal distances.
      if (distance <= args.days && distance < bestDistance) {
        best = l;
        bestDistance = distance;
      }
    }
    if (best === undefined) {
      bankOnly.push(b);
    } else {
      matchedLedger.add(best);
      matches.push(`M ${b.line} ${best.line} ${formatCents(b.cents)} ${bestDistance}`);
    }
  }
  const ledgerOnly = ledger.filter((l) => !matchedLedger.has(l));

  const sum = (entries: Entry[]) => entries.reduce((acc, e) => acc + e.cents, 0);
  const diff = sum(bankOnly) - sum(ledgerOnly);

  const out = [
    ...matches,
    ...bankOnly.map((b) => `B ${b.line} ${b.date} ${formatCents(b.cents)} ${b.text}`),
    ...ledgerOnly.map((l) => `L ${l.line} ${l.date} ${formatCents(l.cents)} ${l.text}`),
    `matched=${matches.length} bank_only=${bankOnly.length} ledger_only=${ledgerOnly.length} diff=${formatCents(diff)}`,
  ];
  process.stdout.write(out.map((l) => l + "\n").join(""));
  return 0;
}

process.exitCode = main();
