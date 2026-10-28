import * as fs from "node:fs";

class UsageError extends Error {}

type Element =
  | { kind: "star" }
  | { kind: "any" }
  | { kind: "literal"; code: number }
  | { kind: "class"; negated: boolean; ranges: Array<[number, number]> };

interface Options {
  ignoreCase: boolean;
  invert: boolean;
  count: boolean;
  pattern: string;
}

function parseArgs(args: string[]): Options {
  const opts = { ignoreCase: false, invert: false, count: false };
  let pattern: string | undefined;
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (pattern !== undefined) throw new UsageError(`unexpected argument: ${arg}`);
    if (arg === "-i") opts.ignoreCase = true;
    else if (arg === "-v") opts.invert = true;
    else if (arg === "-c") opts.count = true;
    else if (arg === "--") {
      if (i + 1 >= args.length) throw new UsageError("missing PATTERN");
      pattern = args[++i];
    } else if (arg.startsWith("-")) throw new UsageError(`unknown option: ${arg}`);
    else pattern = arg;
  }
  if (pattern === undefined) throw new UsageError("missing PATTERN");
  return { ...opts, pattern };
}

function compile(pattern: string): Element[] {
  const elements: Element[] = [];
  let i = 0;
  const n = pattern.length;
  while (i < n) {
    const c = pattern[i];
    if (c === "*") {
      elements.push({ kind: "star" });
      i++;
    } else if (c === "?") {
      elements.push({ kind: "any" });
      i++;
    } else if (c === "\\") {
      if (i + 1 >= n) throw new UsageError("pattern ends with a backslash");
      elements.push({ kind: "literal", code: pattern.charCodeAt(i + 1) });
      i += 2;
    } else if (c === "[") {
      i++;
      let negated = false;
      if (pattern[i] === "!") {
        negated = true;
        i++;
      }
      // Reads one class character at i, returning its code, or throws if unterminated.
      const classChar = (): number => {
        if (i >= n) throw new UsageError("unterminated class");
        if (pattern[i] === "\\") {
          if (i + 1 >= n) throw new UsageError("unterminated class");
          i += 2;
          return pattern.charCodeAt(i - 1);
        }
        i++;
        return pattern.charCodeAt(i - 1);
      };
      const ranges: Array<[number, number]> = [];
      let first = true;
      for (;;) {
        if (i >= n) throw new UsageError("unterminated class");
        if (pattern[i] === "]" && !first) {
          i++;
          break;
        }
        first = false;
        const x = classChar();
        if (pattern[i] === "-" && i + 1 < n && pattern[i + 1] !== "]") {
          i++;
          const y = classChar();
          if (x > y) throw new UsageError("invalid range in class");
          ranges.push([x, y]);
        } else {
          ranges.push([x, x]);
        }
      }
      elements.push({ kind: "class", negated, ranges });
    } else {
      elements.push({ kind: "literal", code: pattern.charCodeAt(i) });
      i++;
    }
  }
  return elements;
}

function lower(code: number): number {
  return code >= 65 && code <= 90 ? code + 32 : code;
}

function upper(code: number): number {
  return code >= 97 && code <= 122 ? code - 32 : code;
}

function matchesOne(el: Element, code: number, ignoreCase: boolean): boolean {
  switch (el.kind) {
    case "star":
      return false;
    case "any":
      return true;
    case "literal":
      return ignoreCase ? lower(el.code) === lower(code) : el.code === code;
    case "class": {
      const inSet = (c: number) => el.ranges.some(([lo, hi]) => c >= lo && c <= hi);
      const found = ignoreCase ? inSet(lower(code)) || inSet(upper(code)) : inSet(code);
      return found !== el.negated;
    }
  }
}

/** Whole-line match using the star-restart algorithm: O(pattern × line) worst case. */
function matches(elements: Element[], line: string, ignoreCase: boolean): boolean {
  let p = 0;
  let s = 0;
  let starP = -1;
  let starS = 0;
  while (s < line.length) {
    if (p < elements.length && elements[p].kind === "star") {
      starP = p++;
      starS = s;
    } else if (p < elements.length && matchesOne(elements[p], line.charCodeAt(s), ignoreCase)) {
      p++;
      s++;
    } else if (starP >= 0) {
      p = starP + 1;
      s = ++starS;
    } else {
      return false;
    }
  }
  while (p < elements.length && elements[p].kind === "star") p++;
  return p === elements.length;
}

function readLines(): string[] {
  const text = fs.readFileSync(0, "latin1");
  if (text.length === 0) return [];
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  return lines.map((l) => (l.endsWith("\r") ? l.slice(0, -1) : l));
}

function main(): number {
  let opts: Options;
  let elements: Element[];
  try {
    opts = parseArgs(process.argv.slice(2));
    elements = compile(opts.pattern);
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`globgrep: ${e.message}\nusage: globgrep [-i] [-v] [-c] [--] PATTERN\n`);
      return 2;
    }
    throw e;
  }
  const selected = readLines().filter((line) => matches(elements, line, opts.ignoreCase) !== opts.invert);
  if (opts.count) process.stdout.write(`${selected.length}\n`);
  else process.stdout.write(selected.map((l) => l + "\n").join(""));
  return selected.length > 0 ? 0 : 1;
}

process.exitCode = main();
