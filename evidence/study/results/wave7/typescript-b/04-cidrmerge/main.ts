import * as fs from "node:fs";

// Addresses are plain numbers (0 to 2^32), not 32-bit integers, so that range
// ends and counts up to 2^32 are exact. Bitwise operators are avoided.

interface Range {
  start: number; // first address
  end: number; // one past the last address
}

const DECIMAL = "(0|[1-9][0-9]*)";
const ENTRY = new RegExp(`^${DECIMAL}\\.${DECIMAL}\\.${DECIMAL}\\.${DECIMAL}(?:/${DECIMAL})?$`);

/** Parses an entry into the range it covers, or returns an error message. */
function parseEntry(line: string): Range | string {
  const m = ENTRY.exec(line);
  if (m === null) return "not an address or CIDR block";
  const octets = m.slice(1, 5).map(Number);
  if (octets.some((o) => o > 255)) return "octet above 255";
  const prefix = m[5] === undefined ? 32 : Number(m[5]);
  if (prefix > 32) return "prefix above 32";
  const address = ((octets[0] * 256 + octets[1]) * 256 + octets[2]) * 256 + octets[3];
  const size = 2 ** (32 - prefix);
  if (address % size !== 0) return "bits set after the prefix";
  return { start: address, end: address + size };
}

function formatAddress(address: number): string {
  const octets: number[] = [];
  for (let i = 0; i < 4; i++) {
    octets.unshift(address % 256);
    address = Math.floor(address / 256);
  }
  return octets.join(".");
}

function mergeRanges(ranges: Range[]): Range[] {
  const sorted = [...ranges].sort((a, b) => a.start - b.start);
  const merged: Range[] = [];
  for (const r of sorted) {
    const last = merged.at(-1);
    if (last !== undefined && r.start <= last.end) {
      last.end = Math.max(last.end, r.end);
    } else {
      merged.push({ ...r });
    }
  }
  return merged;
}

/** Splits a range into the fewest CIDR blocks, greedily from the start. */
function toBlocks(range: Range): string[] {
  const blocks: string[] = [];
  let start = range.start;
  while (start < range.end) {
    let prefix = 0;
    while (start % 2 ** (32 - prefix) !== 0 || start + 2 ** (32 - prefix) > range.end) prefix++;
    blocks.push(`${formatAddress(start)}/${prefix}`);
    start += 2 ** (32 - prefix);
  }
  return blocks;
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length > 1 || (args.length === 1 && args[0] !== "-r")) {
    process.stderr.write("usage: cidrmerge [-r]\n");
    process.exit(2);
  }
  const showRanges = args.length === 1;

  const text = fs.readFileSync(0, "utf8");
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();

  let bad = false;
  const ranges: Range[] = [];
  lines.forEach((raw, index) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line === "" || line.startsWith("#")) return;
    const entry = parseEntry(line);
    if (typeof entry === "string") {
      process.stderr.write(`cidrmerge: line ${index + 1}: ${entry}: ${JSON.stringify(line)}\n`);
      bad = true;
    } else {
      ranges.push(entry);
    }
  });

  const out: string[] = [];
  for (const range of mergeRanges(ranges)) {
    if (showRanges) {
      out.push(`${formatAddress(range.start)}-${formatAddress(range.end - 1)} ${range.end - range.start}`);
    } else {
      out.push(...toBlocks(range));
    }
  }
  process.stdout.write(out.map((l) => l + "\n").join(""));
  process.exitCode = bad ? 1 : 0;
}

main();
