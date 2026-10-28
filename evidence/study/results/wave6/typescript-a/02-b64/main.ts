import { readFileSync } from 'node:fs';
const args = process.argv.slice(2);
let decode = false, width = 76;
function usage(): never { console.error('Usage: b64 [-d] [-w N]'); process.exit(2); }
for (let i = 0; i < args.length; i++) {
  if (args[i] === '-d') decode = true;
  else if (args[i] === '-w') {
    const value = args[++i];
    if (value === undefined || !/^[0-9]{1,4}$/.test(value)) usage();
    width = Number(value);
  } else usage();
}
const input = readFileSync(0);
if (decode) {
  const text = input.toString('latin1').replace(/[\r\n]/g, '');
  const bytes = Buffer.from(text, 'base64');
  if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(text) || bytes.toString('base64') !== text) {
    console.error('Invalid Base64'); process.exit(1);
  }
  process.stdout.write(bytes);
} else {
  const text = input.toString('base64');
  if (text.length) {
    const step = width || text.length;
    for (let i = 0; i < text.length; i += step) process.stdout.write(text.slice(i, i + step) + '\n');
  }
}
