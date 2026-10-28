const [scheme, mode, ...values] = process.argv.slice(2);
if (!['luhn', 'isbn10', 'isbn13'].includes(scheme) || !['check', 'make'].includes(mode) || !values.length) {
  console.error('Invalid arguments'); process.exit(2);
}
function sum(digits: string): number {
  return [...digits].reduce((total, ch, i) => {
    let n = ch === 'X' ? 10 : Number(ch);
    if (scheme === 'isbn10') n *= 10 - i;
    else if (scheme === 'isbn13') n *= i % 2 ? 3 : 1;
    else if ((digits.length - i) % 2 === 0) { n *= 2; if (n > 9) n -= 9; }
    return total + n;
  }, 0);
}
let failed = false;
for (const value of values) {
  const digits = value.replaceAll('-', '');
  const lengthOK = scheme === 'luhn'
    ? digits.length >= (mode === 'check' ? 2 : 1) && digits.length <= (mode === 'check' ? 19 : 18)
    : digits.length === (scheme === 'isbn10' ? 10 : 13) - (mode === 'make' ? 1 : 0);
  const xOK = !digits.includes('X') || (scheme === 'isbn10' && mode === 'check' && /^[0-9]*X$/.test(digits));
  if (!/^[0-9X]+(-[0-9X]+)*$/.test(value) || !lengthOK || !xOK || (scheme === 'isbn13' && !/^97[89]/.test(digits))) {
    console.log(`${value} invalid`); failed = true; continue;
  }
  const modulus = scheme === 'isbn10' ? 11 : 10;
  if (mode === 'check') {
    const ok = sum(digits) % modulus === 0;
    console.log(`${value} ${ok ? 'ok' : 'bad'}`); if (!ok) failed = true;
  } else {
    const check = (modulus - sum(digits + '0') % modulus) % modulus;
    console.log(value + (value.includes('-') ? '-' : '') + (check === 10 ? 'X' : String(check)));
  }
}
process.exitCode = failed ? 1 : 0;
