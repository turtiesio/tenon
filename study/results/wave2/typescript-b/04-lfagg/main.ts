import * as fs from "node:fs";

const KEY_RE = /^[A-Za-z_][A-Za-z0-9_.]*$/;
const KEY_START_RE = /[A-Za-z_]/;
const KEY_CHAR_RE = /[A-Za-z0-9_.]/;
const NUMBER_RE = /^-?[0-9]{1,15}$/;

interface Group {
  name: string;
  count: number;
  n: number;
  sum: bigint;
  min: bigint;
  max: bigint;
}

// Returns the pairs of a logfmt line, or null if the line is malformed.
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
    const keyStart = pos;
    while (pos < line.length && KEY_CHAR_RE.test(line[pos])) {
      pos++;
    }
    const key = line.slice(keyStart, pos);
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
        const c = line[pos];
        if (c === '"') {
          closed = true;
          pos++;
          break;
        }
        if (c === "\\") {
          const next = line[pos + 1];
          if (next !== '"' && next !== "\\") {
            return null;
          }
          value += next;
          pos += 2;
        } else {
          value += c;
          pos++;
        }
      }
      if (!closed) {
        return null;
      }
      if (pos < line.length && line[pos] !== " ") {
        return null;
      }
      pairs.set(key, value);
    } else {
      const valueStart = pos;
      while (pos < line.length && line[pos] !== " ") {
        pos++;
      }
      const value = line.slice(valueStart, pos);
      if (value.includes('"') || value.includes("=")) {
        return null;
      }
      pairs.set(key, value);
    }
  }
}

function splitLines(text: string): string[] {
  if (text === "") {
    return [];
  }
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") {
    lines.pop();
  }
  return lines.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line));
}

function formatAverage(sum: bigint, n: number): string {
  const count = BigInt(n);
  const negative = sum < 0n;
  const magnitude = negative ? -sum : sum;
  // Hundredths of the mean, rounded half away from zero.
  const hundredths = (magnitude * 200n + count) / (2n * count);
  const digits = hundredths.toString().padStart(3, "0");
  const text = `${digits.slice(0, -2)}.${digits.slice(-2)}`;
  return negative && hundredths !== 0n ? `-${text}` : text;
}

function formatGroup(group: Group, withField: boolean): string {
  const name = group.name === "" ? '""' : group.name;
  let line = `${name} count=${group.count}`;
  if (withField) {
    if (group.n === 0) {
      line += " n=0 sum=0 min=- max=- avg=-";
    } else {
      line += ` n=${group.n} sum=${group.sum} min=${group.min} max=${group.max} avg=${formatAverage(group.sum, group.n)}`;
    }
  }
  return line;
}

function main(argv: string[]): number {
  if (argv.length < 1 || argv.length > 2 || !argv.every((arg) => KEY_RE.test(arg))) {
    process.stderr.write("usage: lfagg BY [FIELD]\n");
    return 2;
  }
  const [by, field] = argv;

  const groups = new Map<string, Group>();
  let valid = 0;
  let malformed = 0;
  let noKey = 0;

  for (const line of splitLines(fs.readFileSync(0, "latin1"))) {
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
      noKey++;
      continue;
    }
    let group = groups.get(groupName);
    if (group === undefined) {
      group = { name: groupName, count: 0, n: 0, sum: 0n, min: 0n, max: 0n };
      groups.set(groupName, group);
    }
    group.count++;
    if (field !== undefined) {
      const raw = pairs.get(field);
      if (raw !== undefined && NUMBER_RE.test(raw)) {
        const value = BigInt(raw);
        if (group.n === 0 || value < group.min) {
          group.min = value;
        }
        if (group.n === 0 || value > group.max) {
          group.max = value;
        }
        group.sum += value;
        group.n++;
      }
    }
  }

  const sorted = [...groups.values()].sort((a, b) => {
    if (a.count !== b.count) {
      return b.count - a.count;
    }
    return a.name < b.name ? -1 : a.name > b.name ? 1 : 0;
  });
  const out = sorted.map((group) => formatGroup(group, field !== undefined) + "\n");
  out.push(`lines=${valid} malformed=${malformed} nokey=${noKey}\n`);
  process.stdout.write(Buffer.from(out.join(""), "latin1"));
  return 0;
}

process.exitCode = main(process.argv.slice(2));
