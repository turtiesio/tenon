function usage(): never { console.error('Invalid usage'); process.exit(2); }
const args = process.argv.slice(2), values: string[] = [];
const options: Record<string, number> = { '-f': 10, '-t': 10, '-w': 0, '-g': 0 };
let upper = false;
for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (arg === '-u') upper = true;
  else if (Object.hasOwn(options, arg)) {
    const value = args[++i];
    if (value === undefined || !/^[0-9]{1,2}$/.test(value)) usage();
    const n = Number(value), base = arg === '-f' || arg === '-t';
    if (n < (base ? 2 : 1) || n > (base ? 36 : 64)) usage();
    options[arg] = n;
  } else values.push(arg);
}
if (!values.length) usage();
for (const value of values) {
  let n = 0n, valid = /^-?[0-9a-z]+$/i.test(value);
  const negative = value.startsWith('-');
  if (valid) for (const char of (negative ? value.slice(1) : value).toLowerCase()) {
    const digit = '0123456789abcdefghijklmnopqrstuvwxyz'.indexOf(char);
    if (digit >= options['-f']) { valid = false; break; }
    n = n * BigInt(options['-f']) + BigInt(digit);
    if (n > 9223372036854775807n) { valid = false; break; }
  }
  if (!valid) { console.error('Invalid value: ' + value); process.exitCode = 1; continue; }
  let digits = n.toString(options['-t']).padStart(options['-w'], '0');
  if (upper) digits = digits.toUpperCase();
  const group = options['-g'];
  if (group) {
    const chunks: string[] = [];
    for (let end = digits.length; end > 0; end -= group) chunks.unshift(digits.slice(Math.max(0, end - group), end));
    digits = chunks.join('_');
  }
  console.log((negative && n !== 0n ? '-' : '') + digits);
}
