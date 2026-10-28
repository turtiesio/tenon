type Scheme = "luhn" | "isbn10" | "isbn13";
type Mode = "check" | "make";

const DIGIT_COUNTS: Record<Scheme, Record<Mode, [number, number]>> = {
  luhn: { check: [2, 19], make: [1, 18] },
  isbn10: { check: [10, 10], make: [9, 9] },
  isbn13: { check: [13, 13], make: [12, 12] },
};

function usage(message: string): never {
  process.stderr.write(`checkdigit: ${message}\nusage: checkdigit luhn|isbn10|isbn13 check|make VALUE...\n`);
  process.exit(2);
}

/** Returns the digit values of a well-formed value, or null if it is invalid. */
function parseDigits(value: string, scheme: Scheme, mode: Mode): number[] | null {
  if (!/^[0-9X]+(-[0-9X]+)*$/.test(value)) return null;
  const xIndex = value.indexOf("X");
  if (xIndex !== -1) {
    const allowed = scheme === "isbn10" && mode === "check" && xIndex === value.length - 1;
    if (!allowed) return null;
  }
  const digits = [...value.replaceAll("-", "")].map((c) => (c === "X" ? 10 : Number(c)));
  const [min, max] = DIGIT_COUNTS[scheme][mode];
  if (digits.length < min || digits.length > max) return null;
  if (scheme === "isbn13") {
    const prefix = digits.slice(0, 3).join("");
    if (prefix !== "978" && prefix !== "979") return null;
  }
  return digits;
}

function luhnSum(digits: number[]): number {
  let sum = 0;
  for (let i = 0; i < digits.length; i++) {
    const position = digits.length - i; // 1 for the rightmost digit
    let d = digits[i];
    if (position % 2 === 0) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
  }
  return sum;
}

function isbn10Sum(digits: number[]): number {
  return digits.reduce((sum, d, i) => sum + (10 - i) * d, 0);
}

function isbn13Sum(digits: number[]): number {
  return digits.reduce((sum, d, i) => sum + (i % 2 === 0 ? 1 : 3) * d, 0);
}

function isCorrect(scheme: Scheme, digits: number[]): boolean {
  switch (scheme) {
    case "luhn":
      return luhnSum(digits) % 10 === 0;
    case "isbn10":
      return isbn10Sum(digits) % 11 === 0;
    case "isbn13":
      return isbn13Sum(digits) % 10 === 0;
  }
}

function checkCharacter(scheme: Scheme, digits: number[]): string {
  switch (scheme) {
    case "luhn": {
      for (let c = 0; c <= 9; c++) {
        if (luhnSum([...digits, c]) % 10 === 0) return String(c);
      }
      throw new Error("unreachable: no Luhn check digit");
    }
    case "isbn10": {
      const check = (11 - (isbn10Sum(digits) % 11)) % 11;
      return check === 10 ? "X" : String(check);
    }
    case "isbn13":
      return String((10 - (isbn13Sum(digits) % 10)) % 10);
  }
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length < 3) usage("expected SCHEME, MODE and at least one VALUE");
  const [scheme, mode, ...values] = args;
  if (scheme !== "luhn" && scheme !== "isbn10" && scheme !== "isbn13") usage(`unknown scheme: ${scheme}`);
  if (mode !== "check" && mode !== "make") usage(`unknown mode: ${mode}`);

  let allOk = true;
  const lines: string[] = [];
  for (const value of values) {
    const digits = parseDigits(value, scheme, mode);
    if (digits === null) {
      lines.push(`${value} invalid`);
      allOk = false;
    } else if (mode === "check") {
      const ok = isCorrect(scheme, digits);
      lines.push(`${value} ${ok ? "ok" : "bad"}`);
      if (!ok) allOk = false;
    } else {
      const sep = value.includes("-") ? "-" : "";
      lines.push(value + sep + checkCharacter(scheme, digits));
    }
  }
  process.stdout.write(lines.map((l) => l + "\n").join(""));
  process.exitCode = allOk ? 0 : 1;
}

main();
