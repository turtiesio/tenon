import * as fs from "node:fs";

type Style = "a" | "t" | "n";
type Format = "ln" | "rn" | "rz";

interface Options {
  style: Style;
  width: number;
  sep: string;
  start: number;
  step: number;
  format: Format;
  file: string | null;
}

class UsageError extends Error {}

function parseArgs(args: string[]): Options {
  const opts: Options = { style: "t", width: 6, sep: "\t", start: 1, step: 1, format: "rn", file: null };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (!arg.startsWith("-")) {
      if (opts.file !== null) throw new UsageError("only one FILE may be given");
      opts.file = arg;
      continue;
    }
    if (!["-b", "-w", "-s", "-v", "-i", "-f"].includes(arg)) {
      throw new UsageError(`unknown option: ${arg}`);
    }
    if (i + 1 >= args.length) throw new UsageError(`option ${arg} needs a value`);
    const value = args[++i];
    switch (arg) {
      case "-b":
        if (value !== "a" && value !== "t" && value !== "n") throw new UsageError(`bad style: ${value}`);
        opts.style = value;
        break;
      case "-w":
        if (!/^[1-9][0-9]?$/.test(value) || Number(value) > 20) throw new UsageError(`bad width: ${value}`);
        opts.width = Number(value);
        break;
      case "-s":
        opts.sep = value;
        break;
      case "-v":
        if (!/^-?[0-9]{1,9}$/.test(value)) throw new UsageError(`bad start: ${value}`);
        opts.start = Number(value);
        break;
      case "-i":
        if (!/^-?[0-9]{1,9}$/.test(value)) throw new UsageError(`bad step: ${value}`);
        opts.step = Number(value);
        break;
      case "-f":
        if (value !== "ln" && value !== "rn" && value !== "rz") throw new UsageError(`bad format: ${value}`);
        opts.format = value;
        break;
    }
  }
  return opts;
}

function formatNumber(n: number, width: number, format: Format): string {
  const digits = String(Math.abs(n));
  const sign = n < 0 ? "-" : "";
  switch (format) {
    case "rn":
      return (sign + digits).padStart(width, " ");
    case "ln":
      return (sign + digits).padEnd(width, " ");
    case "rz":
      return sign + digits.padStart(width - sign.length, "0");
  }
}

function splitLines(data: Buffer): Buffer[] {
  const lines: Buffer[] = [];
  let begin = 0;
  while (begin < data.length) {
    const nl = data.indexOf(0x0a, begin);
    if (nl === -1) {
      lines.push(data.subarray(begin));
      break;
    }
    lines.push(data.subarray(begin, nl));
    begin = nl + 1;
  }
  return lines;
}

function main(): void {
  let opts: Options;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`numlines: ${e.message}\n`);
      process.exit(2);
    }
    throw e;
  }

  let data: Buffer;
  try {
    data = fs.readFileSync(opts.file ?? 0);
  } catch (e) {
    process.stderr.write(`numlines: cannot read ${opts.file ?? "stdin"}: ${(e as Error).message}\n`);
    process.exit(1);
  }

  const sep = Buffer.from(opts.sep, "utf8");
  const newline = Buffer.from("\n");
  const out: Buffer[] = [];
  let n = opts.start;
  for (const line of splitLines(data)) {
    const numbered = opts.style === "a" || (opts.style === "t" && line.length > 0);
    if (numbered) {
      out.push(Buffer.from(formatNumber(n, opts.width, opts.format), "utf8"), sep);
      n += opts.step;
    }
    out.push(line, newline);
  }
  process.stdout.write(Buffer.concat(out));
}

main();
