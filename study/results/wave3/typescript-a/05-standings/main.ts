import { readFileSync } from 'node:fs';
const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== '-p' || !/^[0-9]{1,2},[0-9]{1,2},[0-9]{1,2}$/.test(args[1]))) { console.error('Invalid usage'); process.exit(2); }
const points = args.length ? args[1].split(',').map(Number) : [3, 1, 0];
type Team = { name: string; p: number; w: number; d: number; l: number; gf: number; ga: number; gd: number; pts: number; form: string };
const teams = new Map<string, Team>();
function update(name: string, gf: number, ga: number) {
  let team = teams.get(name);
  if (!team) { team = { name, p: 0, w: 0, d: 0, l: 0, gf: 0, ga: 0, gd: 0, pts: 0, form: '' }; teams.set(name, team); }
  const result = gf > ga ? 'W' : gf === ga ? 'D' : 'L';
  team.p++; team.gf += gf; team.ga += ga; team.gd = team.gf - team.ga;
  if (result === 'W') team.w++; else if (result === 'D') team.d++; else team.l++;
  team.pts += points[result === 'W' ? 0 : result === 'D' ? 1 : 2];
  team.form = (team.form + result).slice(-5);
}
readFileSync(0, 'utf8').split('\n').forEach((raw, lineNumber) => {
  const line = raw.endsWith('\r') ? raw.slice(0, -1) : raw;
  if (/^ *$/.test(line) || line.startsWith('#')) return;
  const tokens = line.split(' '), scores = tokens.map((t, i) => /^[0-9]{1,2}-[0-9]{1,2}$/.test(t) ? i : -1).filter(i => i >= 0);
  const index = scores[0];
  const home = tokens.slice(0, index).join(' '), away = tokens.slice(index + 1).join(' ');
  if (scores.length !== 1 || index === 0 || index === tokens.length - 1 || tokens.some((t, i) => i !== index && !/^[A-Za-z0-9.&']+$/.test(t)) || home === away) {
    console.error('Invalid result on line ' + (lineNumber + 1)); process.exit(1);
  }
  const [hg, ag] = tokens[index].split('-').map(Number);
  update(home, hg, ag); update(away, ag, hg);
});
const rank = (a: Team, b: Team) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf || b.w - a.w;
const ordered = [...teams.values()].sort((a, b) => rank(a, b) || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
const width = Math.max(0, ...ordered.map(t => t.name.length));
const pad = (value: string | number, width: number) => String(value).padStart(width);
let position = 0;
const output = ordered.map((team, i) => {
  if (!i || rank(team, ordered[i - 1]) !== 0) position = i + 1;
  return pad(position, 2) + '. ' + team.name.padEnd(width) + [team.p, team.w, team.d, team.l].map(n => pad(n, 3)).join('') + pad(team.gf + ':' + team.ga, 7) + pad(team.gd > 0 ? '+' + team.gd : team.gd, 4) + pad(team.pts, 4) + ' ' + team.form;
});
if (output.length) process.stdout.write(output.join('\n') + '\n');
