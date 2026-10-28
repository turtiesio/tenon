import { readFileSync } from 'node:fs';
const args = process.argv.slice(2);
if (args.length > 1 || (args.length === 1 && args[0] !== '-y')) { console.error('Usage: climate [-y]'); process.exit(2); }
const stations = new Map<string, Map<string, number>>();
let skipped = 0, replaced = 0;
function validDate(text: string): boolean {
  if (!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(text)) return false;
  const [year, month, day] = text.split('-').map(Number);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1];
}
for (const raw of readFileSync(0, 'utf8').split('\n')) {
  const line = raw.replace(/\r$/, '');
  if (line === '') continue;
  const fields = line.split(';');
  const [station, date, temperature] = fields;
  if (fields.length !== 3 || [...station].length < 1 || [...station].length > 40 || station.startsWith(' ') || station.endsWith(' ') || !validDate(date) || !/^-?[0-9]{1,2}\.[0-9]$/.test(temperature)) { skipped++; continue; }
  const readings = stations.get(station) ?? new Map<string, number>();
  if (readings.has(date)) replaced++;
  readings.set(date, Number(temperature.replace('.', '')));
  stations.set(station, readings);
}
function format(t: number): string { return `${t < 0 ? '-' : ''}${Math.floor(Math.abs(t) / 10)}.${Math.abs(t) % 10}`; }
let used = 0;
for (const station of [...stations.keys()].sort((a, b) => Buffer.compare(Buffer.from(a), Buffer.from(b)))) {
  const groups = new Map<string, number[]>();
  for (const [date, temp] of stations.get(station)!) {
    const period = date.slice(0, args.length ? 4 : 7);
    const group = groups.get(period) ?? [];
    group.push(temp); groups.set(period, group); used++;
  }
  for (const period of [...groups.keys()].sort()) {
    const values = groups.get(period)!;
    const sum = values.reduce((a, b) => a + b, 0);
    const mean = Math.sign(sum) * Math.floor((2 * Math.abs(sum) + values.length) / (2 * values.length));
    console.log(`${station} ${period} days=${values.length} min=${format(Math.min(...values))} max=${format(Math.max(...values))} mean=${format(mean)}`);
  }
}
console.log(`readings=${used} skipped=${skipped} replaced=${replaced}`);
