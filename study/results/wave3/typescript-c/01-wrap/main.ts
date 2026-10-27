import { readFileSync } from "node:fs";

class UsageError extends Error {}

interface Options {
  width: number;
  indent: number;
  justify: boolean;
}

function parseNumber(text: string, what: string): number {
  if (!/^[0-9]{1,4}$/.test(text)) {
    throw new UsageError(`bad ${what}: ${text}`);
  }
  return Number(text);
}

function parseArgs(args: string[]): Options {
  let width: number | undefined;
  let indent: number | undefined;
  let justify = false;
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-w" || arg === "-i") {
      const name = arg === "-w" ? "width" : "indent";
      if ((arg === "-w" ? width : indent) !== undefined) {
        throw new UsageError(`${arg} given more than once`);
      }
      if (i + 1 >= args.length) {
        throw new UsageError(`${arg} needs an argument`);
      }
      const value = parseNumber(args[++i], name);
      if (arg === "-w") {
        if (value < 1 || value > 1000) throw new UsageError("width out of range");
        width = value;
      } else {
        indent = value;
      }
    } else if (arg === "-j") {
      if (justify) throw new UsageError("-j given more than once");
      justify = true;
    } else {
      throw new UsageError(`unknown argument: ${arg}`);
    }
  }
  const options = { width: width ?? 72, indent: indent ?? 0, justify };
  if (options.indent >= options.width) {
    throw new UsageError("indent must be smaller than width");
  }
  return options;
}

function readLines(): string[] | null {
  const text = readFileSync(0).toString("latin1");
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  const cleaned = lines.map((l) => (l.endsWith("\r") ? l.slice(0, -1) : l));
  for (const line of cleaned) {
    if (!/^[\x20-\x7e]*$/.test(line)) return null;
  }
  return cleaned;
}

function paragraphs(lines: string[]): string[][] {
  const result: string[][] = [];
  let current: string[] | null = null;
  for (const line of lines) {
    const words = line.split(" ").filter((w) => w !== "");
    if (words.length === 0) {
      current = null;
    } else {
      if (current === null) {
        current = [];
        result.push(current);
      }
      current.push(...words);
    }
  }
  return result;
}

function fill(words: string[], { width, indent }: Options): string[][] {
  const lines: string[][] = [];
  let current: string[] = [];
  let length = 0;
  for (const word of words) {
    if (current.length === 0) {
      current = [word];
      length = (lines.length === 0 ? indent : 0) + word.length;
    } else if (length + 1 + word.length <= width) {
      current.push(word);
      length += 1 + word.length;
    } else {
      lines.push(current);
      current = [word];
      length = word.length;
    }
  }
  if (current.length > 0) lines.push(current);
  return lines;
}

function render(words: string[], lead: number, target: number | null): string {
  const prefix = " ".repeat(lead);
  if (target === null || words.length < 2) return prefix + words.join(" ");
  const letters = words.reduce((n, w) => n + w.length, 0);
  const space = target - lead - letters;
  const gaps = words.length - 1;
  const each = Math.floor(space / gaps);
  const extra = space % gaps;
  let out = prefix;
  words.forEach((w, i) => {
    out += w;
    if (i < gaps) out += " ".repeat(each + (i < extra ? 1 : 0));
  });
  return out;
}

function main(): number {
  let options: Options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`wrap: ${e.message}\n`);
      return 2;
    }
    throw e;
  }
  const lines = readLines();
  if (lines === null) {
    process.stderr.write("wrap: invalid character in input\n");
    return 1;
  }
  const blocks: string[] = [];
  for (const para of paragraphs(lines)) {
    const filled = fill(para, options);
    const out = filled.map((words, i) =>
      render(
        words,
        i === 0 ? options.indent : 0,
        options.justify && i < filled.length - 1 ? options.width : null,
      ),
    );
    blocks.push(out.join("\n") + "\n");
  }
  process.stdout.write(blocks.join("\n"));
  return 0;
}

process.exitCode = main();
