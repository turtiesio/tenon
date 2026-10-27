import { readFileSync } from "node:fs";

class UsageError extends Error {}

type Options = { sep: string | null; outSep: string; rightCols: Set<number> };

function parseArgs(argv: string[]): Options {
  const opts: Options = { sep: null, outSep: "  ", rightCols: new Set() };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg !== "-s" && arg !== "-o" && arg !== "-r") throw new UsageError(`unexpected argument ${arg}`);
    if (i + 1 >= argv.length) throw new UsageError(`option ${arg} requires a value`);
    const value = argv[++i];
    if (arg === "-s") {
      if ([...value].length !== 1) throw new UsageError("-s needs exactly one character");
      opts.sep = value;
    } else if (arg === "-o") {
      opts.outSep = value;
    } else {
      if (!/^[1-9][0-9]{0,2}(,[1-9][0-9]{0,2})*$/.test(value)) throw new UsageError(`bad column list ${value}`);
      opts.rightCols = new Set(value.split(",").map(Number));
    }
  }
  return opts;
}

function readLines(): string[] {
  const text = readFileSync(0, "utf8");
  if (text === "") return [];
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  return lines.map((l) => (l.endsWith("\r") ? l.slice(0, -1) : l));
}

function splitFields(line: string, sep: string | null): string[] {
  if (sep === null) return line.split(/[ \t]+/).filter((f) => f !== "");
  if (line === "") return [];
  return line.split(sep);
}

const codePoints = (s: string): number => [...s].length;

function main(argv: string[]): void {
  const opts = parseArgs(argv);
  const rows = readLines().map((l) => splitFields(l, opts.sep));

  const widths: number[] = [];
  for (const row of rows) {
    row.forEach((field, k) => {
      widths[k] = Math.max(widths[k] ?? 0, codePoints(field));
    });
  }

  const out: string[] = [];
  for (const row of rows) {
    const cells = row.map((field, k) => {
      const right = opts.rightCols.has(k + 1);
      const pad = " ".repeat(widths[k] - codePoints(field));
      if (right) return pad + field;
      return k === row.length - 1 ? field : field + pad;
    });
    out.push(cells.join(opts.outSep) + "\n");
  }
  process.stdout.write(out.join(""));
}

try {
  main(process.argv.slice(2));
} catch (e) {
  if (e instanceof UsageError) {
    process.stderr.write(`colalign: ${e.message}\nusage: colalign [-s CHAR] [-o OUTSEP] [-r LIST]\n`);
    process.exit(2);
  }
  throw e;
}
