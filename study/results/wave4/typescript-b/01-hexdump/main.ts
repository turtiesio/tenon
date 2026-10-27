import * as fs from "node:fs";

function usage(msg: string): never {
  process.stderr.write(`hexdump: ${msg}\nusage: hexdump [-s SKIP] [-n LENGTH] [-w WIDTH] [FILE]\n`);
  process.exit(2);
}

interface Options {
  skip: number;
  length: number | null;
  width: number;
  file: string | null;
}

function parseArgs(args: string[]): Options {
  const opts: Options = { skip: 0, length: null, width: 16, file: null };
  let fileSeen = false;
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-s" || arg === "-n" || arg === "-w") {
      if (i + 1 >= args.length) usage(`option ${arg} requires a value`);
      const value = args[++i];
      if (arg === "-w") {
        if (!/^[0-9]{1,2}$/.test(value)) usage(`invalid width: ${value}`);
        const w = Number(value);
        if (w < 1 || w > 32) usage(`width out of range: ${value}`);
        opts.width = w;
      } else {
        if (!/^[0-9]{1,9}$/.test(value)) usage(`invalid value for ${arg}: ${value}`);
        if (arg === "-s") opts.skip = Number(value);
        else opts.length = Number(value);
      }
    } else if (arg.startsWith("-") && arg !== "-") {
      usage(`unknown option: ${arg}`);
    } else {
      if (fileSeen) usage("more than one file given");
      fileSeen = true;
      opts.file = arg === "-" ? null : arg;
    }
  }
  return opts;
}

function readInput(file: string | null): Buffer {
  try {
    return fs.readFileSync(file ?? 0);
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err);
    process.stderr.write(`hexdump: cannot read ${file ?? "stdin"}: ${reason}\n`);
    process.exit(1);
  }
}

function hex(n: number, digits: number): string {
  return n.toString(16).padStart(digits, "0");
}

function main(): void {
  const opts = parseArgs(process.argv.slice(2));
  const input = readInput(opts.file);
  const start = Math.min(opts.skip, input.length);
  const end = opts.length === null ? input.length : Math.min(input.length, start + opts.length);
  const bytes = input.subarray(start, end);

  const lines: string[] = [];
  for (let pos = 0; pos < bytes.length; pos += opts.width) {
    const chunk = bytes.subarray(pos, pos + opts.width);
    const fields: string[] = [];
    let ascii = "";
    for (let k = 0; k < opts.width; k++) {
      if (k < chunk.length) {
        const b = chunk[k];
        fields.push(hex(b, 2));
        ascii += b >= 0x20 && b <= 0x7e ? String.fromCharCode(b) : ".";
      } else {
        fields.push("  ");
      }
    }
    lines.push(`${hex(opts.skip + pos, 8)}  ${fields.join(" ")}  |${ascii}|\n`);
  }
  lines.push(`${hex(opts.skip + bytes.length, 8)}\n`);
  process.stdout.write(lines.join(""));
}

main();
