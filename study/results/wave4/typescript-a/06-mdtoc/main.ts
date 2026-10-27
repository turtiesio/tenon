import fs from 'node:fs';
const args = process.argv.slice(2);
if (args.length !== 0 && !(args.length === 2 && args[0] === '-l' && /^[1-6]$/.test(args[1]))) {
  console.error('Invalid arguments'); process.exit(2);
}
const limit = args.length ? Number(args[1]) : 6;
const used = new Set<string>();
const nextSuffix = new Map<string, number>();
const headings: {level: number; text: string; slug: string}[] = [];
let fenced = false;
for (const raw of fs.readFileSync(0, 'utf8').split('\n')) {
  const line = raw.replace(/\r$/, '');
  if (line.startsWith('```')) { fenced = !fenced; continue; }
  if (fenced) continue;
  const match = /^(#{1,6}) (.*)$/.exec(line);
  if (!match) continue;
  const text = match[2].replace(/^ +| +$/g, '');
  if (!text) continue;
  const base = text.toLowerCase().replace(/ /g, '-').replace(/[^a-z0-9_-]/g, '') || 'section';
  let slug = base;
  if (used.has(slug)) {
    let suffix = nextSuffix.get(base) ?? 1;
    while (used.has(`${base}-${suffix}`)) suffix++;
    slug = `${base}-${suffix}`;
    nextSuffix.set(base, suffix + 1);
  }
  used.add(slug);
  const level = match[1].length;
  if (level <= limit) headings.push({level, text, slug});
}
const minimum = headings.reduce((min, h) => Math.min(min, h.level), 6);
for (const h of headings) console.log(`${' '.repeat(2 * (h.level - minimum))}- [${h.text}](#${h.slug})`);
