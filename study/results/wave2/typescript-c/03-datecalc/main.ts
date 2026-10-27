interface Date3 {
  year: number;
  month: number;
  day: number;
}

const MIN_ORDINAL = 0;
const MAX_ORDINAL = 3652058;

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const MONTH_ABBREVS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

class UsageError extends Error {}
class DateError extends Error {}

function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

function daysInMonth(year: number, month: number): number {
  if (month === 2) {
    return isLeapYear(year) ? 29 : 28;
  }
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}

// Days since 0001-01-01 (which is ordinal 0).
function toOrdinal(date: Date3): number {
  const y = date.year - 1;
  let days = y * 365 + Math.floor(y / 4) - Math.floor(y / 100) + Math.floor(y / 400);
  for (let month = 1; month < date.month; month++) {
    days += daysInMonth(date.year, month);
  }
  return days + date.day - 1;
}

function fromOrdinal(ordinal: number): Date3 {
  // Narrow the year with an estimate, then walk to the exact one.
  let year = Math.max(1, Math.min(9999, Math.floor(ordinal / 365.2425) + 1));
  while (year > 1 && toOrdinal({ year, month: 1, day: 1 }) > ordinal) {
    year--;
  }
  while (year < 9999 && toOrdinal({ year: year + 1, month: 1, day: 1 }) <= ordinal) {
    year++;
  }
  let remaining = ordinal - toOrdinal({ year, month: 1, day: 1 });
  let month = 1;
  while (remaining >= daysInMonth(year, month)) {
    remaining -= daysInMonth(year, month);
    month++;
  }
  return { year, month, day: remaining + 1 };
}

function parseDate(text: string): Date3 {
  const match = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/.exec(text);
  if (match === null) {
    throw new DateError(`invalid date: ${text}`);
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > daysInMonth(year, month)) {
    throw new DateError(`invalid date: ${text}`);
  }
  return { year, month, day };
}

function parseCount(text: string): number {
  if (!/^-?[0-9]{1,7}$/.test(text)) {
    throw new UsageError(`bad number: ${text}`);
  }
  return Number(text);
}

function pad(value: number, width: number): string {
  return String(value).padStart(width, "0");
}

function checkFormat(format: string): void {
  for (let i = 0; i < format.length; i++) {
    if (format[i] !== "%") {
      continue;
    }
    i++;
    if (i >= format.length || !"Ymdjab%".includes(format[i])) {
      throw new UsageError("bad format");
    }
  }
}

function weekdayIndex(date: Date3): number {
  return toOrdinal(date) % 7;
}

function formatDate(format: string, date: Date3): string {
  let out = "";
  for (let i = 0; i < format.length; i++) {
    if (format[i] !== "%") {
      out += format[i];
      continue;
    }
    i++;
    switch (format[i]) {
      case "Y":
        out += pad(date.year, 4);
        break;
      case "m":
        out += pad(date.month, 2);
        break;
      case "d":
        out += pad(date.day, 2);
        break;
      case "j":
        out += pad(toOrdinal(date) - toOrdinal({ year: date.year, month: 1, day: 1 }) + 1, 3);
        break;
      case "a":
        out += WEEKDAYS[weekdayIndex(date)].slice(0, 3);
        break;
      case "b":
        out += MONTH_ABBREVS[date.month - 1];
        break;
      case "%":
        out += "%";
        break;
    }
  }
  return out;
}

function run(args: string[]): string {
  let format = "%Y-%m-%d";
  let i = 0;
  for (; i < args.length && args[i].startsWith("-"); i++) {
    if (args[i] !== "-F") {
      throw new UsageError(`unknown option: ${args[i]}`);
    }
    if (i + 1 >= args.length) {
      throw new UsageError("-F needs an argument");
    }
    format = args[++i];
  }
  if (i >= args.length) {
    throw new UsageError("no command");
  }
  const command = args[i];
  const operands = args.slice(i + 1);

  const arity: Record<string, number> = { weekday: 1, add: 2, diff: 2, addmonths: 2 };
  if (!Object.hasOwn(arity, command) || operands.length !== arity[command]) {
    throw new UsageError("bad command or argument count");
  }
  checkFormat(format);
  const count = command === "add" || command === "addmonths" ? parseCount(operands[1]) : 0;

  switch (command) {
    case "weekday":
      return WEEKDAYS[weekdayIndex(parseDate(operands[0]))];
    case "diff": {
      const from = parseDate(operands[0]);
      const to = parseDate(operands[1]);
      return String(toOrdinal(to) - toOrdinal(from));
    }
    case "add": {
      const ordinal = toOrdinal(parseDate(operands[0])) + count;
      if (ordinal < MIN_ORDINAL || ordinal > MAX_ORDINAL) {
        throw new DateError("result out of range");
      }
      return formatDate(format, fromOrdinal(ordinal));
    }
    default: {
      const date = parseDate(operands[0]);
      const total = date.year * 12 + (date.month - 1) + count;
      const year = Math.floor(total / 12);
      const month = total - year * 12 + 1;
      if (year < 1 || year > 9999) {
        throw new DateError("result out of range");
      }
      const day = Math.min(date.day, daysInMonth(year, month));
      return formatDate(format, { year, month, day });
    }
  }
}

function main(): number {
  try {
    process.stdout.write(run(process.argv.slice(2)) + "\n");
    return 0;
  } catch (error) {
    if (error instanceof UsageError) {
      console.error(error.message);
      return 2;
    }
    if (error instanceof DateError) {
      console.error(error.message);
      return 1;
    }
    throw error;
  }
}

process.exitCode = main();
