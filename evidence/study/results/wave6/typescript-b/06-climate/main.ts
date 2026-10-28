import * as fs from "node:fs";

interface Reading {
  station: string;
  date: string; // YYYY-MM-DD
  temp: number; // tenths of a degree
}

interface Group {
  station: string;
  period: string;
  days: number;
  min: number;
  max: number;
  sum: number;
}

const DATE_RE = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/;
const TEMP_RE = /^(-?)([0-9]{1,2})\.([0-9])$/;

function isLeap(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

function isValidDate(text: string): boolean {
  const m = DATE_RE.exec(text);
  if (!m) return false;
  const [year, month, day] = [Number(m[1]), Number(m[2]), Number(m[3])];
  if (year < 1 || month < 1 || month > 12 || day < 1) return false;
  const monthDays = [31, isLeap(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day <= monthDays[month - 1];
}

function parseReading(line: string): Reading | null {
  const fields = line.split(";");
  if (fields.length !== 3) return null;
  const [station, date, tempText] = fields;
  const length = [...station].length;
  if (length < 1 || length > 40 || station.startsWith(" ") || station.endsWith(" ")) return null;
  if (!isValidDate(date)) return null;
  const t = TEMP_RE.exec(tempText);
  if (!t) return null;
  const magnitude = Number(t[2]) * 10 + Number(t[3]);
  return { station, date, temp: t[1] === "-" ? -magnitude : magnitude };
}

function formatTenths(t: number): string {
  const sign = t < 0 ? "-" : "";
  const abs = Math.abs(t);
  return `${sign}${Math.floor(abs / 10)}.${abs % 10}`;
}

/** sum / count rounded to the nearest integer, halves away from zero. */
function roundedMean(sum: number, count: number): number {
  const q = Math.floor((2 * Math.abs(sum) + count) / (2 * count));
  return sum < 0 ? -q : q;
}

function compareText(a: string, b: string): number {
  return Buffer.compare(Buffer.from(a, "utf8"), Buffer.from(b, "utf8"));
}

function main(): number {
  const args = process.argv.slice(2);
  if (args.length > 1 || (args.length === 1 && args[0] !== "-y")) {
    process.stderr.write("usage: climate [-y]\n");
    return 2;
  }
  const byYear = args.length === 1;

  const lines = fs.readFileSync(0, "utf8").split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  let skipped = 0;
  let replaced = 0;
  // Keyed by station and date; re-inserting keeps the last reading.
  const latest = new Map<string, Reading>();
  for (const raw of lines) {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line === "") continue;
    const reading = parseReading(line);
    if (reading === null) {
      skipped++;
      continue;
    }
    const key = `${reading.station};${reading.date}`;
    if (latest.has(key)) replaced++;
    latest.set(key, reading);
  }

  const groups = new Map<string, Group>();
  for (const r of latest.values()) {
    const period = r.date.slice(0, byYear ? 4 : 7);
    const key = `${r.station};${period}`;
    const g = groups.get(key);
    if (g === undefined) {
      groups.set(key, { station: r.station, period, days: 1, min: r.temp, max: r.temp, sum: r.temp });
    } else {
      g.days++;
      g.min = Math.min(g.min, r.temp);
      g.max = Math.max(g.max, r.temp);
      g.sum += r.temp;
    }
  }

  const sorted = [...groups.values()].sort(
    (a, b) => compareText(a.station, b.station) || compareText(a.period, b.period),
  );
  let out = "";
  for (const g of sorted) {
    out += `${g.station} ${g.period} days=${g.days} min=${formatTenths(g.min)} max=${formatTenths(g.max)}` +
      ` mean=${formatTenths(roundedMean(g.sum, g.days))}\n`;
  }
  out += `readings=${latest.size} skipped=${skipped} replaced=${replaced}\n`;
  process.stdout.write(out);
  return 0;
}

process.exitCode = main();
