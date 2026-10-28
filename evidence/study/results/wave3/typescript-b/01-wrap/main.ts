import * as fs from "node:fs";

class UsageError extends Error {}

interface Options {
  width: number;
  indent: number;
  justify: boolean;
}

function parseNumber(text: string, name: string): number {
  if (!/^[0-9]{1,4}$/.test(text)) throw new UsageError(`invalid ${name}: ${text}`);
  return Number(text);
}

function parseArgs(args: string[]): Options {
  let width: number | undefined;
  let indent: number | undefined;
  let justify = false;
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-w" || arg === "-i") {
      if (i + 1 >= args.length) throw new UsageError(`${arg} requires a value`);
      const value = args[++i];
      if (arg === "-w") {
        if (width !== undefined) throw new UsageError("-w given more than once");
        width = parseNumber(value, "width");
        if (width < 1 || width > 1000) throw new UsageError("width must be 1..1000");
      } else {
        if (indent !== undefined) throw new UsageError("-i given more than once");
        indent = parseNumber(value, "indent");
      }
    } else if (arg === "-j") {
      if (justify) throw new UsageError("-j given more than once");
      justify = true;
    } else {
      throw new UsageError(`unexpected argument: ${arg}`);
    }
  }
  const opts = { width: width ?? 72, indent: indent ?? 0, justify };
  if (opts.indent >= opts.width) throw new UsageError("indent must be smaller than width");
  return opts;
}

function readLines(): string[] {
  const data = fs.readFileSync(0);
  const lines: string[] = [];
  let start = 0;
  for (let i = 0; i <= data.length; i++) {
    if (i === data.length || data[i] === 0x0a) {
      if (i === data.length && start === data.length) break;
      let end = i;
      if (end > start && data[end - 1] === 0x0d) end--;
      for (let k = start; k < end; k++) {
        const b = data[k];
        if (b < 0x20 || b > 0x7e) throw new Error(`invalid byte 0x${b.toString(16)} on line ${lines.length + 1}`);
      }
      lines.push(data.toString("latin1", start, end));
      start = i + 1;
    }
  }
  return lines;
}

function paragraphs(lines: string[]): string[][] {
  const result: string[][] = [];
  let current: string[] = [];
  for (const line of lines) {
    const words = line.split(" ").filter((w) => w.length > 0);
    if (words.length === 0) {
      if (current.length > 0) result.push(current);
      current = [];
    } else {
      current.push(...words);
    }
  }
  if (current.length > 0) result.push(current);
  return result;
}

function fill(words: string[], opts: Options): string[] {
  const lines: string[][] = [];
  let i = 0;
  while (i < words.length) {
    const indent = lines.length === 0 ? opts.indent : 0;
    const line = [words[i]];
    let length = indent + words[i].length;
    i++;
    while (i < words.length && length + 1 + words[i].length <= opts.width) {
      length += 1 + words[i].length;
      line.push(words[i]);
      i++;
    }
    lines.push(line);
  }
  return lines.map((line, n) => {
    const indent = n === 0 ? opts.indent : 0;
    const prefix = " ".repeat(indent);
    const isLast = n === lines.length - 1;
    if (!opts.justify || isLast || line.length < 2) return prefix + line.join(" ");
    const letters = line.reduce((sum, w) => sum + w.length, 0);
    const spaces = opts.width - indent - letters;
    const gaps = line.length - 1;
    const base = Math.floor(spaces / gaps);
    const extra = spaces % gaps;
    let out = prefix + line[0];
    for (let g = 0; g < gaps; g++) {
      out += " ".repeat(base + (g < extra ? 1 : 0)) + line[g + 1];
    }
    return out;
  });
}

function main(): number {
  let opts: Options;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`wrap: ${e.message}\nusage: wrap [-w WIDTH] [-i INDENT] [-j]\n`);
      return 2;
    }
    throw e;
  }
  let lines: string[];
  try {
    lines = readLines();
  } catch (e) {
    process.stderr.write(`wrap: ${(e as Error).message}\n`);
    return 1;
  }
  const output = paragraphs(lines).map((p) => fill(p, opts).join("\n") + "\n");
  process.stdout.write(output.join("\n"));
  return 0;
}

process.exitCode = main();
