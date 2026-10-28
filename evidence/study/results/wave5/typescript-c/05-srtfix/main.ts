import { readFileSync } from "node:fs";

const OFFSET = /^[+-]?[0-9]{1,9}$/;
const INDEX = /^[0-9]{1,9}$/;
const TIME = "([0-9]{2}):([0-5][0-9]):([0-5][0-9]),([0-9]{3})";
const TIMING = new RegExp(`^${TIME} --> ${TIME}$`);

class InvalidInput extends Error {}

interface Cue {
  start: number;
  end: number;
  text: string[];
}

function readLines(): string[] {
  const text = readFileSync(0, "utf8");
  if (text === "") return [];
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  return lines.map((l) => (l.endsWith("\r") ? l.slice(0, -1) : l));
}

const isBlank = (line: string): boolean => /^[ \t]*$/.test(line);

function toMillis(h: string, m: string, s: string, ms: string): number {
  return ((Number(h) * 60 + Number(m)) * 60 + Number(s)) * 1000 + Number(ms);
}

function splitBlocks(lines: string[]): string[][] {
  const blocks: string[][] = [];
  let current: string[] = [];
  for (const line of lines) {
    if (isBlank(line)) {
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
  if (block.length < 3) throw new InvalidInput(`cue ${n}: needs index, timing and text`);
  if (!INDEX.test(block[0])) throw new InvalidInput(`cue ${n}: bad index line`);
  const m = TIMING.exec(block[1]);
  if (m === null) throw new InvalidInput(`cue ${n}: bad timing line`);
  const start = toMillis(m[1], m[2], m[3], m[4]);
  const end = toMillis(m[5], m[6], m[7], m[8]);
  if (end <= start) throw new InvalidInput(`cue ${n}: end must be after start`);
  return { start, end, text: block.slice(2) };
}

function formatTime(ms: number): string {
  const pad = (v: number, w: number) => String(v).padStart(w, "0");
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor(ms / 60_000) % 60;
  const s = Math.floor(ms / 1000) % 60;
  return `${pad(h, 2)}:${pad(m, 2)}:${pad(s, 2)},${pad(ms % 1000, 3)}`;
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1 || !OFFSET.test(args[0])) {
    process.stderr.write("srtfix: usage: srtfix OFFSET (milliseconds, e.g. +1500)\n");
    process.exit(2);
  }
  const offset = Number(args[0]);

  let cues: Cue[];
  try {
    cues = splitBlocks(readLines()).map((b, i) => parseCue(b, i + 1));
  } catch (e) {
    if (!(e instanceof InvalidInput)) throw e;
    process.stderr.write(`srtfix: ${e.message}\n`);
    process.exit(1);
  }

  const shifted = cues
    .map((c) => ({ ...c, start: c.start + offset, end: c.end + offset }))
    .filter((c) => c.end > 0)
    .map((c) => ({ ...c, start: Math.max(0, c.start) }))
    .sort((a, b) => a.start - b.start);

  const out = shifted.map(
    (c, i) => [String(i + 1), `${formatTime(c.start)} --> ${formatTime(c.end)}`, ...c.text, ""].join("\n") + "\n",
  );
  process.stdout.write(out.join(""));
}

main();
