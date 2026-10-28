import { readFileSync } from "node:fs";

// Addresses are plain numbers in 0 .. 2^32-1; arithmetic (not bitwise
// operators, which work on signed 32-bit values) keeps them non-negative.
const TWO_32 = 2 ** 32;

interface Range {
  start: number;
  end: number; // inclusive
}

const OCTET = "(0|[1-9][0-9]{0,2})";
const ENTRY = new RegExp(`^${OCTET}\\.${OCTET}\\.${OCTET}\\.${OCTET}(?:/(0|[1-9][0-9]?))?$`);

function parseEntry(line: string): Range | null {
  const m = ENTRY.exec(line);
  if (m === null) return null;
  const octets = m.slice(1, 5).map(Number);
  if (octets.some((o) => o > 255)) return null;
  const prefix = m[5] === undefined ? 32 : Number(m[5]);
  if (prefix > 32) return null;
  const address = octets.reduce((acc, o) => acc * 256 + o, 0);
  const size = 2 ** (32 - prefix);
  if (address % size !== 0) return null;
  return { start: address, end: address + size - 1 };
}

function merge(ranges: Range[]): Range[] {
  const sorted = [...ranges].sort((a, b) => a.start - b.start);
  const merged: Range[] = [];
  for (const r of sorted) {
    const last = merged[merged.length - 1];
    if (last !== undefined && r.start <= last.end + 1) {
      last.end = Math.max(last.end, r.end);
    } else {
      merged.push({ ...r });
    }
  }
  return merged;
}

function dotted(address: number): string {
  const parts: number[] = [];
  for (let i = 0; i < 4; i++) {
    parts.unshift(address % 256);
    address = Math.floor(address / 256);
  }
  return parts.join(".");
}

// Fewest CIDR blocks covering [start, end], taking the largest aligned block each time.
function toBlocks(range: Range): string[] {
  const blocks: string[] = [];
  let s = range.start;
  while (s <= range.end) {
    let bits = 32;
    // Largest block that starts at s (alignment) and ends at or before range.end.
    while (bits > 0 && (s % 2 ** bits !== 0 || s + 2 ** bits - 1 > range.end)) bits--;
    blocks.push(`${dotted(s)}/${32 - bits}`);
    s += 2 ** bits;
  }
  return blocks;
}

function main(): number {
  const args = process.argv.slice(2);
  if (args.length > 1 || (args.length === 1 && args[0] !== "-r")) {
    process.stderr.write("usage: cidrmerge [-r]\n");
    return 2;
  }
  const asRanges = args.length === 1;

  const lines = readFileSync(0, "latin1").split("\n");
  if (lines[lines.length - 1] === "") lines.pop();

  let status = 0;
  const entries: Range[] = [];
  lines.forEach((raw, index) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line === "" || line.startsWith("#")) return;
    const entry = parseEntry(line);
    if (entry === null) {
      process.stderr.write(`cidrmerge: line ${index + 1}: bad entry: ${JSON.stringify(line)}\n`);
      status = 1;
    } else {
      entries.push(entry);
    }
  });

  const out: string[] = [];
  for (const r of merge(entries)) {
    if (asRanges) {
      out.push(`${dotted(r.start)}-${dotted(r.end)} ${r.end - r.start + 1}`);
    } else {
      out.push(...toBlocks(r));
    }
  }
  process.stdout.write(out.map((l) => l + "\n").join(""));
  return status;
}

process.exitCode = main();
