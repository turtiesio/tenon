import { readFileSync } from "node:fs";

class InputError extends Error {}

type Book = { id: string; title: string; rate: number; cap: number };
type Loan = { member: string; bookId: string; out: number; due: number; returned: number | null };
type LateLoan = { book: Book; days: number; fine: number };
type MemberReport = { name: string; loans: number; late: LateLoan[]; fine: number };

const BOOK_ID_RE = /^[A-Za-z0-9-]{1,12}$/;
const MEMBER_RE = /^[a-z][a-z0-9]{0,11}$/;
const NUM_RE = /^[0-9]{1,6}$/;

function readRecords(path: string): { lineNo: number; fields: string[] }[] {
  let text: string;
  try {
    text = readFileSync(path, "utf8");
  } catch (e) {
    throw new InputError(`cannot read ${path}: ${(e as Error).message}`);
  }
  const lines = text === "" ? [] : text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  const records: { lineNo: number; fields: string[] }[] = [];
  lines.forEach((raw, i) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line === "" || line.startsWith("#")) return;
    records.push({ lineNo: i + 1, fields: line.split("|") });
  });
  return records;
}

function check(ok: boolean, path: string, lineNo: number, what: string): void {
  if (!ok) throw new InputError(`${path}:${lineNo}: ${what}`);
}

function loadBooks(path: string): Map<string, Book> {
  const books = new Map<string, Book>();
  for (const { lineNo, fields } of readRecords(path)) {
    check(fields.length === 4, path, lineNo, "expected 4 fields");
    const [id, title, rate, cap] = fields;
    check(BOOK_ID_RE.test(id), path, lineNo, "bad book id");
    check(title !== "", path, lineNo, "empty title");
    check(NUM_RE.test(rate) && NUM_RE.test(cap), path, lineNo, "bad rate or cap");
    check(!books.has(id), path, lineNo, `duplicate book id ${id}`);
    books.set(id, { id, title, rate: Number(rate), cap: Number(cap) });
  }
  return books;
}

function loadLoans(path: string): Loan[] {
  return readRecords(path).map(({ lineNo, fields }) => {
    check(fields.length === 5, path, lineNo, "expected 5 fields");
    const [member, bookId, out, due, returned] = fields;
    check(MEMBER_RE.test(member), path, lineNo, "bad member");
    check(BOOK_ID_RE.test(bookId), path, lineNo, "bad book id");
    check(NUM_RE.test(out) && NUM_RE.test(due), path, lineNo, "bad day number");
    check(Number(due) >= Number(out), path, lineNo, "due before out");
    check(returned === "-" || NUM_RE.test(returned), path, lineNo, "bad returned day");
    if (returned !== "-") check(Number(returned) >= Number(out), path, lineNo, "returned before out");
    return {
      member,
      bookId,
      out: Number(out),
      due: Number(due),
      returned: returned === "-" ? null : Number(returned),
    };
  });
}

const money = (cents: number): string => `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, "0")}`;

function main(argv: string[]): void {
  if (argv.length !== 3 || !NUM_RE.test(argv[2])) {
    process.stderr.write("usage: libfines BOOKS LOANS TODAY\n");
    process.exit(2);
  }
  const today = Number(argv[2]);

  let books: Map<string, Book>;
  let loans: Loan[];
  try {
    books = loadBooks(argv[0]);
    loans = loadLoans(argv[1]);
  } catch (e) {
    if (e instanceof InputError) {
      process.stderr.write(`libfines: ${e.message}\n`);
      process.exit(1);
    }
    throw e;
  }

  const members = new Map<string, MemberReport>();
  let skipped = 0;
  let total = 0;
  for (const loan of loans) {
    const book = books.get(loan.bookId);
    if (!book) {
      skipped++;
      continue;
    }
    let report = members.get(loan.member);
    if (!report) {
      report = { name: loan.member, loans: 0, late: [], fine: 0 };
      members.set(loan.member, report);
    }
    const days = Math.max(0, (loan.returned ?? today) - loan.due);
    const fine = Math.min(days * book.rate, book.cap);
    report.loans++;
    report.fine += fine;
    total += fine;
    if (days > 0) report.late.push({ book, days, fine });
  }

  const sorted = [...members.values()].sort(
    (a, b) => b.fine - a.fine || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0),
  );
  const out: string[] = [];
  for (const m of sorted) {
    out.push(`${m.name} loans=${m.loans} late=${m.late.length} fine=${money(m.fine)}`);
    for (const l of m.late) out.push(`  ${l.book.id} ${l.book.title} days=${l.days} fine=${money(l.fine)}`);
  }
  out.push(`total=${money(total)} skipped=${skipped}`);
  process.stdout.write(out.join("\n") + "\n");
}

main(process.argv.slice(2));
