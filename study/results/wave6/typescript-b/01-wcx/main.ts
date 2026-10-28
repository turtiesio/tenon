import * as fs from "node:fs";

interface Counts {
  lines: number;
  words: number;
  chars: number;
  bytes: number;
}

function isSpace(b: number): boolean {
  return b === 0x20 || (b >= 0x09 && b <= 0x0d);
}

function count(data: Buffer): Counts {
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

function main(): number {
  const flags = new Set<string>();
  const files: string[] = [];
  for (const arg of process.argv.slice(2)) {
    if (arg === "-l" || arg === "-w" || arg === "-m" || arg === "-c") {
      flags.add(arg);
    } else if (arg.startsWith("-")) {
      process.stderr.write(`wcx: invalid option '${arg}'\nusage: wcx [-l] [-w] [-m] [-c] [FILE...]\n`);
      return 2;
    } else {
      files.push(arg);
    }
  }
  if (flags.size === 0) ["-l", "-w", "-c"].forEach((f) => flags.add(f));
  const selected: (keyof Counts)[] = [];
  if (flags.has("-l")) selected.push("lines");
  if (flags.has("-w")) selected.push("words");
  if (flags.has("-m")) selected.push("chars");
  if (flags.has("-c")) selected.push("bytes");

  const rows: { counts: Counts; name: string | null }[] = [];
  let status = 0;
  if (files.length === 0) {
    rows.push({ counts: count(fs.readFileSync(0)), name: null });
  } else {
    const total: Counts = { lines: 0, words: 0, chars: 0, bytes: 0 };
    for (const file of files) {
      let data: Buffer;
      try {
        data = fs.readFileSync(file);
      } catch (e) {
        process.stderr.write(`wcx: ${file}: ${(e as Error).message}\n`);
        status = 1;
        continue;
      }
      const c = count(data);
      rows.push({ counts: c, name: file });
      for (const k of selected) total[k] += c[k];
    }
    if (files.length >= 2) rows.push({ counts: total, name: "total" });
  }

  let width = 1;
  for (const row of rows) {
    for (const k of selected) width = Math.max(width, String(row.counts[k]).length);
  }
  let out = "";
  for (const row of rows) {
    const fields = selected.map((k) => String(row.counts[k]).padStart(width));
    out += fields.join(" ") + (row.name === null ? "" : " " + row.name) + "\n";
  }
  process.stdout.write(out);
  return status;
}

process.exitCode = main();
