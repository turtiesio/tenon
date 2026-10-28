type Scheme = "luhn" | "isbn10" | "isbn13";
type Mode = "check" | "make";

const SCHEMES: readonly string[] = ["luhn", "isbn10", "isbn13"];
const MODES: readonly string[] = ["check", "make"];

// Allowed digit counts (inclusive) per scheme and mode.
const DIGIT_COUNTS: Record<Scheme, Record<Mode, [number, number]>> = {
  luhn: { check: [2, 19], make: [1, 18] },
  isbn10: { check: [10, 10], make: [9, 9] },
  isbn13: { check: [13, 13], make: [12, 12] },
};

// Returns the digit values of a well-formed value, or null if it is invalid.
function parseDigits(value: string, scheme: Scheme, mode: Mode): number[] | null {
  if (!/^[0-9X]+(-[0-9X]+)*$/.test(value)) return null;
  const chars = value.replaceAll("-", "");
  const xIndex = chars.indexOf("X");
  if (xIndex !== -1) {
    const allowed = scheme === "isbn10" && mode === "check" && xIndex === chars.length - 1;
    if (!allowed) return null;
  }
  const [min, max] = DIGIT_COUNTS[scheme][mode];
  if (chars.length < min || chars.length > max) return null;
  const digits = [...chars].map((c) => (c === "X" ? 10 : Number(c)));
  if (scheme === "isbn13" && !(digits[0] === 9 && digits[1] === 7 && (digits[2] === 8 || digits[2] === 9))) {
    return null;
  }
  return digits;
}

function luhnSum(digits: number[]): number {
  let sum = 0;
  for (let i = 0; i < digits.length; i++) {
    const d = digits[digits.length - 1 - i];
    if (i % 2 === 1) {
      const doubled = d * 2;
      sum += doubled > 9 ? doubled - 9 : doubled;
    } else {
      sum += d;
    }
  }
  return sum;
}

function isbn10Sum(digits: number[]): number {
  return digits.reduce((sum, d, i) => sum + (10 - i) * d, 0);
}

function isbn13Sum(digits: number[]): number {
  return digits.reduce((sum, d, i) => sum + (i % 2 === 0 ? 1 : 3) * d, 0);
}

function isCorrect(digits: number[], scheme: Scheme): boolean {
  switch (scheme) {
    case "luhn":
      return luhnSum(digits) % 10 === 0;
    case "isbn10":
      return isbn10Sum(digits) % 11 === 0;
    case "isbn13":
      return isbn13Sum(digits) % 10 === 0;
  }
}

function checkCharacter(digits: number[], scheme: Scheme): string {
  switch (scheme) {
    case "luhn": {
      // With the check digit appended, the existing digits move one position left.
      const s = luhnSum([...digits, 0]);
      return String((10 - (s % 10)) % 10);
    }
    case "isbn10": {
      const v = (11 - (isbn10Sum(digits) % 11)) % 11;
      return v === 10 ? "X" : String(v);
    }
    case "isbn13":
      return String((10 - (isbn13Sum(digits) % 10)) % 10);
  }
}

function main(): number {
  const [scheme, mode, ...values] = process.argv.slice(2);
  if (values.length === 0 || !SCHEMES.includes(scheme) || !MODES.includes(mode)) {
    process.stderr.write("usage: checkdigit (luhn|isbn10|isbn13) (check|make) VALUE...\n");
    return 2;
  }
  const s = scheme as Scheme;
  const m = mode as Mode;

  let allGood = true;
  const lines: string[] = [];
  for (const value of values) {
    const digits = parseDigits(value, s, m);
    if (digits === null) {
      lines.push(`${value} invalid`);
      allGood = false;
    } else if (m === "check") {
      const ok = isCorrect(digits, s);
      lines.push(`${value} ${ok ? "ok" : "bad"}`);
      if (!ok) allGood = false;
    } else {
      const sep = value.includes("-") ? "-" : "";
      lines.push(`${value}${sep}${checkCharacter(digits, s)}`);
    }
  }
  process.stdout.write(lines.map((l) => l + "\n").join(""));
  return allGood ? 0 : 1;
}

process.exitCode = main();
