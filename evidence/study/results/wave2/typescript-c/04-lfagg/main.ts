import { readFileSync } from "node:fs";

const KEY_START_RE = /[A-Za-z_]/;
const KEY_RE = /[A-Za-z_][A-Za-z0-9_.]*/y;
const KEY_ARG_RE = /^[A-Za-z_][A-Za-z0-9_.]*$/;
const NUMERIC_RE = /^-?[0-9]{1,15}$/;

interface Group {
  count: number;
  n: number;
  sum: bigint;
  min: bigint;
  max: bigint;
}

// Returns the pairs of a line, or null if the line is malformed.
function parseLine(line: string): Map<string, string> | null {
  const pairs = new Map<string, string>();
  let pos = 0;
  while (true) {
    while (line[pos] === " ") {
      pos++;
    }
    if (pos >= line.length) {
      return pairs;
    }
    if (!KEY_START_RE.test(line[pos])) {
      return null;
    }
    KEY_RE.lastIndex = pos;
    const key = KEY_RE.exec(line)![0];
    pos += key.length;
    if (pairs.has(key)) {
      return null;
    }

    if (pos >= line.length || line[pos] === " ") {
      pairs.set(key, "true");
      continue;
    }
    if (line[pos] !== "=") {
      return null;
    }
    pos++;

    if (line[pos] === '"') {
      pos++;
      let value = "";
      let closed = false;
      while (pos < line.length) {
        const ch = line[pos];
        if (ch === "\\") {
          const next = line[pos + 1];
          if (next !== '"' && next !== "\\") {
            return null;
          }
          value += next;
          pos += 2;
        } else if (ch === '"') {
          pos++;
          closed = true;
          break;
        } else {
          value += ch;
          pos++;
        }
      }
      if (!closed || (pos < line.length && line[pos] !== " ")) {
        return null;
      }
      pairs.set(key, value);
    } else {
      let end = pos;
      while (end < line.length && line[end] !== " ") {
        end++;
      }
      const value = line.slice(pos, end);
      if (value.includes('"') || value.includes("=")) {
        return null;
      }
      pairs.set(key, value);
      pos = end;
    }
  }
}

// sum / n rounded to two decimals, half away from zero.
function formatAverage(sum: bigint, n: bigint): string {
  const negative = sum < 0n;
  const magnitude = negative ? -sum : sum;
  const hundredths = (magnitude * 200n + n) / (2n * n);
  const text = hundredths.toString().padStart(3, "0");
  const body = `${text.slice(0, -2)}.${text.slice(-2)}`;
  return negative && hundredths !== 0n ? `-${body}` : body;
}

function main(): number {
  const args = process.argv.slice(2);
  if (args.length < 1 || args.length > 2 || !args.every((arg) => KEY_ARG_RE.test(arg))) {
    console.error("usage: lfagg BY [FIELD]");
    return 2;
  }
  const [by, field] = args;

  const lines = readFileSync(0, "latin1").split("\n");
  if (lines[lines.length - 1] === "") {
    lines.pop();
  }

  const groups = new Map<string, Group>();
  let valid = 0;
  let malformed = 0;
  let nokey = 0;

  for (let line of lines) {
    if (line.endsWith("\r")) {
      line = line.slice(0, -1);
    }
    if (/^ *$/.test(line)) {
      continue;
    }
    const pairs = parseLine(line);
    if (pairs === null) {
      malformed++;
      continue;
    }
    valid++;
    const groupName = pairs.get(by);
    if (groupName === undefined) {
      nokey++;
      continue;
    }
    let group = groups.get(groupName);
    if (group === undefined) {
      group = { count: 0, n: 0, sum: 0n, min: 0n, max: 0n };
      groups.set(groupName, group);
    }
    group.count++;
    const raw = field === undefined ? undefined : pairs.get(field);
    if (raw !== undefined && NUMERIC_RE.test(raw)) {
      const number = BigInt(raw);
      if (group.n === 0 || number < group.min) {
        group.min = number;
      }
      if (group.n === 0 || number > group.max) {
        group.max = number;
      }
      group.n++;
      group.sum += number;
    }
  }

  const sorted = [...groups.entries()].sort(([nameA, a], [nameB, b]) => {
    if (a.count !== b.count) {
      return b.count - a.count;
    }
    return nameA < nameB ? -1 : nameA > nameB ? 1 : 0;
  });

  const out: string[] = [];
  for (const [name, group] of sorted) {
    let text = `${name === "" ? '""' : name} count=${group.count}`;
    if (field !== undefined) {
      if (group.n === 0) {
        text += " n=0 sum=0 min=- max=- avg=-";
      } else {
        const avg = formatAverage(group.sum, BigInt(group.n));
        text += ` n=${group.n} sum=${group.sum} min=${group.min} max=${group.max} avg=${avg}`;
      }
    }
    out.push(text);
  }
  out.push(`lines=${valid} malformed=${malformed} nokey=${nokey}`);
  process.stdout.write(out.join("\n") + "\n");
  return 0;
}

process.exitCode = main();
