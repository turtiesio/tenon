import { readFileSync } from "node:fs";

const BINARY_UNITS = ["KiB", "MiB", "GiB", "TiB", "PiB"];
const DECIMAL_UNITS = ["kB", "MB", "GB", "TB", "PB"];
const SIZE_PATTERN = /^[0-9]{1,16}$/;

class UsageError extends Error {}

interface Options {
  decimal: boolean;
  places: number;
  sizes: string[];
}

function parseArgs(args: string[]): Options {
  const opts: Options = { decimal: false, places: 1, sizes: [] };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-s") {
      opts.decimal = true;
    } else if (arg === "-p") {
      const value = args[++i];
      if (value !== "0" && value !== "1" && value !== "2") {
        throw new UsageError("-p needs 0, 1 or 2");
      }
      opts.places = Number(value);
    } else if (SIZE_PATTERN.test(arg)) {
      opts.sizes.push(arg);
    } else {
      throw new UsageError(`bad argument '${arg}'`);
    }
  }
  return opts;
}

function format(text: string, opts: Options): string {
  const v = BigInt(text);
  const base = opts.decimal ? 1000n : 1024n;
  if (v < base) return `${v} B`;

  const units = opts.decimal ? DECIMAL_UNITS : BINARY_UNITS;
  const scale = 10n ** BigInt(opts.places);
  let k = 1;
  while (k < 5 && v >= base ** BigInt(k + 1)) k++;

  for (;;) {
    const unit = base ** BigInt(k);
    const r = (2n * v * scale + unit) / (2n * unit);
    if (r >= base * scale && k < 5) {
      k++;
      continue;
    }
    let out = `${r / scale}`;
    if (opts.places > 0) out += "." + String(r % scale).padStart(opts.places, "0");
    return `${out} ${units[k - 1]}`;
  }
}

function readStdinLines(): string[] {
  let text: string;
  try {
    text = readFileSync(0, "latin1");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "EOF") return [];
    throw e;
  }
  if (text === "") return [];
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  return lines.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line));
}

function main(): number {
  let opts: Options;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (!(e instanceof UsageError)) throw e;
    process.stderr.write(`hsize: ${e.message}\nusage: hsize [-s] [-p N] [SIZE...]\n`);
    return 2;
  }

  let status = 0;
  const out: string[] = [];
  if (opts.sizes.length > 0) {
    for (const size of opts.sizes) out.push(format(size, opts));
  } else {
    for (const line of readStdinLines()) {
      if (SIZE_PATTERN.test(line)) {
        out.push(format(line, opts));
      } else {
        out.push("?");
        status = 1;
      }
    }
  }
  if (out.length > 0) process.stdout.write(out.join("\n") + "\n");
  return status;
}

process.exitCode = main();
