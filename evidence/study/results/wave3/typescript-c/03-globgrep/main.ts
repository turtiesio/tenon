import { readFileSync } from "node:fs";

class UsageError extends Error {}

interface Options {
  ignoreCase: boolean;
  invert: boolean;
  count: boolean;
  pattern: string;
}

type Range = readonly [number, number];

type Element =
  | { kind: "star" }
  | { kind: "any" }
  | { kind: "char"; code: number }
  | { kind: "class"; negated: boolean; ranges: Range[] };

function parseArgs(args: string[]): Options {
  let ignoreCase = false;
  let invert = false;
  let count = false;
  let pattern: string | null = null;
  let optionsEnded = false;
  for (const arg of args) {
    if (pattern !== null) throw new UsageError(`unexpected argument: ${arg}`);
    if (optionsEnded) {
      pattern = arg;
    } else if (arg === "--") {
      optionsEnded = true;
    } else if (arg === "-i") {
      ignoreCase = true;
    } else if (arg === "-v") {
      invert = true;
    } else if (arg === "-c") {
      count = true;
    } else if (arg.startsWith("-")) {
      throw new UsageError(`unknown option: ${arg}`);
    } else {
      pattern = arg;
    }
  }
  if (pattern === null) throw new UsageError("missing PATTERN");
  return { ignoreCase, invert, count, pattern };
}

function parsePattern(source: string, ignoreCase: boolean): Element[] {
  const pat = Array.from(Buffer.from(source, "latin1"));
  const elements: Element[] = [];
  let i = 0;

  // Reads one class character (plain or backslash-escaped).
  const classChar = (): number => {
    if (i >= pat.length) throw new UsageError("unterminated class");
    if (pat[i] === 0x5c) {
      if (i + 1 >= pat.length) throw new UsageError("unterminated escape");
      i += 2;
      return pat[i - 1];
    }
    return pat[i++];
  };

  while (i < pat.length) {
    const c = pat[i];
    if (c === 0x2a) {
      // Consecutive stars are equivalent to one.
      if (elements.length === 0 || elements[elements.length - 1].kind !== "star") {
        elements.push({ kind: "star" });
      }
      i++;
    } else if (c === 0x3f) {
      elements.push({ kind: "any" });
      i++;
    } else if (c === 0x5c) {
      if (i + 1 >= pat.length) throw new UsageError("trailing backslash");
      elements.push({ kind: "char", code: fold(pat[i + 1], ignoreCase) });
      i += 2;
    } else if (c === 0x5b) {
      i++;
      let negated = false;
      if (pat[i] === 0x21) {
        negated = true;
        i++;
      }
      const ranges: Range[] = [];
      let first = true;
      for (;;) {
        if (i >= pat.length) throw new UsageError("unterminated class");
        if (pat[i] === 0x5d && !first) {
          i++;
          break;
        }
        first = false;
        const lo = classChar();
        if (pat[i] === 0x2d && i + 1 < pat.length && pat[i + 1] !== 0x5d) {
          i++;
          const hi = classChar();
          if (lo > hi) throw new UsageError("reversed range in class");
          ranges.push([lo, hi]);
        } else {
          ranges.push([lo, lo]);
        }
      }
      elements.push({ kind: "class", negated, ranges });
    } else {
      elements.push({ kind: "char", code: fold(c, ignoreCase) });
      i++;
    }
  }
  return elements;
}

function fold(code: number, ignoreCase: boolean): number {
  return ignoreCase && code >= 0x41 && code <= 0x5a ? code + 0x20 : code;
}

function inRanges(ranges: Range[], code: number): boolean {
  return ranges.some(([lo, hi]) => code >= lo && code <= hi);
}

function classMatches(
  element: { negated: boolean; ranges: Range[] },
  code: number,
  ignoreCase: boolean,
): boolean {
  let found = inRanges(element.ranges, code);
  if (!found && ignoreCase) {
    if (code >= 0x41 && code <= 0x5a) found = inRanges(element.ranges, code + 0x20);
    else if (code >= 0x61 && code <= 0x7a) found = inRanges(element.ranges, code - 0x20);
  }
  return found !== element.negated;
}

// Simulates the pattern as an NFA, so time is O(pattern * line).
function matches(elements: Element[], line: Buffer, ignoreCase: boolean): boolean {
  const n = elements.length;
  let active = new Uint8Array(n + 1);
  let next = new Uint8Array(n + 1);

  const closure = (states: Uint8Array) => {
    for (let s = 0; s < n; s++) {
      if (states[s] && elements[s].kind === "star") states[s + 1] = 1;
    }
  };

  active[0] = 1;
  closure(active);
  for (const code of line) {
    next.fill(0);
    for (let s = 0; s < n; s++) {
      if (!active[s]) continue;
      const e = elements[s];
      switch (e.kind) {
        case "star":
          next[s] = 1;
          break;
        case "any":
          next[s + 1] = 1;
          break;
        case "char":
          if (e.code === fold(code, ignoreCase)) next[s + 1] = 1;
          break;
        case "class":
          if (classMatches(e, code, ignoreCase)) next[s + 1] = 1;
          break;
      }
    }
    closure(next);
    [active, next] = [next, active];
  }
  return active[n] === 1;
}

function splitLines(input: Buffer): Buffer[] {
  const lines: Buffer[] = [];
  let start = 0;
  while (start < input.length) {
    let end = input.indexOf(0x0a, start);
    const hasNewline = end >= 0;
    if (!hasNewline) end = input.length;
    let lineEnd = end;
    if (lineEnd > start && input[lineEnd - 1] === 0x0d) lineEnd--;
    lines.push(input.subarray(start, lineEnd));
    start = end + 1;
  }
  return lines;
}

function main(): number {
  let options: Options;
  let elements: Element[];
  try {
    options = parseArgs(process.argv.slice(2));
    elements = parsePattern(options.pattern, options.ignoreCase);
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`globgrep: ${e.message}\n`);
      return 2;
    }
    throw e;
  }
  const selected = splitLines(readFileSync(0)).filter(
    (line) => matches(elements, line, options.ignoreCase) !== options.invert,
  );
  if (options.count) {
    process.stdout.write(`${selected.length}\n`);
  } else if (selected.length > 0) {
    const nl = Buffer.from("\n");
    process.stdout.write(Buffer.concat(selected.flatMap((l) => [l, nl])));
  }
  return selected.length > 0 ? 0 : 1;
}

process.exitCode = main();
