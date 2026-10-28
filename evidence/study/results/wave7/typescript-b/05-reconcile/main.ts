import * as fs from "node:fs";

interface Entry {
  lineNo: number;
  date: string;
  day: number; // days since 1970-01-01
  cents: number;
  text: string;
}

class UsageError extends Error {}
class InputError extends Error {}

const MS_PER_DAY = 86_400_000;

/** Returns the day number of a valid YYYY-MM-DD date in 1970-2099, or null. */
function parseDate(s: string): number | null {
  const m = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/.exec(s);
  if (m === null) return null;
  const [year, month, day] = [Number(m[1]), Number(m[2]), Number(m[3])];
  if (year < 1970 || year > 2099 || month < 1 || month > 12 || day < 1) return null;
  const ms = Date.UTC(year, month - 1, day);
  const d = new Date(ms);
  if (d.getUTCMonth() !== month - 1 || d.getUTCDate() !== day) return null;
  return ms / MS_PER_DAY;
}

function parseAmount(s: string): number | null {
  const m = /^(-?)(0|[1-9][0-9]{0,8})\.([0-9]{2})$/.exec(s);
  if (m === null) return null;
  const cents = Number(m[2]) * 100 + Number(m[3]);
  return m[1] === "-" ? -cents : cents;
}

function isValidText(s: string): boolean {
  return /^[\x20-\x7e]{1,40}$/.test(s) && !s.includes(",") && !s.startsWith(" ") && !s.endsWith(" ");
}

function formatAmount(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

function readEntries(path: string): Entry[] {
  let text: string;
  try {
    text = fs.readFileSync(path, "latin1");
  } catch (e) {
    throw new InputError(`cannot read ${path}: ${(e as Error).message}`);
  }
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  const entries: Entry[] = [];
  lines.forEach((raw, index) => {
    const lineNo = index + 1;
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line === "") return;
    const fields = line.split(",");
    const invalid = (why: string) => new InputError(`${path}:${lineNo}: ${why}`);
    if (fields.length !== 3) throw invalid("expected date,amount,text");
    const [date, amount, desc] = fields;
    const day = parseDate(date);
    if (day === null) throw invalid(`bad date: ${date}`);
    const cents = parseAmount(amount);
    if (cents === null) throw invalid(`bad amount: ${amount}`);
    if (!isValidText(desc)) throw invalid(`bad text: ${JSON.stringify(desc)}`);
    entries.push({ lineNo, date, day, cents, text: desc });
  });
  return entries;
}

function parseArgs(args: string[]): { days: number; files: string[] } {
  let days = 3;
  const files: string[] = [];
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-d") {
      if (i + 1 >= args.length) throw new UsageError("-d needs a value");
      const value = args[++i];
      if (!/^(0|[1-9][0-9]{0,2})$/.test(value) || Number(value) > 365) throw new UsageError(`bad DAYS: ${value}`);
      days = Number(value);
    } else if (arg.startsWith("-")) {
      throw new UsageError(`unknown option: ${arg}`);
    } else {
      files.push(arg);
    }
  }
  if (files.length !== 2) throw new UsageError("expected exactly two files: BANK LEDGER");
  return { days, files };
}

function main(): void {
  let days: number;
  let files: string[];
  try {
    ({ days, files } = parseArgs(process.argv.slice(2)));
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`reconcile: ${e.message}\nusage: reconcile [-d DAYS] BANK LEDGER\n`);
      process.exit(2);
    }
    throw e;
  }

  let bank: Entry[];
  let ledger: Entry[];
  try {
    bank = readEntries(files[0]);
    ledger = readEntries(files[1]);
  } catch (e) {
    if (e instanceof InputError) {
      process.stderr.write(`reconcile: ${e.message}\n`);
      process.exit(1);
    }
    throw e;
  }

  const out: string[] = [];
  const ledgerMatched = new Set<Entry>();
  const bankOnly: Entry[] = [];
  let matches = 0;
  for (const b of bank) {
    let best: Entry | null = null;
    let bestDistance = Infinity;
    for (const l of ledger) {
      if (ledgerMatched.has(l) || l.cents !== b.cents) continue;
      const distance = Math.abs(l.day - b.day);
      // Ledger lines are in line order, so the first of equal distances wins.
      if (distance <= days && distance < bestDistance) {
        best = l;
        bestDistance = distance;
      }
    }
    if (best === null) {
      bankOnly.push(b);
    } else {
      ledgerMatched.add(best);
      matches++;
      out.push(`M ${b.lineNo} ${best.lineNo} ${formatAmount(b.cents)} ${bestDistance}`);
    }
  }
  const ledgerOnly = ledger.filter((l) => !ledgerMatched.has(l));
  for (const b of bankOnly) out.push(`B ${b.lineNo} ${b.date} ${formatAmount(b.cents)} ${b.text}`);
  for (const l of ledgerOnly) out.push(`L ${l.lineNo} ${l.date} ${formatAmount(l.cents)} ${l.text}`);
  const sum = (entries: Entry[]) => entries.reduce((total, e) => total + e.cents, 0);
  const diff = sum(bankOnly) - sum(ledgerOnly);
  out.push(`matched=${matches} bank_only=${bankOnly.length} ledger_only=${ledgerOnly.length} diff=${formatAmount(diff)}`);
  process.stdout.write(out.map((l) => l + "\n").join(""));
}

main();
