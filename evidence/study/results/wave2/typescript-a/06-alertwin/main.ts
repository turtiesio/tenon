import { readFileSync } from 'node:fs';

const args = process.argv.slice(2);
const options: Record<string, number> = { '-w': 60, '-t': 3, '-c': 300 };
for (let i = 0; i < args.length; i += 2) {
  const key = args[i];
  const value = args[i + 1];
  if (!Object.hasOwn(options, key) || !/^[0-9]{1,9}$/.test(value ?? '') || Number(value) < (key === '-c' ? 0 : 1)) process.exit(2);
  options[key] = Number(value);
}
type Service = { errors: number; warns: number; alerts: number; peak: number; times: number[]; head: number; lastAlert?: number };
const services = new Map<string, Service>();
let lastTime = -1, skipped = 0;
for (let line of readFileSync(0, 'utf8').split('\n')) {
  line = line.replace(/\r$/, '');
  if (/^ *$/.test(line)) continue;
  const match = /^([0-9]{1,12}) ([a-z][a-z0-9-]{0,31}) (INFO|WARN|ERROR)$/.exec(line);
  if (!match || Number(match[1]) < lastTime) { skipped++; continue; }
  const time = Number(match[1]);
  lastTime = time;
  const name = match[2];
  const service = services.get(name) ?? { errors: 0, warns: 0, alerts: 0, peak: 0, times: [], head: 0 };
  services.set(name, service);
  if (match[3] === 'WARN') service.warns++;
  if (match[3] !== 'ERROR') continue;
  service.errors++;
  service.times.push(time);
  while (service.times[service.head] <= time - options['-w']) service.head++;
  const count = service.times.length - service.head;
  service.peak = Math.max(service.peak, count);
  if (count >= options['-t'] && (service.lastAlert === undefined || time - service.lastAlert >= options['-c'])) {
    service.lastAlert = time;
    service.alerts++;
    console.log(`ALERT ${time} ${name} ${count}`);
  }
}
for (const name of [...services.keys()].sort()) {
  const service = services.get(name)!;
  console.log(`${name} errors=${service.errors} warns=${service.warns} alerts=${service.alerts} peak=${service.peak}`);
}
console.log(`skipped=${skipped}`);
