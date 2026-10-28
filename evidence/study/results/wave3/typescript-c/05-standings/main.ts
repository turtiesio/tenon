import { readFileSync } from "node:fs";

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

interface Team {
  name: string;
  won: number;
  drawn: number;
  lost: number;
  goalsFor: number;
  goalsAgainst: number;
  form: string[];
}

const SCORE = /^[0-9]{1,2}-[0-9]{1,2}$/;
const NAME_TOKEN = /^[A-Za-z0-9.&']+$/;

function parseArgs(args: string[]): Points {
  if (args.length === 0) return { win: 3, draw: 1, loss: 0 };
  if (args.length !== 2 || args[0] !== "-p") throw new UsageError("usage: standings [-p W,D,L]");
  const parts = args[1].split(",");
  if (parts.length !== 3 || !parts.every((p) => /^[0-9]{1,2}$/.test(p))) {
    throw new UsageError(`bad point values: ${args[1]}`);
  }
  const [win, draw, loss] = parts.map(Number);
  return { win, draw, loss };
}

function parseMatch(line: string): Match | null {
  const tokens = line.split(" ");
  const scoreAt = tokens.flatMap((t, i) => (SCORE.test(t) ? [i] : []));
  if (scoreAt.length !== 1) return null;
  const at = scoreAt[0];
  if (at === 0 || at === tokens.length - 1) return null;
  const nameTokens = [...tokens.slice(0, at), ...tokens.slice(at + 1)];
  if (!nameTokens.every((t) => NAME_TOKEN.test(t))) return null;
  const home = tokens.slice(0, at).join(" ");
  const away = tokens.slice(at + 1).join(" ");
  if (home === away) return null;
  const [homeGoals, awayGoals] = tokens[at].split("-").map(Number);
  return { home, away, homeGoals, awayGoals };
}

function parseInput(text: string): Match[] {
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  const matches: Match[] = [];
  lines.forEach((raw, index) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line.trim() === "" || line.startsWith("#")) return;
    const match = parseMatch(line);
    if (match === null) throw new InputError(`line ${index + 1}: invalid result`);
    matches.push(match);
  });
  return matches;
}

function tally(matches: Match[]): Team[] {
  const teams = new Map<string, Team>();
  const team = (name: string): Team => {
    let t = teams.get(name);
    if (!t) {
      t = { name, won: 0, drawn: 0, lost: 0, goalsFor: 0, goalsAgainst: 0, form: [] };
      teams.set(name, t);
    }
    return t;
  };
  const record = (t: Team, gf: number, ga: number) => {
    t.goalsFor += gf;
    t.goalsAgainst += ga;
    const result = gf > ga ? "W" : gf < ga ? "L" : "D";
    if (result === "W") t.won++;
    else if (result === "L") t.lost++;
    else t.drawn++;
    t.form.push(result);
  };
  for (const m of matches) {
    record(team(m.home), m.homeGoals, m.awayGoals);
    record(team(m.away), m.awayGoals, m.homeGoals);
  }
  return [...teams.values()];
}

function render(teams: Team[], points: Points): string {
  const rows = teams.map((t) => ({
    team: t,
    pts: t.won * points.win + t.drawn * points.draw + t.lost * points.loss,
    gd: t.goalsFor - t.goalsAgainst,
  }));
  type Row = (typeof rows)[number];
  const key = (r: Row) => [r.pts, r.gd, r.team.goalsFor, r.team.won];
  const compareKeys = (a: Row, b: Row): number => {
    const ka = key(a);
    const kb = key(b);
    for (let i = 0; i < ka.length; i++) {
      if (ka[i] !== kb[i]) return kb[i] - ka[i];
    }
    return 0;
  };
  rows.sort((a, b) => compareKeys(a, b) || (a.team.name < b.team.name ? -1 : a.team.name > b.team.name ? 1 : 0));

  const width = Math.max(0, ...rows.map((r) => r.team.name.length));
  const num = (n: number | string, w: number) => String(n).padStart(w);
  let out = "";
  for (const row of rows) {
    const t = row.team;
    const position = 1 + rows.filter((other) => compareKeys(other, row) < 0).length;
    const gd = row.gd > 0 ? `+${row.gd}` : String(row.gd);
    out +=
      `${num(position, 2)}. ${t.name.padEnd(width)}` +
      num(t.form.length, 3) +
      num(t.won, 3) +
      num(t.drawn, 3) +
      num(t.lost, 3) +
      num(`${t.goalsFor}:${t.goalsAgainst}`, 7) +
      num(gd, 4) +
      num(row.pts, 4) +
      ` ${t.form.slice(-5).join("")}\n`;
  }
  return out;
}

function main(): number {
  try {
    const points = parseArgs(process.argv.slice(2));
    const matches = parseInput(readFileSync(0).toString("latin1"));
    process.stdout.write(render(tally(matches), points));
    return 0;
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`standings: ${e.message}\n`);
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
