import { readFileSync } from "node:fs";

class UsageError extends Error {}

type Token = { ch: string; escapedDash: boolean };

function parseSet(arg: string): string[] {
  const tokens: Token[] = [];
  for (let i = 0; i < arg.length; i++) {
    const c = arg[i];
    if (c !== "\\") {
      tokens.push({ ch: c, escapedDash: false });
      continue;
    }
    const next = arg[++i];
    switch (next) {
      case "n": tokens.push({ ch: "\n", escapedDash: false }); break;
      case "t": tokens.push({ ch: "\t", escapedDash: false }); break;
      case "\\": tokens.push({ ch: "\\", escapedDash: false }); break;
      case "-": tokens.push({ ch: "-", escapedDash: true }); break;
      default:
        throw new UsageError(next === undefined ? "trailing backslash in set" : `bad escape \\${next}`);
    }
  }

  const chars: string[] = [];
  for (let i = 0; i < tokens.length; i++) {
    const dash = tokens[i + 1];
    if (dash && dash.ch === "-" && !dash.escapedDash && i + 2 < tokens.length) {
      const lo = tokens[i].ch.charCodeAt(0);
      const hi = tokens[i + 2].ch.charCodeAt(0);
      if (lo > hi) throw new UsageError(`reversed range ${tokens[i].ch}-${tokens[i + 2].ch}`);
      for (let code = lo; code <= hi; code++) chars.push(String.fromCharCode(code));
      i += 2;
    } else {
      chars.push(tokens[i].ch);
    }
  }
  return chars;
}

function parseArgs(argv: string[]): { del: boolean; squeeze: boolean; sets: string[] } {
  let del = false;
  let squeeze = false;
  let i = 0;
  for (; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "-d") del = true;
    else if (arg === "-s") squeeze = true;
    else if (arg === "--") { i++; break; }
    else if (arg.startsWith("-") && arg.length >= 2) throw new UsageError(`unknown option ${arg}`);
    else break;
  }
  return { del, squeeze, sets: argv.slice(i) };
}

function main(argv: string[]): void {
  const { del, squeeze, sets: rawSets } = parseArgs(argv);
  const n = rawSets.length;
  const valid =
    (!del && !squeeze && n === 2) ||
    (del && !squeeze && n === 1) ||
    (!del && squeeze && (n === 1 || n === 2)) ||
    (del && squeeze && n === 2);
  if (!valid) throw new UsageError("wrong number of sets");

  const sets = rawSets.map(parseSet);
  const translating = !del && n === 2;
  if (translating && sets[1].length === 0) throw new UsageError("SET2 must not be empty");

  const input = readFileSync(0, "latin1");
  let out: string[];

  if (del) {
    const remove = new Set(sets[0]);
    out = [];
    for (const c of input) if (!remove.has(c)) out.push(c);
  } else if (translating) {
    const [from, to] = sets;
    const map = new Map<string, string>();
    from.forEach((c, i) => map.set(c, to[Math.min(i, to.length - 1)]));
    out = [];
    for (const c of input) out.push(map.get(c) ?? c);
  } else {
    out = Array.from(input);
  }

  if (squeeze) {
    const squeezeSet = new Set(n === 1 ? sets[0] : sets[1]);
    const kept: string[] = [];
    for (const c of out) {
      if (kept.length > 0 && kept[kept.length - 1] === c && squeezeSet.has(c)) continue;
      kept.push(c);
    }
    out = kept;
  }

  process.stdout.write(Buffer.from(out.join(""), "latin1"));
}

try {
  main(process.argv.slice(2));
} catch (e) {
  if (e instanceof UsageError) {
    process.stderr.write(`trx: ${e.message}\nusage: trx [-d] [-s] [--] SET1 [SET2]\n`);
    process.exit(2);
  }
  throw e;
}
