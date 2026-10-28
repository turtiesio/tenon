import { readFileSync } from "node:fs";

interface Options {
  stops: number[];
  leadingOnly: boolean;
  files: string[];
}

class UsageError extends Error {}

function parseStops(value: string): number[] {
  if (!/^[1-9][0-9]{0,3}(,[1-9][0-9]{0,3})*$/.test(value)) {
    throw new UsageError(`bad tab stops: ${value}`);
  }
  const stops = value.split(",").map(Number);
  for (let i = 1; i < stops.length; i++) {
    if (stops[i] <= stops[i - 1]) throw new UsageError(`tab stops must increase: ${value}`);
  }
  return stops;
}

function parseArgs(argv: string[]): Options {
  const opts: Options = { stops: [8], leadingOnly: false, files: [] };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "-t") {
      if (i + 1 >= argv.length) throw new UsageError("-t needs a value");
      opts.stops = parseStops(argv[++i]);
    } else if (arg === "-i") {
      opts.leadingOnly = true;
    } else if (arg.startsWith("-")) {
      throw new UsageError(`unknown argument: ${arg}`);
    } else {
      opts.files.push(arg);
    }
  }
  return opts;
}

// Number of spaces a tab at `column` expands to.
function tabWidth(column: number, stops: number[]): number {
  if (stops.length === 1) return stops[0] - (column % stops[0]);
  const next = stops.find((s) => s > column);
  return next === undefined ? 1 : next - column;
}

function expand(text: string, opts: Options): string {
  const out: string[] = [];
  let column = 0;
  let leading = true; // only spaces and tabs seen so far on this line
  for (const ch of text) {
    if (ch === "\n") {
      out.push(ch);
      column = 0;
      leading = true;
    } else if (ch === "\t") {
      if (opts.leadingOnly && !leading) {
        out.push(ch);
        column += 1;
      } else {
        const width = tabWidth(column, opts.stops);
        out.push(" ".repeat(width));
        column += width;
      }
    } else {
      out.push(ch);
      column += 1;
      if (ch !== " ") leading = false;
    }
  }
  return out.join("");
}

function main(): number {
  let opts: Options;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`detab: ${e.message}\n`);
      return 2;
    }
    throw e;
  }

  let status = 0;
  const chunks: Buffer[] = [];
  if (opts.files.length === 0) {
    chunks.push(readFileSync(0));
  } else {
    for (const file of opts.files) {
      try {
        chunks.push(readFileSync(file));
      } catch (e) {
        process.stderr.write(`detab: cannot read ${file}: ${(e as Error).message}\n`);
        status = 1;
      }
    }
  }
  const text = Buffer.concat(chunks).toString("utf8");
  process.stdout.write(expand(text, opts));
  return status;
}

process.exitCode = main();
