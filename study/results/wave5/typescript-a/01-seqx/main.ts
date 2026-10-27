const args = process.argv.slice(2);
let separator = '\n';
let pad = false;
let limit = Infinity;
const numbers: bigint[] = [];
function usage(): never {
  console.error('Invalid arguments');
  process.exit(2);
}
for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (arg === '-w') pad = true;
  else if (arg === '-s') {
    if (++i === args.length) usage();
    separator = args[i];
  } else if (arg === '-n') {
    if (++i === args.length || !/^[0-9]{1,9}$/.test(args[i])) usage();
    limit = Number(args[i]);
  } else {
    if (!/^-?[0-9]{1,18}$/.test(arg)) usage();
    numbers.push(BigInt(arg));
  }
}
if (numbers.length !== 2 && numbers.length !== 3) usage();
const first = numbers[0];
const step = numbers.length === 3 ? numbers[1] : 1n;
const last = numbers[numbers.length - 1];
if (step === 0n) usage();
const values: string[] = [];
for (let value = first; (step > 0n ? value <= last : value >= last) && values.length < limit; value += step) {
  values.push(value.toString());
}
if (values.length) {
  const width = pad ? Math.max(...values.map(value => value.length)) : 0;
  const formatted = values.map(value => value.startsWith('-')
    ? '-' + value.slice(1).padStart(width - 1, '0')
    : value.padStart(width, '0'));
  process.stdout.write(formatted.join(separator) + '\n');
}
