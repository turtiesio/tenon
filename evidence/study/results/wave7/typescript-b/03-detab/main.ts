import * as fs from "node:fs";

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
    if (stops[i] <= stops[i - 1]) throw new UsageError(`tab stops must be strictly increasing: ${value}`);
  }
  return stops;
}

function parseArgs(args: string[]): Options {
  const opts: Options = { stops: [8], leadingOnly: false, files: [] };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-t") {
      if (i + 1 >= args.length) throw new UsageError("-t needs a value");
      opts.stops = parseStops(args[++i]);
    } else if (arg === "-i") {
      opts.leadingOnly = true;
    } else if (arg.startsWith("-")) {
      throw new UsageError(`unknown option: ${arg}`);
    } else {
      opts.files.push(arg);
    }
  }
  return opts;
}

/** Number of spaces that replace a tab at the given column. */
function tabWidth(column: number, stops: number[]): number {
  if (stops.length === 1) {
    const n = stops[0];
    return n - (column % n);
  }
  for (const stop of stops) {
    if (stop > column) return stop - column;
  }
  return 1;
}

function expand(text: string, opts: Options): string {
  const out: string[] = [];
  let column = 0;
  let leading = true; // only spaces and tabs so far on this line
  for (const ch of text) {
    if (ch === "\n") {
      out.push(ch);
      column = 0;
      leading = true;
    } else if (ch === "\t" && (leading || !opts.leadingOnly)) {
      const width = tabWidth(column, opts.stops);
      out.push(" ".repeat(width));
      column += width;
    } else {
      if (ch !== " " && ch !== "\t") leading = false;
      out.push(ch);
      column += 1;
    }
  }
  return out.join("");
}

function main(): void {
  let opts: Options;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`detab: ${e.message}\n`);
      process.exit(2);
    }
    throw e;
  }

  let failed = false;
  const chunks: Buffer[] = [];
  if (opts.files.length === 0) {
    chunks.push(fs.readFileSync(0));
  } else {
    for (const file of opts.files) {
      try {
        chunks.push(fs.readFileSync(file));
      } catch (e) {
        process.stderr.write(`detab: cannot read ${file}: ${(e as Error).message}\n`);
        failed = true;
      }
    }
  }

  process.stdout.write(expand(Buffer.concat(chunks).toString("utf8"), opts));
  process.exitCode = failed ? 1 : 0;
}

main();
