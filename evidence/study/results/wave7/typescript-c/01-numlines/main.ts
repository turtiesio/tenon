import { readFileSync } from "node:fs";

type Style = "a" | "t" | "n";
type Format = "ln" | "rn" | "rz";

interface Options {
  style: Style;
  width: number;
  sep: string;
  start: number;
  step: number;
  format: Format;
  file: string | undefined;
}

class UsageError extends Error {}

function parseArgs(argv: string[]): Options {
  const opts: Options = {
    style: "t",
    width: 6,
    sep: "\t",
    start: 1,
    step: 1,
    format: "rn",
    file: undefined,
  };
  let haveFile = false;
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith("-")) {
      if (haveFile) throw new UsageError("more than one FILE");
      haveFile = true;
      opts.file = arg;
      continue;
    }
    if (!["-b", "-w", "-s", "-v", "-i", "-f"].includes(arg)) {
      throw new UsageError(`unknown argument: ${arg}`);
    }
    if (i + 1 >= argv.length) throw new UsageError(`${arg} needs a value`);
    const value = argv[++i];
    switch (arg) {
      case "-b":
        if (value !== "a" && value !== "t" && value !== "n") {
          throw new UsageError(`bad style: ${value}`);
        }
        opts.style = value;
        break;
      case "-w":
        if (!/^[1-9][0-9]?$/.test(value) || Number(value) > 20) {
          throw new UsageError(`bad width: ${value}`);
        }
        opts.width = Number(value);
        break;
      case "-s":
        opts.sep = value;
        break;
      case "-v":
      case "-i": {
        if (!/^-?[0-9]{1,9}$/.test(value)) {
          throw new UsageError(`bad number: ${value}`);
        }
        const n = Number(value);
        if (arg === "-v") opts.start = n;
        else opts.step = n;
        break;
      }
      case "-f":
        if (value !== "ln" && value !== "rn" && value !== "rz") {
          throw new UsageError(`bad format: ${value}`);
        }
        opts.format = value;
        break;
    }
  }
  return opts;
}

function field(n: number, width: number, format: Format): string {
  const negative = n < 0;
  const digits = String(Math.abs(n));
  const text = (negative ? "-" : "") + digits;
  if (text.length >= width) return text;
  switch (format) {
    case "ln":
      return text.padEnd(width, " ");
    case "rn":
      return text.padStart(width, " ");
    case "rz":
      return (negative ? "-" : "") + digits.padStart(width - (negative ? 1 : 0), "0");
  }
}

function main(): number {
  let opts: Options;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`numlines: ${e.message}\n`);
      return 2;
    }
    throw e;
  }

  let input: Buffer;
  try {
    input = readFileSync(opts.file ?? 0);
  } catch (e) {
    process.stderr.write(`numlines: cannot read ${opts.file ?? "stdin"}: ${(e as Error).message}\n`);
    return 1;
  }

  // Work on a byte-preserving (latin1) view so lines are copied byte for byte;
  // the separator is the only text that needs real UTF-8 encoding.
  const text = input.toString("latin1");
  const sep = Buffer.from(opts.sep, "utf8").toString("latin1");
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();

  const out: string[] = [];
  let n = opts.start;
  for (const line of lines) {
    const numbered = opts.style === "a" || (opts.style === "t" && line.length > 0);
    if (numbered) {
      out.push(field(n, opts.width, opts.format), sep, line, "\n");
      n += opts.step;
    } else {
      out.push(line, "\n");
    }
  }
  process.stdout.write(Buffer.from(out.join(""), "latin1"));
  return 0;
}

process.exitCode = main();
