import { readFileSync } from "node:fs";

const RANKS = "23456789TJQKA";
const WAR_DRAWS = 4;

class UsageError extends Error {}
class InputError extends Error {}

function parseArgs(argv: string[]): { max: number; quiet: boolean } {
  let max = 1000;
  let quiet = false;
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "-n") {
      if (i + 1 >= argv.length || !/^[1-9][0-9]{0,5}$/.test(argv[i + 1])) {
        throw new UsageError("-n needs a number from 1 to 999999");
      }
      max = Number(argv[++i]);
    } else if (arg === "-q") {
      quiet = true;
    } else {
      throw new UsageError(`unknown argument: ${arg}`);
    }
  }
  return { max, quiet };
}

function readDecks(): [string[], string[]] {
  const lines = readFileSync(0, "latin1").split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  if (lines.length !== 2) throw new InputError("expected exactly two lines");
  const decks = lines.map((raw) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (!/^[2-9TJQKA]{1,52}$/.test(line)) throw new InputError(`invalid deck: ${JSON.stringify(line)}`);
    return [...line];
  });
  return [decks[0], decks[1]];
}

const rank = (card: string): number => RANKS.indexOf(card);

function play(a: string[], b: string[], max: number, quiet: boolean): string[] {
  const out: string[] = [];
  let round = 0;
  while (round < max) {
    round++;
    const pile: string[] = [];
    const upA: string[] = [];
    const upB: string[] = [];
    const faceUp = () => {
      const ca = a.shift()!;
      const cb = b.shift()!;
      pile.push(ca, cb);
      upA.push(ca);
      upB.push(cb);
    };
    faceUp();

    let cannotComplete = false;
    while (upA[upA.length - 1] === upB[upB.length - 1]) {
      if (a.length < WAR_DRAWS || b.length < WAR_DRAWS) {
        cannotComplete = true;
        break;
      }
      const drawnA = a.splice(0, WAR_DRAWS);
      const drawnB = b.splice(0, WAR_DRAWS);
      pile.push(...drawnA, ...drawnB);
      upA.push(drawnA[WAR_DRAWS - 1]);
      upB.push(drawnB[WAR_DRAWS - 1]);
    }

    let winner: "A" | "B" | "-";
    if (cannotComplete) {
      winner = "-"; // the pile is discarded
    } else {
      winner = rank(upA[upA.length - 1]) > rank(upB[upB.length - 1]) ? "A" : "B";
      (winner === "A" ? a : b).push(...pile);
    }
    if (!quiet) out.push(`${round} ${upA.join("/")} ${upB.join("/")} ${winner} ${a.length} ${b.length}`);

    if (cannotComplete) {
      const result = a.length === b.length ? "draw" : a.length > b.length ? "A wins" : "B wins";
      out.push(`${result} in round ${round}`);
      return out;
    }
    if (a.length === 0 || b.length === 0) {
      out.push(`${winner} wins in round ${round}`);
      return out;
    }
  }
  out.push(`stopped at round ${max}`);
  return out;
}

function main(): number {
  let options: ReturnType<typeof parseArgs>;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`war: ${e.message}\n`);
      return 2;
    }
    throw e;
  }
  let decks: [string[], string[]];
  try {
    decks = readDecks();
  } catch (e) {
    if (e instanceof InputError) {
      process.stderr.write(`war: ${e.message}\n`);
      return 1;
    }
    throw e;
  }
  const lines = play(decks[0], decks[1], options.max, options.quiet);
  process.stdout.write(lines.map((l) => l + "\n").join(""));
  return 0;
}

process.exitCode = main();
