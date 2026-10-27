import * as fs from "node:fs";

interface Options {
  count: boolean;
  onlyRepeated: boolean;
  onlyUnique: boolean;
  ignoreCase: boolean;
  skipFields: number;
  skipChars: number;
}

function usage(msg: string): never {
  process.stderr.write(`uniqx: ${msg}\nusage: uniqx [-c] [-d] [-u] [-i] [-f N] [-s N]\n`);
  process.exit(2);
}

function parseArgs(args: string[]): Options {
  const opts: Options = {
    count: false,
    onlyRepeated: false,
    onlyUnique: false,
    ignoreCase: false,
    skipFields: 0,
    skipChars: 0,
  };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    switch (arg) {
      case "-c": opts.count = true; break;
      case "-d": opts.onlyRepeated = true; break;
      case "-u": opts.onlyUnique = true; break;
      case "-i": opts.ignoreCase = true; break;
      case "-f":
      case "-s": {
        if (i + 1 >= args.length) usage(`option ${arg} requires a value`);
        const value = args[++i];
        if (!/^[0-9]{1,4}$/.test(value)) usage(`invalid value for ${arg}: ${value}`);
        if (arg === "-f") opts.skipFields = Number(value);
        else opts.skipChars = Number(value);
        break;
      }
      default:
        usage(`unexpected argument: ${arg}`);
    }
  }
  return opts;
}

function splitLines(text: string): string[] {
  if (text === "") return [];
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  return lines.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line));
}

const isBlank = (ch: string): boolean => ch === " " || ch === "\t";

function keyOf(line: string, opts: Options): string {
  let pos = 0;
  for (let f = 0; f < opts.skipFields; f++) {
    while (pos < line.length && isBlank(line[pos])) pos++;
    while (pos < line.length && !isBlank(line[pos])) pos++;
  }
  let key = line.slice(pos + opts.skipChars);
  if (opts.ignoreCase) key = key.replace(/[A-Z]/g, (c) => c.toLowerCase());
  return key;
}

function main(): void {
  const opts = parseArgs(process.argv.slice(2));
  const lines = splitLines(fs.readFileSync(0, "latin1"));
  const out: string[] = [];

  const emit = (line: string, size: number): void => {
    if (opts.onlyRepeated && size < 2) return;
    if (opts.onlyUnique && size !== 1) return;
    out.push(opts.count ? `${String(size).padStart(7)} ${line}\n` : `${line}\n`);
  };

  let i = 0;
  while (i < lines.length) {
    const key = keyOf(lines[i], opts);
    let j = i + 1;
    while (j < lines.length && keyOf(lines[j], opts) === key) j++;
    emit(lines[i], j - i);
    i = j;
  }
  process.stdout.write(out.join(""), "latin1");
}

main();
