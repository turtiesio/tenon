import { readFileSync } from "node:fs";

interface Counts {
  lines: number;
  words: number;
  chars: number;
  bytes: number;
}

const OPTIONS = new Set(["-l", "-w", "-m", "-c"]);

function isSpace(b: number): boolean {
  return b === 0x20 || (b >= 0x09 && b <= 0x0d);
}

function count(data: Uint8Array): Counts {
  let lines = 0;
  let words = 0;
  let chars = 0;
  let inWord = false;
  for (const b of data) {
    if (b === 0x0a) lines++;
    if ((b & 0xc0) !== 0x80) chars++;
    if (isSpace(b)) {
      inWord = false;
    } else if (!inWord) {
      inWord = true;
      words++;
    }
  }
  return { lines, words, chars, bytes: data.length };
}

function readStdin(): Uint8Array {
  try {
    return readFileSync(0);
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "EOF") return new Uint8Array(0);
    throw e;
  }
}

function main(): number {
  const args = process.argv.slice(2);
  const selected = new Set<string>();
  const files: string[] = [];
  for (const arg of args) {
    if (OPTIONS.has(arg)) {
      selected.add(arg);
    } else if (arg.startsWith("-")) {
      process.stderr.write(`wcx: invalid option '${arg}'\nusage: wcx [-l] [-w] [-m] [-c] [FILE...]\n`);
      return 2;
    } else {
      files.push(arg);
    }
  }
  if (selected.size === 0) {
    selected.add("-l").add("-w").add("-c");
  }
  const pick = (c: Counts): number[] => {
    const out: number[] = [];
    if (selected.has("-l")) out.push(c.lines);
    if (selected.has("-w")) out.push(c.words);
    if (selected.has("-m")) out.push(c.chars);
    if (selected.has("-c")) out.push(c.bytes);
    return out;
  };

  const rows: { counts: number[]; name: string | null }[] = [];
  let status = 0;
  if (files.length === 0) {
    rows.push({ counts: pick(count(readStdin())), name: null });
  } else {
    const total = pick({ lines: 0, words: 0, chars: 0, bytes: 0 });
    for (const file of files) {
      let data: Uint8Array;
      try {
        data = readFileSync(file);
      } catch (e) {
        process.stderr.write(`wcx: ${file}: ${(e as Error).message}\n`);
        status = 1;
        continue;
      }
      const counts = pick(count(data));
      counts.forEach((n, i) => (total[i] += n));
      rows.push({ counts, name: file });
    }
    if (files.length >= 2) rows.push({ counts: total, name: "total" });
  }

  const width = Math.max(1, ...rows.flatMap((r) => r.counts.map((n) => String(n).length)));
  let out = "";
  for (const row of rows) {
    out += row.counts.map((n) => String(n).padStart(width)).join(" ");
    if (row.name !== null) out += " " + row.name;
    out += "\n";
  }
  process.stdout.write(out);
  return status;
}

process.exitCode = main();
