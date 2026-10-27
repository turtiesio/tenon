import * as fs from "node:fs";

class UsageError extends Error {}

interface Options {
  skip: number;
  length: number | null;
  width: number;
  file: string | null;
}

function parseArgs(args: string[]): Options {
  const opts: Options = { skip: 0, length: null, width: 16, file: null };
  let i = 0;
  while (i < args.length) {
    const arg = args[i++];
    if (arg === "-s" || arg === "-n" || arg === "-w") {
      if (i >= args.length) throw new UsageError(`option ${arg} needs a value`);
      const value = args[i++];
      if (arg === "-w") {
        if (!/^[0-9]{1,2}$/.test(value)) throw new UsageError(`bad width: ${value}`);
        const w = Number(value);
        if (w < 1 || w > 32) throw new UsageError(`width out of range: ${value}`);
        opts.width = w;
      } else {
        if (!/^[0-9]{1,9}$/.test(value)) throw new UsageError(`bad value for ${arg}: ${value}`);
        if (arg === "-s") opts.skip = Number(value);
        else opts.length = Number(value);
      }
    } else if (arg !== "-" && arg.startsWith("-")) {
      throw new UsageError(`unknown option: ${arg}`);
    } else {
      if (opts.file !== null) throw new UsageError("more than one FILE");
      opts.file = arg;
    }
  }
  return opts;
}

function hex(n: number, digits: number): string {
  return n.toString(16).padStart(digits, "0");
}

function dump(data: Buffer, opts: Options): string {
  const start = Math.min(opts.skip, data.length);
  let end = data.length;
  if (opts.length !== null) end = Math.min(end, start + opts.length);
  const out: string[] = [];
  for (let pos = start; pos < end; pos += opts.width) {
    const chunk = data.subarray(pos, Math.min(pos + opts.width, end));
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
    out.push(`${hex(pos, 8)}  ${fields.join(" ")}  |${ascii}|\n`);
  }
  // Final line: SKIP plus the number of bytes dumped.
  out.push(`${hex(opts.skip + Math.max(0, end - start), 8)}\n`);
  return out.join("");
}

function main(): number {
  let opts: Options;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (e) {
    if (e instanceof UsageError) {
      console.error(`hexdump: ${e.message}`);
      return 2;
    }
    throw e;
  }
  let data: Buffer;
  try {
    data = fs.readFileSync(opts.file === null || opts.file === "-" ? 0 : opts.file);
  } catch (e) {
    const err = e as NodeJS.ErrnoException;
    if (opts.file === null || opts.file === "-") {
      if (err.code === "EOF") {
        data = Buffer.alloc(0);
        process.stdout.write(dump(data, opts));
        return 0;
      }
    }
    console.error(`hexdump: cannot read ${opts.file ?? "stdin"}: ${err.message}`);
    return 1;
  }
  process.stdout.write(dump(data, opts));
  return 0;
}

process.exitCode = main();
