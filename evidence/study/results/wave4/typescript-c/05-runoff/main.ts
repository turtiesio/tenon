import * as fs from "node:fs";

const NAME = /^[A-Za-z][A-Za-z0-9_]{0,19}$/;

function parseCandidates(line: string): string[] | null {
  const prefix = "candidates:";
  if (!line.startsWith(prefix)) return null;
  const rest = line.slice(prefix.length);
  if (rest === "") return null;
  // Each name is preceded by exactly one space, so the rest splits on " " with an empty first piece.
  const parts = rest.split(" ");
  if (parts[0] !== "") return null;
  const names = parts.slice(1);
  if (names.length < 1 || names.length > 20) return null;
  if (!names.every((n) => NAME.test(n))) return null;
  if (new Set(names).size !== names.length) return null;
  return names;
}

// Returns the ballot as candidate indexes, or null if the ballot is invalid.
function parseBallot(line: string, index: Map<string, number>): number[] | null {
  const ranking: number[] = [];
  for (const item of line.split(">")) {
    const idx = index.get(item);
    if (idx === undefined || ranking.includes(idx)) return null;
    ranking.push(idx);
  }
  return ranking;
}

function main(): number {
  if (process.argv.length > 2) {
    console.error("runoff: takes no arguments");
    return 2;
  }

  let text: string;
  try {
    text = fs.readFileSync(0, "latin1");
  } catch {
    text = "";
  }

  const lines: string[] = [];
  const raw = text.split("\n");
  if (raw[raw.length - 1] === "") raw.pop();
  for (let line of raw) {
    if (line.endsWith("\r")) line = line.slice(0, -1);
    if (/^ *$/.test(line) || line.startsWith("#")) continue;
    lines.push(line);
  }

  const names = lines.length > 0 ? parseCandidates(lines[0]) : null;
  if (names === null) {
    console.error("runoff: missing or invalid candidates line");
    return 1;
  }
  const index = new Map(names.map((n, i): [string, number] => [n, i]));

  const ballots: number[][] = [];
  let invalid = 0;
  for (const line of lines.slice(1)) {
    const ballot = parseBallot(line, index);
    if (ballot === null) invalid++;
    else ballots.push(ballot);
  }

  const out: string[] = [`ballots=${ballots.length} invalid=${invalid}\n`];
  const continuing = new Set(names.map((_, i) => i));
  for (let round = 1; ; round++) {
    const votes = new Array<number>(names.length).fill(0);
    let exhausted = 0;
    for (const ballot of ballots) {
      const choice = ballot.find((c) => continuing.has(c));
      if (choice === undefined) exhausted++;
      else votes[choice]++;
    }
    const active = ballots.length - exhausted;
    const standing = [...continuing].sort((a, b) => a - b);
    const tally = standing.map((c) => `${names[c]}=${votes[c]}`).join(" ");
    out.push(`round ${round}: ${tally} exhausted=${exhausted}\n`);

    const majority = standing.find((c) => 2 * votes[c] > active);
    if (majority !== undefined) {
      out.push(`winner: ${names[majority]}\n`);
      break;
    }
    if (standing.length === 1) {
      out.push(`winner: ${names[standing[0]]}\n`);
      break;
    }
    // Fewest votes; on a tie the latest in listing order goes.
    let loser = standing[0];
    for (const c of standing) {
      if (votes[c] <= votes[loser]) loser = c;
    }
    continuing.delete(loser);
    out.push(`eliminated: ${names[loser]}\n`);
  }
  process.stdout.write(out.join(""));
  return 0;
}

process.exitCode = main();
