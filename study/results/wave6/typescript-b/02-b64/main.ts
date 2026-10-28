import * as fs from "node:fs";

const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const VALUES = new Map<number, number>();
for (let i = 0; i < ALPHABET.length; i++) VALUES.set(ALPHABET.charCodeAt(i), i);
const PAD = 0x3d; // '='

function encode(data: Uint8Array): string {
  let out = "";
  let i = 0;
  for (; i + 3 <= data.length; i += 3) {
    const n = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2];
    out += ALPHABET[(n >> 18) & 63] + ALPHABET[(n >> 12) & 63] + ALPHABET[(n >> 6) & 63] + ALPHABET[n & 63];
  }
  const rest = data.length - i;
  if (rest === 1) {
    const n = data[i] << 16;
    out += ALPHABET[(n >> 18) & 63] + ALPHABET[(n >> 12) & 63] + "==";
  } else if (rest === 2) {
    const n = (data[i] << 16) | (data[i + 1] << 8);
    out += ALPHABET[(n >> 18) & 63] + ALPHABET[(n >> 12) & 63] + ALPHABET[(n >> 6) & 63] + "=";
  }
  return out;
}

function wrap(text: string, width: number): string {
  if (text.length === 0) return "";
  if (width === 0) return text + "\n";
  const lines: string[] = [];
  for (let i = 0; i < text.length; i += width) lines.push(text.slice(i, i + width));
  return lines.join("\n") + "\n";
}

/** Strictly decodes Base64; returns null if the text is not canonical. */
function decode(input: Uint8Array): Buffer | null {
  const text = input.filter((b) => b !== 0x0a && b !== 0x0d);
  if (text.length % 4 !== 0) return null;
  const out: number[] = [];
  for (let g = 0; g < text.length; g += 4) {
    const isLast = g + 4 === text.length;
    const c = text.subarray(g, g + 4);
    let pads = 0;
    if (c[3] === PAD) pads = c[2] === PAD ? 2 : 1;
    if (pads > 0 && !isLast) return null;
    const vals: number[] = [];
    for (let k = 0; k < 4 - pads; k++) {
      const v = VALUES.get(c[k]);
      if (v === undefined) return null;
      vals.push(v);
    }
    if (pads === 2) {
      if ((vals[1] & 0x0f) !== 0) return null;
      out.push((vals[0] << 2) | (vals[1] >> 4));
    } else if (pads === 1) {
      if ((vals[2] & 0x03) !== 0) return null;
      const n = (vals[0] << 18) | (vals[1] << 12) | (vals[2] << 6);
      out.push((n >> 16) & 255, (n >> 8) & 255);
    } else {
      const n = (vals[0] << 18) | (vals[1] << 12) | (vals[2] << 6) | vals[3];
      out.push((n >> 16) & 255, (n >> 8) & 255, n & 255);
    }
  }
  return Buffer.from(out);
}

function usage(msg: string): number {
  process.stderr.write(`b64: ${msg}\nusage: b64 [-d] [-w N]\n`);
  return 2;
}

function main(): number {
  const args = process.argv.slice(2);
  let decodeMode = false;
  let width = 76;
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-d") {
      decodeMode = true;
    } else if (arg === "-w") {
      const value = args[++i];
      if (value === undefined) return usage("option -w requires an argument");
      if (!/^[0-9]{1,4}$/.test(value)) return usage(`invalid width '${value}'`);
      width = Number(value);
    } else {
      return usage(`unexpected argument '${arg}'`);
    }
  }

  const input = fs.readFileSync(0);
  if (decodeMode) {
    const bytes = decode(input);
    if (bytes === null) {
      process.stderr.write("b64: invalid Base64 input\n");
      return 1;
    }
    process.stdout.write(bytes);
  } else {
    process.stdout.write(wrap(encode(input), width));
  }
  return 0;
}

process.exitCode = main();
