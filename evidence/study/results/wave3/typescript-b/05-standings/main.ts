import * as fs from "node:fs";

class UsageError extends Error {}
class InputError extends Error {}

interface Points {
  win: number;
  draw: number;
  loss: number;
}

interface Match {
  home: string;
  away: string;
  homeGoals: number;
  awayGoals: number;
}

type Outcome = "W" | "D" | "L";

interface Team {
  name: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goalsFor: number;
  goalsAgainst: number;
  points: number;
  form: Outcome[];
}

const SCORE = /^([0-9]{1,2})-([0-9]{1,2})$/;
const NAME_TOKEN = /^[A-Za-z0-9.&']+$/;

function parseArgs(args: string[]): Points {
  if (args.length === 0) return { win: 3, draw: 1, loss: 0 };
  if (args.length !== 2 || args[0] !== "-p") throw new UsageError("expected no arguments or -p W,D,L");
  const m = /^([0-9]{1,2}),([0-9]{1,2}),([0-9]{1,2})$/.exec(args[1]);
  if (!m) throw new UsageError(`malformed point values: ${args[1]}`);
  return { win: Number(m[1]), draw: Number(m[2]), loss: Number(m[3]) };
}

function parseResult(line: string): Match {
  const tokens = line.split(" ");
  if (tokens.some((t) => t === "")) throw new InputError("tokens must be separated by single spaces");
  const scoreIndexes = tokens.flatMap((t, i) => (SCORE.test(t) ? [i] : []));
  if (scoreIndexes.length !== 1) throw new InputError("expected exactly one score token");
  const s = scoreIndexes[0];
  const homeTokens = tokens.slice(0, s);
  const awayTokens = tokens.slice(s + 1);
  if (homeTokens.length === 0) throw new InputError("missing home team");
  if (awayTokens.length === 0) throw new InputError("missing away team");
  for (const t of [...homeTokens, ...awayTokens]) {
    if (!NAME_TOKEN.test(t)) throw new InputError(`invalid team name token: ${t}`);
  }
  const home = homeTokens.join(" ");
  const away = awayTokens.join(" ");
  if (home === away) throw new InputError(`team plays itself: ${home}`);
  const [, hg, ag] = SCORE.exec(tokens[s])!;
  return { home, away, homeGoals: Number(hg), awayGoals: Number(ag) };
}

function readMatches(): Match[] {
  const text = fs.readFileSync(0, "latin1");
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  const matches: Match[] = [];
  lines.forEach((raw, i) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (/^ *$/.test(line)) return;
    if (line.startsWith("#")) return;
    try {
      matches.push(parseResult(line));
    } catch (e) {
      if (e instanceof InputError) throw new InputError(`line ${i + 1}: ${e.message}`);
      throw e;
    }
  });
  return matches;
}

function buildTable(matches: Match[], points: Points): Team[] {
  const teams = new Map<string, Team>();
  const team = (name: string): Team => {
    let t = teams.get(name);
    if (!t) {
      t = { name, played: 0, won: 0, drawn: 0, lost: 0, goalsFor: 0, goalsAgainst: 0, points: 0, form: [] };
      teams.set(name, t);
    }
    return t;
  };
  const record = (t: Team, scored: number, conceded: number) => {
    t.played++;
    t.goalsFor += scored;
    t.goalsAgainst += conceded;
    const outcome: Outcome = scored > conceded ? "W" : scored < conceded ? "L" : "D";
    if (outcome === "W") t.won++;
    else if (outcome === "D") t.drawn++;
    else t.lost++;
    t.form.push(outcome);
    if (t.form.length > 5) t.form.shift();
  };
  for (const m of matches) {
    record(team(m.home), m.homeGoals, m.awayGoals);
    record(team(m.away), m.awayGoals, m.homeGoals);
  }
  for (const t of teams.values()) {
    t.points = t.won * points.win + t.drawn * points.draw + t.lost * points.loss;
  }
  return [...teams.values()];
}

/** Compares by (Pts, GD, GF, W), better first; 0 means fully tied. */
function compareRank(a: Team, b: Team): number {
  return (
    b.points - a.points ||
    b.goalsFor - b.goalsAgainst - (a.goalsFor - a.goalsAgainst) ||
    b.goalsFor - a.goalsFor ||
    b.won - a.won
  );
}

function formatTable(teams: Team[]): string {
  teams.sort((a, b) => compareRank(a, b) || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  const width = Math.max(...teams.map((t) => t.name.length));
  let position = 0;
  return teams
    .map((t, i) => {
      if (i === 0 || compareRank(teams[i - 1], t) !== 0) position = i + 1;
      const gd = t.goalsFor - t.goalsAgainst;
      const gdText = gd > 0 ? `+${gd}` : String(gd);
      return (
        String(position).padStart(2) +
        ". " +
        t.name.padEnd(width) +
        [t.played, t.won, t.drawn, t.lost].map((n) => String(n).padStart(3)).join("") +
        `${t.goalsFor}:${t.goalsAgainst}`.padStart(7) +
        gdText.padStart(4) +
        String(t.points).padStart(4) +
        " " +
        t.form.join("") +
        "\n"
      );
    })
    .join("");
}

function main(): number {
  try {
    const points = parseArgs(process.argv.slice(2));
    const matches = readMatches();
    process.stdout.write(formatTable(buildTable(matches, points)));
    return 0;
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`standings: ${e.message}\nusage: standings [-p W,D,L]\n`);
      return 2;
    }
    if (e instanceof InputError) {
      process.stderr.write(`standings: ${e.message}\n`);
      return 1;
    }
    throw e;
  }
}

process.exitCode = main();
