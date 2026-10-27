const NUMBER = /^-?[0-9]{1,18}$/;
const COUNT = /^[0-9]{1,9}$/;

function usage(msg: string): never {
  process.stderr.write(`seqx: ${msg}\nusage: seqx [-s SEP] [-w] [-n COUNT] FIRST [STEP] LAST\n`);
  process.exit(2);
}

function format(v: bigint, width: number): string {
  const neg = v < 0n;
  const digits = (neg ? -v : v).toString();
  const total = digits.length + (neg ? 1 : 0);
  const zeros = "0".repeat(Math.max(0, width - total));
  return (neg ? "-" : "") + zeros + digits;
}

function main(args: string[]): void {
  let sep = "\n";
  let pad = false;
  let limit: number | null = null;
  const nums: bigint[] = [];

  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "-s") {
      if (i + 1 >= args.length) usage("-s needs a value");
      sep = args[++i];
    } else if (a === "-w") {
      pad = true;
    } else if (a === "-n") {
      if (i + 1 >= args.length) usage("-n needs a value");
      const v = args[++i];
      if (!COUNT.test(v)) usage(`bad count: ${v}`);
      limit = Number(v);
    } else {
      if (!NUMBER.test(a)) usage(`bad number: ${a}`);
      nums.push(BigInt(a));
    }
  }

  if (nums.length !== 2 && nums.length !== 3) usage("expected FIRST [STEP] LAST");
  const first = nums[0];
  const step = nums.length === 3 ? nums[1] : 1n;
  const last = nums[nums.length - 1];
  if (step === 0n) usage("step must not be zero");

  const values: bigint[] = [];
  for (let v = first; step > 0n ? v <= last : v >= last; v += step) {
    if (limit !== null && values.length >= limit) break;
    values.push(v);
  }
  if (values.length === 0) return;

  const width = pad ? Math.max(...values.map((v) => format(v, 0).length)) : 0;
  process.stdout.write(values.map((v) => format(v, width)).join(sep) + "\n");
}

main(process.argv.slice(2));
