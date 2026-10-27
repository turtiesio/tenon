import { readFileSync } from "node:fs";
const text = readFileSync(0, "utf8").toLowerCase();
const counts = new Map<string, number>();
for (const w of text.split(/[ \t\r\n]+/)) if (w) counts.set(w, (counts.get(w) ?? 0) + 1);
const entries = [...counts.entries()].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
console.log(entries.slice(0, 10).map(([w, n]) => `${n} ${w}`).join("\n"));
