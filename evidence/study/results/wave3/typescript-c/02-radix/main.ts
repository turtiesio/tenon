const MAX_VALUE = 9223372036854775807n;
const DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz";

class UsageError extends Error {}

interface Options {
  from: number;
  to: number;
  width: number | null;
  group: number | null;
  upper: boolean;
  values: string[];
}

function intOption(name: string, text: string, min: number, max: number): number {
  if (!/^[0-9]{1,2}$/.test(text)) {
    throw new UsageError(`bad value for ${name}: ${text}`);
  }
  const n = Number(text);
  if (n < min || n > max) {
    throw new UsageError(`value for ${name} out of range: ${text}`);
  }
  return n;
}

function parseArgs(args: string[]): Options {
  const options: Options = {
    from: 10,
    to: 10,
    width: null,
    group: null,
    upper: false,
    values: [],
  };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    switch (arg) {
      case "-f":
      case "-t":
      case "-w":
      case "-g": {
        if (i + 1 >= args.length) throw new UsageError(`${arg} needs an argument`);
        const text = args[++i];
        if (arg === "-f") options.from = intOption(arg, text, 2, 36);
        else if (arg === "-t") options.to = intOption(arg, text, 2, 36);
        else if (arg === "-w") options.width = intOption(arg, text, 1, 64);
        else options.group = intOption(arg, text, 1, 64);
        break;
      }
      case "-u":
        options.upper = true;
        break;
      default:
        options.values.push(arg);
    }
  }
  if (options.values.length === 0) throw new UsageError("no VALUE given");
  return options;
}

// Returns the signed value, or null if the text is not a valid VALUE.
function parseValue(text: string, base: number): bigint | null {
  const negative = text.startsWith("-");
  const digits = negative ? text.slice(1) : text;
  if (digits === "") return null;
  const bigBase = BigInt(base);
  let magnitude = 0n;
  for (const ch of digits.toLowerCase()) {
    const d = DIGITS.indexOf(ch);
    if (d < 0 || d >= base) return null;
    magnitude = magnitude * bigBase + BigInt(d);
    if (magnitude > MAX_VALUE) return null;
  }
  return negative ? -magnitude : magnitude;
}

function format(value: bigint, options: Options): string {
  const negative = value < 0n;
  let rest = negative ? -value : value;
  const base = BigInt(options.to);
  let digits = "";
  do {
    digits = DIGITS[Number(rest % base)] + digits;
    rest /= base;
  } while (rest > 0n);
  if (options.width !== null) digits = digits.padStart(options.width, "0");
  if (options.group !== null) {
    const groups: string[] = [];
    for (let end = digits.length; end > 0; end -= options.group) {
      groups.unshift(digits.slice(Math.max(0, end - options.group), end));
    }
    digits = groups.join("_");
  }
  if (options.upper) digits = digits.toUpperCase();
  return (negative ? "-" : "") + digits;
}

function main(): number {
  let options: Options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`radix: ${e.message}\n`);
      return 2;
    }
    throw e;
  }
  let status = 0;
  let out = "";
  for (const text of options.values) {
    const value = parseValue(text, options.from);
    if (value === null) {
      process.stderr.write(`radix: invalid value: ${text}\n`);
      status = 1;
    } else {
      out += format(value, options) + "\n";
    }
  }
  process.stdout.write(out);
  return status;
}

process.exitCode = main();
