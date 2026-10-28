import { readFileSync } from "node:fs";

const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const MAX_INPUT = 1_000_000;

class UsageError extends Error {}
class InvalidInput extends Error {}

function readStdin(): Uint8Array {
  let data: Uint8Array;
  try {
    data = readFileSync(0);
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "EOF") return new Uint8Array(0);
    throw e;
  }
  return data.length > MAX_INPUT ? data.subarray(0, MAX_INPUT) : data;
}

function encode(data: Uint8Array): string {
  let out = "";
  for (let i = 0; i < data.length; i += 3) {
    const rest = data.length - i;
    const n = (data[i] << 16) | ((data[i + 1] ?? 0) << 8) | (data[i + 2] ?? 0);
    out += ALPHABET[(n >> 18) & 63] + ALPHABET[(n >> 12) & 63];
    out += rest >= 2 ? ALPHABET[(n >> 6) & 63] : "=";
    out += rest >= 3 ? ALPHABET[n & 63] : "=";
  }
  return out;
}

function wrap(text: string, width: number): string {
  if (text.length === 0) return "";
  if (width === 0) return text + "\n";
  let out = "";
  for (let i = 0; i < text.length; i += width) {
    out += text.slice(i, i + width) + "\n";
  }
  return out;
}

function decode(raw: Uint8Array): Uint8Array {
  // Work on a latin1 string: any non-ASCII byte is simply not in the alphabet.
  const text = Buffer.from(raw).toString("latin1").replace(/[\r\n]/g, "");
  if (text.length % 4 !== 0) throw new InvalidInput("length is not a multiple of 4");
  if (!/^[A-Za-z0-9+/]*(={0,2})$/.test(text)) throw new InvalidInput("invalid character or padding");

  const pad = text.length - text.replace(/=+$/, "").length;
  const out = new Uint8Array((text.length / 4) * 3 - pad);
  let o = 0;
  for (let i = 0; i < text.length; i += 4) {
    const v = [0, 1, 2, 3].map((k) => {
      const c = text[i + k];
      return c === "=" ? 0 : ALPHABET.indexOf(c);
    });
    const last = i + 4 === text.length;
    const groupPad = last ? pad : 0;
    if (groupPad === 2 && (v[1] & 0x0f) !== 0) throw new InvalidInput("non-zero unused bits");
    if (groupPad === 1 && (v[2] & 0x03) !== 0) throw new InvalidInput("non-zero unused bits");
    const n = (v[0] << 18) | (v[1] << 12) | (v[2] << 6) | v[3];
    out[o++] = (n >> 16) & 255;
    if (groupPad < 2) out[o++] = (n >> 8) & 255;
    if (groupPad < 1) out[o++] = n & 255;
  }
  return out;
}

function parseArgs(args: string[]): { decode: boolean; width: number } {
  let decodeMode = false;
  let width = 76;
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-d") {
      decodeMode = true;
    } else if (arg === "-w") {
      const value = args[++i];
      if (value === undefined || !/^[0-9]{1,4}$/.test(value)) {
        throw new UsageError("-w needs a width of 1 to 4 digits");
      }
      width = Number(value);
    } else {
      throw new UsageError(`unexpected argument '${arg}'`);
    }
  }
  return { decode: decodeMode, width };
}

function main(): number {
  let opts;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (!(e instanceof UsageError)) throw e;
    process.stderr.write(`b64: ${e.message}\nusage: b64 [-d] [-w N]\n`);
    return 2;
  }
  const input = readStdin();
  if (opts.decode) {
    try {
      process.stdout.write(decode(input));
    } catch (e) {
      if (!(e instanceof InvalidInput)) throw e;
      process.stderr.write(`b64: invalid input: ${e.message}\n`);
      return 1;
    }
  } else {
    process.stdout.write(wrap(encode(input), opts.width));
  }
  return 0;
}

process.exitCode = main();
