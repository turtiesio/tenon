import { readFileSync } from "node:fs";

const LIST = /^[1-9][0-9]{0,2}(,[1-9][0-9]{0,2})*$/;

interface Options {
  sep: string | null;
  outSep: string;
  right: Set<number>;
}

function parseArgs(args: string[]): Options | string {
  const opts: Options = { sep: null, outSep: "  ", right: new Set() };
  for (let i = 0; i < args.length; i++) {
    const flag = args[i];
    if (flag !== "-s" && flag !== "-o" && flag !== "-r") return `unexpected argument: ${flag}`;
    if (i + 1 >= args.length) return `${flag} needs a value`;
    const value = args[++i];
    if (flag === "-s") {
      if (Array.from(value).length !== 1) return "-s needs exactly one character";
      opts.sep = value;
    } else if (flag === "-o") {
      opts.outSep = value;
    } else {
      if (!LIST.test(value)) return `bad column list: ${value}`;
      opts.right = new Set(value.split(",").map(Number));
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
  return line === "" ? [] : line.split(sep);
}

const len = (s: string): number => Array.from(s).length;

function main(): void {
  const opts = parseArgs(process.argv.slice(2));
  if (typeof opts === "string") {
    process.stderr.write(`colalign: ${opts}\nusage: colalign [-s CHAR] [-o OUTSEP] [-r LIST]\n`);
    process.exit(2);
  }

  const rows = readLines().map((l) => splitFields(l, opts.sep));
  const widths: number[] = [];
  for (const row of rows) {
    row.forEach((f, k) => {
      widths[k] = Math.max(widths[k] ?? 0, len(f));
    });
  }

  const out = rows.map((row) =>
    row
      .map((f, k) => {
        const pad = " ".repeat(widths[k] - len(f));
        if (opts.right.has(k + 1)) return pad + f;
        return k === row.length - 1 ? f : f + pad;
      })
      .join(opts.outSep),
  );
  process.stdout.write(out.map((l) => l + "\n").join(""));
}

main();
