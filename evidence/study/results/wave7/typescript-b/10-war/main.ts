import * as fs from "node:fs";

const RANKS = "23456789TJQKA";

interface Options {
  maxRounds: number;
  quiet: boolean;
}

class UsageError extends Error {}

function parseArgs(args: string[]): Options {
  const opts: Options = { maxRounds: 1000, quiet: false };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-q") {
      opts.quiet = true;
    } else if (arg === "-n") {
      if (i + 1 >= args.length) throw new UsageError("-n needs a value");
      const value = args[++i];
      if (!/^[1-9][0-9]{0,5}$/.test(value)) throw new UsageError(`bad round limit: ${value}`);
      opts.maxRounds = Number(value);
    } else {
      throw new UsageError(`unexpected argument: ${arg}`);
    }
  }
  return opts;
}

function parseDecks(text: string): [string[], string[]] | null {
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  if (lines.length !== 2) return null;
  const decks = lines.map((raw) => (raw.endsWith("\r") ? raw.slice(0, -1) : raw));
  if (!decks.every((d) => /^[2-9TJQKA]{1,52}$/.test(d))) return null;
  return [[...decks[0]], [...decks[1]]];
}

function rank(card: string): number {
  return RANKS.indexOf(card);
}

/** Plays the game and returns the output lines. */
function play(a: string[], b: string[], opts: Options): string[] {
  const out: string[] = [];
  for (let round = 1; round <= opts.maxRounds; round++) {
    const pile: string[] = [];
    const faceA: string[] = [];
    const faceB: string[] = [];
    let winner: "A" | "B" | "-";

    const cardA = a.shift()!;
    const cardB = b.shift()!;
    pile.push(cardA, cardB);
    faceA.push(cardA);
    faceB.push(cardB);
    for (;;) {
      const lastA = faceA.at(-1)!;
      const lastB = faceB.at(-1)!;
      if (rank(lastA) !== rank(lastB)) {
        winner = rank(lastA) > rank(lastB) ? "A" : "B";
        (winner === "A" ? a : b).push(...pile);
        break;
      }
      if (a.length < 4 || b.length < 4) {
        winner = "-"; // the war cannot be completed; the pile is discarded
        break;
      }
      const drawnA = a.splice(0, 4);
      const drawnB = b.splice(0, 4);
      pile.push(...drawnA, ...drawnB);
      faceA.push(drawnA[3]);
      faceB.push(drawnB[3]);
    }

    if (!opts.quiet) {
      out.push(`${round} ${faceA.join("/")} ${faceB.join("/")} ${winner} ${a.length} ${b.length}`);
    }
    if (winner === "-") {
      if (a.length === b.length) out.push(`draw in round ${round}`);
      else out.push(`${a.length > b.length ? "A" : "B"} wins in round ${round}`);
      return out;
    }
    if (a.length === 0) {
      out.push(`B wins in round ${round}`);
      return out;
    }
    if (b.length === 0) {
      out.push(`A wins in round ${round}`);
      return out;
    }
  }
  out.push(`stopped at round ${opts.maxRounds}`);
  return out;
}

function main(): void {
  let opts: Options;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`war: ${e.message}\nusage: war [-n MAX] [-q]\n`);
      process.exit(2);
    }
    throw e;
  }

  const decks = parseDecks(fs.readFileSync(0, "latin1"));
  if (decks === null) {
    process.stderr.write("war: invalid input: expected two decks of 1 to 52 cards from 23456789TJQKA\n");
    process.exit(1);
  }
  process.stdout.write(play(decks[0], decks[1], opts).map((l) => l + "\n").join(""));
}

main();
