import * as fs from "node:fs";

interface Heading {
  level: number;
  text: string;
  slug: string;
}

function parseLevel(args: string[]): number | null {
  if (args.length === 0) return 6;
  if (args.length === 2 && args[0] === "-l" && /^[1-6]$/.test(args[1])) return Number(args[1]);
  return null;
}

function baseSlug(text: string): string {
  const slug = text
    .toLowerCase()
    .replace(/ /g, "-")
    .replace(/[^a-z0-9\-_]/g, "");
  return slug === "" ? "section" : slug;
}

function uniqueSlug(base: string, used: Set<string>): string {
  let slug = base;
  for (let n = 1; used.has(slug); n++) slug = `${base}-${n}`;
  used.add(slug);
  return slug;
}

function parseHeadings(lines: string[]): Heading[] {
  const headings: Heading[] = [];
  const used = new Set<string>();
  let inFence = false;
  for (const line of lines) {
    if (line.startsWith("```")) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;
    const m = /^(#{1,6}) (.*)$/.exec(line);
    if (m === null) continue;
    const text = m[2].replace(/^ +| +$/g, "");
    if (text === "") continue;
    headings.push({ level: m[1].length, text, slug: uniqueSlug(baseSlug(text), used) });
  }
  return headings;
}

function main(): number {
  const maxLevel = parseLevel(process.argv.slice(2));
  if (maxLevel === null) {
    console.error("usage: mdtoc [-l LEVEL]   (LEVEL is 1-6)");
    return 2;
  }

  let text: string;
  try {
    text = fs.readFileSync(0, "latin1");
  } catch {
    text = "";
  }
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  const cleaned = lines.map((l) => (l.endsWith("\r") ? l.slice(0, -1) : l));

  const listed = parseHeadings(cleaned).filter((h) => h.level <= maxLevel);
  if (listed.length === 0) return 0;
  const min = Math.min(...listed.map((h) => h.level));
  const out = listed.map((h) => `${" ".repeat(2 * (h.level - min))}- [${h.text}](#${h.slug})\n`);
  process.stdout.write(out.join(""));
  return 0;
}

process.exitCode = main();
