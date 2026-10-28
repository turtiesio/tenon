import * as fs from "node:fs";

const NAME = /^[A-Za-z][A-Za-z0-9_]{0,19}$/;
const MAX_CANDIDATES = 20;

function fail(msg: string): never {
  process.stderr.write(`runoff: ${msg}\n`);
  process.exit(1);
}

function readLines(): string[] {
  return fs
    .readFileSync(0, "latin1")
    .split("\n")
    .map((raw) => (raw.endsWith("\r") ? raw.slice(0, -1) : raw))
    .filter((line) => !/^ *$/.test(line) && !line.startsWith("#"));
}

function parseCandidates(line: string | undefined): string[] {
  if (line === undefined) fail("missing candidates line");
  const prefix = "candidates:";
  if (!line.startsWith(prefix)) fail("first line is not a candidates line");
  const rest = line.slice(prefix.length);
  if (!rest.startsWith(" ")) fail("candidates line names no candidates");
  const names = rest.slice(1).split(" ");
  if (names.length > MAX_CANDIDATES) fail("too many candidates");
  for (const name of names) {
    if (!NAME.test(name)) fail(`invalid candidate name: '${name}'`);
  }
  if (new Set(names).size !== names.length) fail("duplicate candidate name");
  return names;
}

/** Returns the ballot as candidate indices, or null if it is invalid. */
function parseBallot(line: string, index: Map<string, number>): number[] | null {
  const ranking: number[] = [];
  const seen = new Set<number>();
  for (const item of line.split(">")) {
    const c = index.get(item);
    if (c === undefined || seen.has(c)) return null;
    seen.add(c);
    ranking.push(c);
  }
  return ranking;
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("usage: runoff < ballots\n");
    process.exit(2);
  }

  const lines = readLines();
  const names = parseCandidates(lines[0]);
  const index = new Map(names.map((n, i) => [n, i]));

  const ballots: number[][] = [];
  let invalid = 0;
  for (const line of lines.slice(1)) {
    const ballot = parseBallot(line, index);
    if (ballot === null) invalid++;
    else ballots.push(ballot);
  }

  const out: string[] = [`ballots=${ballots.length} invalid=${invalid}`];
  const continuing = names.map(() => true);
  for (let round = 1; ; round++) {
    const votes = names.map(() => 0);
    let exhausted = 0;
    for (const ballot of ballots) {
      const choice = ballot.find((c) => continuing[c]);
      if (choice === undefined) exhausted++;
      else votes[choice]++;
    }
    const active = ballots.length - exhausted;
    const alive = names.map((_, i) => i).filter((i) => continuing[i]);

    const counts = alive.map((i) => `${names[i]}=${votes[i]}`).join(" ");
    out.push(`round ${round}: ${counts} exhausted=${exhausted}`);

    const majority = alive.find((i) => 2 * votes[i] > active);
    if (majority !== undefined || alive.length === 1) {
      out.push(`winner: ${names[majority ?? alive[0]]}`);
      break;
    }

    // Fewest votes; ties go to the candidate listed latest.
    let loser = alive[0];
    for (const i of alive) {
      if (votes[i] <= votes[loser]) loser = i;
    }
    continuing[loser] = false;
    out.push(`eliminated: ${names[loser]}`);
  }
  process.stdout.write(out.map((l) => l + "\n").join(""));
}

main();
