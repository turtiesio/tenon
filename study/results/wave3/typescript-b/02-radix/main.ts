class UsageError extends Error {}

interface Options {
  from: number;
  to: number;
  width?: number;
  group?: number;
  upper: boolean;
}

const MAX = 9223372036854775807n;

function parseOptionValue(text: string, name: string, min: number, max: number): number {
  if (!/^[0-9]{1,2}$/.test(text)) throw new UsageError(`malformed ${name}: ${text}`);
  const n = Number(text);
  if (n < min || n > max) throw new UsageError(`${name} out of range: ${text}`);
  return n;
}

function parseArgs(args: string[]): { opts: Options; values: string[] } {
  const opts: Options = { from: 10, to: 10, upper: false };
  const values: string[] = [];
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    switch (arg) {
      case "-u":
        opts.upper = true;
        break;
      case "-f":
      case "-t":
      case "-w":
      case "-g": {
        if (i + 1 >= args.length) throw new UsageError(`${arg} requires a value`);
        const value = args[++i];
        if (arg === "-f") opts.from = parseOptionValue(value, "FROM", 2, 36);
        else if (arg === "-t") opts.to = parseOptionValue(value, "TO", 2, 36);
        else if (arg === "-w") opts.width = parseOptionValue(value, "WIDTH", 1, 64);
        else opts.group = parseOptionValue(value, "GROUP", 1, 64);
        break;
      }
      default:
        values.push(arg);
    }
  }
  if (values.length === 0) throw new UsageError("no VALUE given");
  return { opts, values };
}

function digitValue(ch: string): number {
  const c = ch.toLowerCase().charCodeAt(0);
  if (c >= 48 && c <= 57) return c - 48;
  if (c >= 97 && c <= 122) return c - 97 + 10;
  return -1;
}

/** Parses VALUE in base `from`; returns null if invalid. */
function parseValue(text: string, from: number): { negative: boolean; magnitude: bigint } | null {
  const negative = text.startsWith("-");
  const digits = negative ? text.slice(1) : text;
  if (digits.length === 0) return null;
  const base = BigInt(from);
  let magnitude = 0n;
  for (const ch of digits) {
    const d = digitValue(ch);
    if (d < 0 || d >= from) return null;
    magnitude = magnitude * base + BigInt(d);
    if (magnitude > MAX) return null;
  }
  return { negative: negative && magnitude !== 0n, magnitude };
}

function format(negative: boolean, magnitude: bigint, opts: Options): string {
  let digits = magnitude.toString(opts.to);
  if (opts.upper) digits = digits.toUpperCase();
  if (opts.width !== undefined) digits = digits.padStart(opts.width, "0");
  if (opts.group !== undefined) {
    const groups: string[] = [];
    for (let end = digits.length; end > 0; end -= opts.group) {
      groups.unshift(digits.slice(Math.max(0, end - opts.group), end));
    }
    digits = groups.join("_");
  }
  return (negative ? "-" : "") + digits;
}

function main(): number {
  let parsed: { opts: Options; values: string[] };
  try {
    parsed = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`radix: ${e.message}\nusage: radix [-f FROM] [-t TO] [-w WIDTH] [-g GROUP] [-u] VALUE...\n`);
      return 2;
    }
    throw e;
  }
  const { opts, values } = parsed;
  let status = 0;
  const out: string[] = [];
  for (const text of values) {
    const value = parseValue(text, opts.from);
    if (value === null) {
      process.stderr.write(`radix: invalid value in base ${opts.from}: ${text}\n`);
      status = 1;
      continue;
    }
    out.push(format(value.negative, value.magnitude, opts) + "\n");
  }
  process.stdout.write(out.join(""));
  return status;
}

process.exitCode = main();
