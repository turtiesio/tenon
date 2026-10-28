import { readFileSync } from "node:fs";

interface Reading {
  station: string;
  date: string; // YYYY-MM-DD
  tenths: number;
}

interface Group {
  station: string;
  period: string;
  days: number;
  min: number;
  max: number;
  sum: number;
}

const DATE = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/;
const TEMP = /^(-?)([0-9]{1,2})\.([0-9])$/;

function readStdin(): string {
  try {
    return readFileSync(0, "utf8");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "EOF") return "";
    throw e;
  }
}

function splitLines(text: string): string[] {
  if (text === "") return [];
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  return lines.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line));
}

function isLeap(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

function isRealDate(date: string): boolean {
  const m = DATE.exec(date);
  if (!m) return false;
  const year = Number(m[1]);
  const month = Number(m[2]);
  const day = Number(m[3]);
  if (year < 1 || month < 1 || month > 12 || day < 1) return false;
  const daysInMonth = [31, isLeap(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day <= daysInMonth[month - 1];
}

function isValidStation(s: string): boolean {
  const length = [...s].length;
  return length >= 1 && length <= 40 && !s.includes(";") && !s.startsWith(" ") && !s.endsWith(" ");
}

function parseReading(line: string): Reading | null {
  const fields = line.split(";");
  if (fields.length !== 3) return null;
  const [station, date, temp] = fields;
  if (!isValidStation(station) || !isRealDate(date)) return null;
  const t = TEMP.exec(temp);
  if (!t) return null;
  const magnitude = Number(t[2]) * 10 + Number(t[3]);
  return { station, date, tenths: t[1] === "-" ? -magnitude : magnitude };
}

/** Rounds sum / days to the nearest integer, exact halves away from zero. */
function roundedMean(sum: number, days: number): number {
  const q = Math.floor((2 * Math.abs(sum) + days) / (2 * days));
  return sum < 0 ? -q : q;
}

function formatTenths(t: number): string {
  const abs = Math.abs(t);
  return `${t < 0 ? "-" : ""}${Math.floor(abs / 10)}.${abs % 10}`;
}

function compareBytes(a: string, b: string): number {
  return Buffer.compare(Buffer.from(a, "utf8"), Buffer.from(b, "utf8"));
}

function main(): number {
  const args = process.argv.slice(2);
  if (args.length > 1 || (args.length === 1 && args[0] !== "-y")) {
    process.stderr.write("usage: climate [-y]\n");
    return 2;
  }
  const byYear = args.length === 1;

  let skipped = 0;
  let replaced = 0;
  const latest = new Map<string, Reading>();
  for (const line of splitLines(readStdin())) {
    if (line === "") continue;
    const reading = parseReading(line);
    if (!reading) {
      skipped++;
      continue;
    }
    const key = `${reading.station};${reading.date}`;
    if (latest.has(key)) replaced++;
    latest.set(key, reading);
  }

  const groups = new Map<string, Group>();
  for (const r of latest.values()) {
    const period = byYear ? r.date.slice(0, 4) : r.date.slice(0, 7);
    const key = `${r.station};${period}`;
    const g = groups.get(key);
    if (!g) {
      groups.set(key, { station: r.station, period, days: 1, min: r.tenths, max: r.tenths, sum: r.tenths });
    } else {
      g.days++;
      g.min = Math.min(g.min, r.tenths);
      g.max = Math.max(g.max, r.tenths);
      g.sum += r.tenths;
    }
  }

  const sorted = [...groups.values()].sort(
    (a, b) => compareBytes(a.station, b.station) || compareBytes(a.period, b.period),
  );
  let out = "";
  for (const g of sorted) {
    out += `${g.station} ${g.period} days=${g.days} min=${formatTenths(g.min)} max=${formatTenths(g.max)} `;
    out += `mean=${formatTenths(roundedMean(g.sum, g.days))}\n`;
  }
  out += `readings=${latest.size} skipped=${skipped} replaced=${replaced}\n`;
  process.stdout.write(out);
  return 0;
}

process.exitCode = main();
