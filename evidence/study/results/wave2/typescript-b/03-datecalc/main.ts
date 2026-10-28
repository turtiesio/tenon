interface CivilDate {
  year: number;
  month: number;
  day: number;
}

class UsageError extends Error {}
class DateError extends Error {}

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DEFAULT_FORMAT = "%Y-%m-%d";

const ARITY: Record<string, number> = {
  weekday: 1,
  add: 2,
  diff: 2,
  addmonths: 2,
};

function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

function daysInMonth(year: number, month: number): number {
  const lengths = [31, isLeapYear(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return lengths[month - 1];
}

// Days since 1970-01-01 (Howard Hinnant's days_from_civil).
function toDayNumber(date: CivilDate): number {
  const y = date.month <= 2 ? date.year - 1 : date.year;
  const era = Math.floor(y / 400);
  const yoe = y - era * 400;
  const mp = (date.month + 9) % 12;
  const doy = Math.floor((153 * mp + 2) / 5) + date.day - 1;
  const doe = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
  return era * 146097 + doe - 719468;
}

function fromDayNumber(days: number): CivilDate {
  const z = days + 719468;
  const era = Math.floor(z / 146097);
  const doe = z - era * 146097;
  const yoe = Math.floor((doe - Math.floor(doe / 1460) + Math.floor(doe / 36524) - Math.floor(doe / 146096)) / 365);
  const doy = doe - (365 * yoe + Math.floor(yoe / 4) - Math.floor(yoe / 100));
  const mp = Math.floor((5 * doy + 2) / 153);
  const day = doy - Math.floor((153 * mp + 2) / 5) + 1;
  const month = mp < 10 ? mp + 3 : mp - 9;
  const year = yoe + era * 400 + (month <= 2 ? 1 : 0);
  return { year, month, day };
}

const MIN_DAY = toDayNumber({ year: 1, month: 1, day: 1 });
const MAX_DAY = toDayNumber({ year: 9999, month: 12, day: 31 });

function weekdayIndex(date: CivilDate): number {
  // 1970-01-01 was a Thursday (index 3 with Monday = 0).
  const days = toDayNumber(date);
  return (((days + 3) % 7) + 7) % 7;
}

function parseDate(text: string): CivilDate {
  const m = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/.exec(text);
  if (!m) {
    throw new DateError(`invalid date: ${text}`);
  }
  const year = Number(m[1]);
  const month = Number(m[2]);
  const day = Number(m[3]);
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > daysInMonth(year, month)) {
    throw new DateError(`invalid date: ${text}`);
  }
  return { year, month, day };
}

function parseCount(text: string): number {
  if (!/^-?[0-9]{1,7}$/.test(text)) {
    throw new UsageError(`invalid number: ${text}`);
  }
  return Number(text);
}

function validateFormat(format: string): void {
  for (let i = 0; i < format.length; i++) {
    if (format[i] !== "%") {
      continue;
    }
    const directive = format[i + 1];
    if (directive === undefined || !"Ymdjab%".includes(directive)) {
      throw new UsageError(`invalid format: ${format}`);
    }
    i++;
  }
}

function pad(value: number, width: number): string {
  return String(value).padStart(width, "0");
}

function formatDate(date: CivilDate, format: string): string {
  let out = "";
  for (let i = 0; i < format.length; i++) {
    const c = format[i];
    if (c !== "%") {
      out += c;
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
      case "j": {
        const dayOfYear = toDayNumber(date) - toDayNumber({ year: date.year, month: 1, day: 1 }) + 1;
        out += pad(dayOfYear, 3);
        break;
      }
      case "a":
        out += WEEKDAYS[weekdayIndex(date)].slice(0, 3);
        break;
      case "b":
        out += MONTHS[date.month - 1];
        break;
      case "%":
        out += "%";
        break;
    }
  }
  return out;
}

function checkRange(days: number): CivilDate {
  if (days < MIN_DAY || days > MAX_DAY) {
    throw new DateError("result out of range");
  }
  return fromDayNumber(days);
}

function addMonths(date: CivilDate, n: number): CivilDate {
  const monthIndex = date.year * 12 + (date.month - 1) + n;
  const year = Math.floor(monthIndex / 12);
  const month = monthIndex - year * 12 + 1;
  if (year < 1 || year > 9999) {
    throw new DateError("result out of range");
  }
  return { year, month, day: Math.min(date.day, daysInMonth(year, month)) };
}

function run(argv: string[]): string {
  let format = DEFAULT_FORMAT;
  let index = 0;
  while (index < argv.length && argv[index].startsWith("-")) {
    if (argv[index] !== "-F") {
      throw new UsageError(`unknown option: ${argv[index]}`);
    }
    if (index + 1 >= argv.length) {
      throw new UsageError("-F requires an argument");
    }
    format = argv[index + 1];
    index += 2;
  }
  if (index >= argv.length) {
    throw new UsageError("missing command");
  }
  const command = argv[index];
  const args = argv.slice(index + 1);
  if (!Object.hasOwn(ARITY, command)) {
    throw new UsageError(`unknown command: ${command}`);
  }
  if (args.length !== ARITY[command]) {
    throw new UsageError(`wrong number of arguments for ${command}`);
  }
  const count = command === "add" || command === "addmonths" ? parseCount(args[1]) : 0;
  validateFormat(format);

  switch (command) {
    case "weekday":
      return WEEKDAYS[weekdayIndex(parseDate(args[0]))];
    case "diff":
      return String(toDayNumber(parseDate(args[1])) - toDayNumber(parseDate(args[0])));
    case "add":
      return formatDate(checkRange(toDayNumber(parseDate(args[0])) + count), format);
    case "addmonths":
      return formatDate(addMonths(parseDate(args[0]), count), format);
    default:
      throw new UsageError(`unknown command: ${command}`);
  }
}

function main(argv: string[]): number {
  try {
    process.stdout.write(run(argv) + "\n");
    return 0;
  } catch (err) {
    if (err instanceof UsageError) {
      process.stderr.write(`datecalc: ${err.message}\n`);
      return 2;
    }
    if (err instanceof DateError) {
      process.stderr.write(`datecalc: ${err.message}\n`);
      return 1;
    }
    throw err;
  }
}

process.exitCode = main(process.argv.slice(2));
