import fs from 'node:fs';
if (process.argv.length > 2) { console.error('No arguments expected'); process.exit(2); }
const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
type Punch = {time: number; kind: string};
const employees = new Map<string, Punch[][]>();
let skipped = 0;
for (const raw of fs.readFileSync(0, 'utf8').split('\n')) {
  const line = raw.replace(/\r$/, '');
  if (/^ *$/.test(line)) continue;
  const match = /^([a-z]{1,16}) (Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([0-9]{2}):([0-9]{2}) (IN|OUT)$/.exec(line);
  if (!match || Number(match[3]) > 23 || Number(match[4]) > 59) { skipped++; continue; }
  const [, name, day, hour, minute, kind] = match;
  if (!employees.has(name)) employees.set(name, days.map(() => []));
  employees.get(name)![days.indexOf(day)].push({time: Number(hour) * 60 + Number(minute), kind});
}
const format = (minutes: number) => `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}`;
for (const name of [...employees.keys()].sort()) {
  let total = 0, overtime = 0, anomalies = 0;
  const parts = [name];
  employees.get(name)!.forEach((punches, day) => {
    punches.sort((a, b) => a.time - b.time);
    let open: number | undefined, minutes = 0;
    for (const punch of punches) {
      if (punch.kind === 'IN') { if (open !== undefined) anomalies++; open = punch.time; }
      else if (open === undefined) anomalies++;
      else { minutes += punch.time - open; open = undefined; }
    }
    if (open !== undefined) anomalies++;
    total += minutes; overtime += Math.max(0, minutes - 480);
    if (minutes > 0) parts.push(`${days[day]}=${format(minutes)}`);
  });
  parts.push(`total=${format(total)}`, `overtime=${format(overtime)}`, `anomalies=${anomalies}`);
  console.log(parts.join(' '));
}
console.log(`skipped=${skipped}`);
