import * as fs from "node:fs";

interface Options {
  count: boolean;
  dupOnly: boolean;
  uniqOnly: boolean;
  ignoreCase: boolean;
  fields: number;
  chars: number;
}

interface Group {
  line: string;
  size: number;
}

function parseArgs(args: string[]): Options | string {
  const opts: Options = {
    count: false,
    dupOnly: false,
    uniqOnly: false,
    ignoreCase: false,
    fields: 0,
    chars: 0,
  };
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "-c": opts.count = true; break;
      case "-d": opts.dupOnly = true; break;
      case "-u": opts.uniqOnly = true; break;
      case "-i": opts.ignoreCase = true; break;
      case "-f":
      case "-s": {
        const flag = args[i];
        if (i + 1 >= args.length) return `${flag} needs a value`;
        const value = args[++i];
        if (!/^[0-9]{1,4}$/.test(value)) return `bad value for ${flag}: ${value}`;
        if (flag === "-f") opts.fields = Number(value);
        else opts.chars = Number(value);
        break;
      }
      default:
        return `unexpected argument: ${args[i]}`;
    }
  }
  return opts;
}

function isBlank(ch: string): boolean {
  return ch === " " || ch === "\t";
}

function splitLines(text: string): string[] {
  if (text === "") return [];
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  return lines.map((l) => (l.endsWith("\r") ? l.slice(0, -1) : l));
}

function keyOf(line: string, opts: Options): string {
  let pos = 0;
  for (let n = 0; n < opts.fields; n++) {
    while (pos < line.length && isBlank(line[pos])) pos++;
    while (pos < line.length && !isBlank(line[pos])) pos++;
  }
  let key = line.slice(Math.min(pos + opts.chars, line.length));
  if (opts.ignoreCase) key = key.replace(/[A-Z]/g, (c) => c.toLowerCase());
  return key;
}

function main(): number {
  const parsed = parseArgs(process.argv.slice(2));
  if (typeof parsed === "string") {
    console.error(`uniqx: ${parsed}`);
    return 2;
  }
  const opts = parsed;

  let text: string;
  try {
    text = fs.readFileSync(0, "latin1");
  } catch {
    text = "";
  }

  const groups: Group[] = [];
  let currentKey: string | null = null;
  for (const line of splitLines(text)) {
    const key = keyOf(line, opts);
    if (currentKey !== null && key === currentKey) {
      groups[groups.length - 1].size++;
    } else {
      groups.push({ line, size: 1 });
      currentKey = key;
    }
  }

  const out: string[] = [];
  for (const g of groups) {
    if (opts.dupOnly && g.size < 2) continue;
    if (opts.uniqOnly && g.size !== 1) continue;
    out.push(opts.count ? `${String(g.size).padStart(7)} ${g.line}\n` : `${g.line}\n`);
  }
  process.stdout.write(out.join(""), "latin1");
  return 0;
}

process.exitCode = main();
