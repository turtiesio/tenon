import * as fs from "node:fs";

const SIZE_RE = /^[0-9]{1,16}$/;
const BINARY_UNITS = ["KiB", "MiB", "GiB", "TiB", "PiB"];
const DECIMAL_UNITS = ["kB", "MB", "GB", "TB", "PB"];

function format(value: bigint, si: boolean, places: number): string {
  const base = si ? 1000n : 1024n;
  const units = si ? DECIMAL_UNITS : BINARY_UNITS;
  if (value < base) return `${value} B`;
  let k = 1;
  while (k < 5 && value >= base ** BigInt(k + 1)) k++;
  const scale = 10n ** BigInt(places);
  let r: bigint;
  for (;;) {
    const divisor = base ** BigInt(k);
    r = (2n * value * scale + divisor) / (2n * divisor);
    if (r >= base * scale && k < 5) {
      k++;
    } else {
      break;
    }
  }
  let text = String(r / scale);
  if (places > 0) text += "." + String(r % scale).padStart(places, "0");
  return `${text} ${units[k - 1]}`;
}

function usage(msg: string): number {
  process.stderr.write(`hsize: ${msg}\nusage: hsize [-s] [-p N] [SIZE...]\n`);
  return 2;
}

function main(): number {
  const args = process.argv.slice(2);
  let si = false;
  let places = 1;
  const sizes: bigint[] = [];
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-s") {
      si = true;
    } else if (arg === "-p") {
      const value = args[++i];
      if (value === undefined) return usage("option -p requires an argument");
      if (value !== "0" && value !== "1" && value !== "2") return usage(`invalid precision '${value}'`);
      places = Number(value);
    } else if (SIZE_RE.test(arg)) {
      sizes.push(BigInt(arg));
    } else {
      return usage(`invalid argument '${arg}'`);
    }
  }

  const out: string[] = [];
  let status = 0;
  if (sizes.length > 0) {
    for (const size of sizes) out.push(format(size, si, places));
  } else {
    const text = fs.readFileSync(0, "latin1");
    const lines = text.split("\n");
    if (lines[lines.length - 1] === "") lines.pop();
    for (let line of lines) {
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (SIZE_RE.test(line)) {
        out.push(format(BigInt(line), si, places));
      } else {
        out.push("?");
        status = 1;
      }
    }
  }
  process.stdout.write(out.map((l) => l + "\n").join(""));
  return status;
}

process.exitCode = main();
