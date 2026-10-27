const args = process.argv.slice(2);
let format = '%Y-%m-%d';
while (args[0]?.startsWith('-')) {
  if (args.shift() !== '-F' || !args.length) process.exit(2);
  format = args.shift()!;
}
const command = args.shift();
if (!command || !['weekday', 'add', 'diff', 'addmonths'].includes(command) || args.length !== (command === 'weekday' ? 1 : 2)) process.exit(2);
if ((command === 'add' || command === 'addmonths') && !/^-?[0-9]{1,7}$/.test(args[1])) process.exit(2);
for (let i = 0; i < format.length; i++) {
  if (format[i] === '%' && !'Ymdjab%'.includes(format[++i] ?? '\0')) process.exit(2);
}
const dayMs = 86400000;
function makeDate(year: number, month: number, day: number): Date {
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  return date;
}
function parseDate(text: string): Date {
  if (!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(text)) process.exit(1);
  const [year, month, day] = text.split('-').map(Number);
  const date = makeDate(year, month, day);
  if (year < 1 || date.getUTCFullYear() !== year || date.getUTCMonth() + 1 !== month || date.getUTCDate() !== day) process.exit(1);
  return date;
}
let date = parseDate(args[0]);
const weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
if (command === 'weekday') console.log(weekdays[date.getUTCDay()]);
else if (command === 'diff') console.log((parseDate(args[1]).getTime() - date.getTime()) / dayMs);
else {
  const n = Number(args[1]);
  if (command === 'add') date = new Date(date.getTime() + n * dayMs);
  else {
    const months = (date.getUTCFullYear() - 1) * 12 + date.getUTCMonth() + n;
    if (months < 0 || months >= 9999 * 12) process.exit(1);
    const year = Math.floor(months / 12) + 1;
    const month = months % 12 + 1;
    const last = makeDate(year, month + 1, 0).getUTCDate();
    date = makeDate(year, month, Math.min(date.getUTCDate(), last));
  }
  const year = date.getUTCFullYear();
  if (year < 1 || year > 9999) process.exit(1);
  const pad = (n: number, length: number) => String(n).padStart(length, '0');
  const replacements: Record<string, string> = {
    Y: pad(year, 4),
    m: pad(date.getUTCMonth() + 1, 2),
    d: pad(date.getUTCDate(), 2),
    j: pad((date.getTime() - makeDate(year, 1, 1).getTime()) / dayMs + 1, 3),
    a: weekdays[date.getUTCDay()].slice(0, 3),
    b: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][date.getUTCMonth()],
    '%': '%',
  };
  console.log(format.replace(/%(.)/g, (_, directive: string) => replacements[directive]));
}
