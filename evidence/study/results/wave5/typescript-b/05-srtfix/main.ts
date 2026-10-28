import { readFileSync } from "node:fs";

class InputError extends Error {}

type Cue = { start: number; end: number; text: string[] };

const TIME = "([0-9]{2}):([0-5][0-9]):([0-5][0-9]),([0-9]{3})";
const TIMING_RE = new RegExp(`^${TIME} --> ${TIME}$`);

function readLines(): string[] {
  const text = readFileSync(0, "utf8");
  if (text === "") return [];
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  return lines.map((l) => (l.endsWith("\r") ? l.slice(0, -1) : l));
}

function toMs(h: string, m: string, s: string, ms: string): number {
  return ((Number(h) * 60 + Number(m)) * 60 + Number(s)) * 1000 + Number(ms);
}

function formatTime(total: number): string {
  const ms = total % 1000;
  const secs = Math.floor(total / 1000);
  const p = (n: number, w: number) => String(n).padStart(w, "0");
  return `${p(Math.floor(secs / 3600), 2)}:${p(Math.floor(secs / 60) % 60, 2)}:${p(secs % 60, 2)},${p(ms, 3)}`;
}

function splitBlocks(lines: string[]): string[][] {
  const blocks: string[][] = [];
  let current: string[] = [];
  for (const line of lines) {
    if (/^[ \t]*$/.test(line)) {
      if (current.length > 0) blocks.push(current);
      current = [];
    } else {
      current.push(line);
    }
  }
  if (current.length > 0) blocks.push(current);
  return blocks;
}

function parseCue(block: string[], n: number): Cue {
  if (block.length < 3) throw new InputError(`cue ${n}: needs index, timing and text lines`);
  if (!/^[0-9]{1,9}$/.test(block[0])) throw new InputError(`cue ${n}: bad index line`);
  const m = TIMING_RE.exec(block[1]);
  if (!m) throw new InputError(`cue ${n}: bad timing line`);
  const start = toMs(m[1], m[2], m[3], m[4]);
  const end = toMs(m[5], m[6], m[7], m[8]);
  if (end <= start) throw new InputError(`cue ${n}: end is not after start`);
  return { start, end, text: block.slice(2) };
}

function main(argv: string[]): void {
  if (argv.length !== 1 || !/^[+-]?[0-9]{1,9}$/.test(argv[0])) {
    process.stderr.write("usage: srtfix OFFSET   (milliseconds, e.g. +1500 or -250)\n");
    process.exit(2);
  }
  const offset = Number(argv[0]);

  let cues: Cue[];
  try {
    cues = splitBlocks(readLines()).map((b, i) => parseCue(b, i + 1));
  } catch (e) {
    if (e instanceof InputError) {
      process.stderr.write(`srtfix: ${e.message}\n`);
      process.exit(1);
    }
    throw e;
  }

  const shifted = cues
    .map((c) => ({ ...c, start: c.start + offset, end: c.end + offset }))
    .filter((c) => c.end > 0)
    .map((c) => ({ ...c, start: Math.max(0, c.start) }))
    .sort((a, b) => a.start - b.start); // Array.prototype.sort is stable

  const out: string[] = [];
  shifted.forEach((c, i) => {
    out.push(String(i + 1), `${formatTime(c.start)} --> ${formatTime(c.end)}`, ...c.text, "");
  });
  process.stdout.write(out.map((l) => l + "\n").join(""));
}

main(process.argv.slice(2));
