import * as fs from "node:fs";

interface Heading {
  level: number;
  text: string;
  slug: string;
}

function parseLevel(args: string[]): number {
  if (args.length === 0) return 6;
  if (args.length === 2 && args[0] === "-l" && /^[1-6]$/.test(args[1])) return Number(args[1]);
  process.stderr.write("usage: mdtoc [-l LEVEL]   (LEVEL is 1-6)\n");
  process.exit(2);
}

function baseSlug(text: string): string {
  const slug = text
    .replace(/[A-Z]/g, (c) => c.toLowerCase())
    .replace(/ /g, "-")
    .replace(/[^a-z0-9_-]/g, "");
  return slug === "" ? "section" : slug;
}

function trimSpaces(s: string): string {
  return s.replace(/^ +| +$/g, "");
}

function collectHeadings(lines: string[]): Heading[] {
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
    const text = trimSpaces(m[2]);
    if (text === "") continue;

    const base = baseSlug(text);
    let slug = base;
    for (let n = 1; used.has(slug); n++) slug = `${base}-${n}`;
    used.add(slug);
    headings.push({ level: m[1].length, text, slug });
  }
  return headings;
}

function main(): void {
  const maxLevel = parseLevel(process.argv.slice(2));
  const lines = fs
    .readFileSync(0, "latin1")
    .split("\n")
    .map((raw) => (raw.endsWith("\r") ? raw.slice(0, -1) : raw));

  const listed = collectHeadings(lines).filter((h) => h.level <= maxLevel);
  if (listed.length === 0) return;
  const min = Math.min(...listed.map((h) => h.level));
  const out = listed.map((h) => `${" ".repeat(2 * (h.level - min))}- [${h.text}](#${h.slug})\n`);
  process.stdout.write(out.join(""));
}

main();
