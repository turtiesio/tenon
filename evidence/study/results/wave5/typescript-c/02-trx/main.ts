import { readFileSync } from "node:fs";

class UsageError extends Error {}

type Token = { ch: string; escaped: boolean };

const ESCAPES: Record<string, string> = { n: "\n", t: "\t", "\\": "\\", "-": "-" };

function tokenize(arg: string): Token[] {
  const tokens: Token[] = [];
  for (let i = 0; i < arg.length; i++) {
    const c = arg[i];
    if (c !== "\\") {
      tokens.push({ ch: c, escaped: false });
      continue;
    }
    const next = arg[++i];
    if (next === undefined || !(next in ESCAPES)) {
      throw new UsageError(`bad escape in set: ${arg}`);
    }
    tokens.push({ ch: ESCAPES[next], escaped: true });
  }
  return tokens;
}

function parseSet(arg: string): string[] {
  const tokens = tokenize(arg);
  const out: string[] = [];
  let i = 0;
  while (i < tokens.length) {
    const x = tokens[i];
    const dash = tokens[i + 1];
    const y = tokens[i + 2];
    if (dash !== undefined && !dash.escaped && dash.ch === "-" && y !== undefined) {
      const lo = x.ch.charCodeAt(0);
      const hi = y.ch.charCodeAt(0);
      if (lo > hi) throw new UsageError(`reversed range in set: ${arg}`);
      for (let c = lo; c <= hi; c++) out.push(String.fromCharCode(c));
      i += 3;
    } else {
      out.push(x.ch);
      i += 1;
    }
  }
  return out;
}

function squeeze(text: string, set: Set<string>): string {
  const out: string[] = [];
  let prev: string | null = null;
  for (const c of text) {
    if (c === prev && set.has(c)) continue;
    out.push(c);
    prev = c;
  }
  return out.join("");
}

function run(args: string[]): string | null {
  let del = false;
  let sq = false;
  let i = 0;
  for (; i < args.length; i++) {
    const a = args[i];
    if (a === "-d") del = true;
    else if (a === "-s") sq = true;
    else if (a === "--") { i++; break; }
    else if (a.length >= 2 && a.startsWith("-")) throw new UsageError(`unknown option: ${a}`);
    else break;
  }
  const sets = args.slice(i);

  const expected = del && sq ? 2 : del ? 1 : sq ? [1, 2] : 2;
  const ok = Array.isArray(expected) ? expected.includes(sets.length) : sets.length === expected;
  if (!ok) throw new UsageError("wrong number of sets");

  const set1 = parseSet(sets[0]);
  const set2 = sets.length > 1 ? parseSet(sets[1]) : [];
  const translating = !del && sets.length === 2;
  if (translating && set2.length === 0) throw new UsageError("empty SET2");

  const input = readFileSync(0, "latin1");

  let text: string;
  if (del) {
    const gone = new Set(set1);
    text = Array.from(input).filter((c) => !gone.has(c)).join("");
  } else if (translating) {
    const map = new Map<string, string>();
    set1.forEach((c, idx) => map.set(c, set2[Math.min(idx, set2.length - 1)]));
    text = Array.from(input, (c) => map.get(c) ?? c).join("");
  } else {
    text = input;
  }

  if (sq) {
    const squeezeSet = new Set(sets.length === 2 ? set2 : set1);
    text = squeeze(text, squeezeSet);
  }
  return text;
}

try {
  const text = run(process.argv.slice(2));
  process.stdout.write(Buffer.from(text ?? "", "latin1"));
} catch (e) {
  if (!(e instanceof UsageError)) throw e;
  process.stderr.write(`trx: ${e.message}\nusage: trx [-d] [-s] [--] SET1 [SET2]\n`);
  process.exit(2);
}
