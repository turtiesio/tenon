import { readFileSync } from "node:fs";

const BOOK_ID = /^[A-Za-z0-9-]{1,12}$/;
const MEMBER = /^[a-z][a-z0-9]{0,11}$/;
const DAY = /^[0-9]{1,6}$/;

class InvalidFile extends Error {}

interface Book {
  title: string;
  rate: number;
  cap: number;
}

interface Loan {
  member: string;
  bookId: string;
  due: number;
  returned: number | null;
}

interface Member {
  loans: number;
  late: number;
  fine: number;
  lateLines: { bookId: string; title: string; days: number; fine: number }[];
}

function readRecords(path: string, fieldCount: number): string[][] {
  let text: string;
  try {
    text = readFileSync(path, "utf8");
  } catch {
    throw new InvalidFile(`cannot read ${path}`);
  }
  const lines = text.split("\n");
  if (text.endsWith("\n") || text === "") lines.pop();
  const records: string[][] = [];
  lines.forEach((raw, idx) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line === "" || line.startsWith("#")) return;
    const fields = line.split("|");
    if (fields.length !== fieldCount) {
      throw new InvalidFile(`${path}:${idx + 1}: expected ${fieldCount} fields`);
    }
    records.push(fields);
  });
  return records;
}

function loadBooks(path: string): Map<string, Book> {
  const books = new Map<string, Book>();
  for (const [id, title, rate, cap] of readRecords(path, 4)) {
    if (!BOOK_ID.test(id) || title === "" || !DAY.test(rate) || !DAY.test(cap)) {
      throw new InvalidFile(`${path}: bad book record for '${id}'`);
    }
    if (books.has(id)) throw new InvalidFile(`${path}: duplicate book id '${id}'`);
    books.set(id, { title, rate: Number(rate), cap: Number(cap) });
  }
  return books;
}

function loadLoans(path: string): Loan[] {
  return readRecords(path, 5).map(([member, bookId, out, due, returned]) => {
    const returnedOk = returned === "-" || DAY.test(returned);
    if (!MEMBER.test(member) || !BOOK_ID.test(bookId) || !DAY.test(out) || !DAY.test(due) || !returnedOk) {
      throw new InvalidFile(`${path}: bad loan record for '${member}'`);
    }
    if (Number(due) < Number(out)) throw new InvalidFile(`${path}: due before out for '${member}'`);
    if (returned !== "-" && Number(returned) < Number(out)) {
      throw new InvalidFile(`${path}: returned before out for '${member}'`);
    }
    return { member, bookId, due: Number(due), returned: returned === "-" ? null : Number(returned) };
  });
}

function money(cents: number): string {
  return `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, "0")}`;
}

function report(books: Map<string, Book>, loans: Loan[], today: number): string {
  const members = new Map<string, Member>();
  let total = 0;
  let skipped = 0;

  for (const loan of loans) {
    const book = books.get(loan.bookId);
    if (book === undefined) {
      skipped++;
      continue;
    }
    let m = members.get(loan.member);
    if (m === undefined) {
      m = { loans: 0, late: 0, fine: 0, lateLines: [] };
      members.set(loan.member, m);
    }
    const days = Math.max(0, (loan.returned ?? today) - loan.due);
    const fine = Math.min(days * book.rate, book.cap);
    m.loans++;
    m.fine += fine;
    total += fine;
    if (days > 0) {
      m.late++;
      m.lateLines.push({ bookId: loan.bookId, title: book.title, days, fine });
    }
  }

  const names = [...members.keys()].sort((a, b) => {
    const diff = members.get(b)!.fine - members.get(a)!.fine;
    return diff !== 0 ? diff : a < b ? -1 : a > b ? 1 : 0;
  });

  const out: string[] = [];
  for (const name of names) {
    const m = members.get(name)!;
    out.push(`${name} loans=${m.loans} late=${m.late} fine=${money(m.fine)}`);
    for (const l of m.lateLines) {
      out.push(`  ${l.bookId} ${l.title} days=${l.days} fine=${money(l.fine)}`);
    }
  }
  out.push(`total=${money(total)} skipped=${skipped}`);
  return out.join("\n") + "\n";
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 3 || !DAY.test(args[2])) {
    process.stderr.write("libfines: usage: libfines BOOKS LOANS TODAY\n");
    process.exit(2);
  }
  const [booksPath, loansPath, today] = args;
  try {
    const books = loadBooks(booksPath);
    const loans = loadLoans(loansPath);
    process.stdout.write(report(books, loans, Number(today)));
  } catch (e) {
    if (!(e instanceof InvalidFile)) throw e;
    process.stderr.write(`libfines: ${e.message}\n`);
    process.exit(1);
  }
}

main();
