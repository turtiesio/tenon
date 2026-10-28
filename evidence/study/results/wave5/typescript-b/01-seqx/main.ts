function usage(msg: string): never {
  process.stderr.write(`seqx: ${msg}\nusage: seqx [-s SEP] [-w] [-n COUNT] FIRST [STEP] LAST\n`);
  process.exit(2);
}

function main(argv: string[]): void {
  let sep = "\n";
  let pad = false;
  let limit: number | null = null;
  const nums: bigint[] = [];

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "-s" || arg === "-n") {
      if (i + 1 >= argv.length) usage(`option ${arg} requires a value`);
      const value = argv[++i];
      if (arg === "-s") {
        sep = value;
      } else {
        if (!/^[0-9]{1,9}$/.test(value)) usage(`invalid count: ${value}`);
        limit = Number(value);
      }
    } else if (arg === "-w") {
      pad = true;
    } else {
      if (!/^-?[0-9]{1,18}$/.test(arg)) usage(`invalid number: ${arg}`);
      nums.push(BigInt(arg));
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

  let formatted = values.map((v) => v.toString());
  if (pad) {
    const width = formatted.reduce((w, s) => Math.max(w, s.length), 0);
    formatted = formatted.map((s) =>
      s.startsWith("-") ? "-" + s.slice(1).padStart(width - 1, "0") : s.padStart(width, "0"),
    );
  }
  process.stdout.write(formatted.join(sep) + "\n");
}

main(process.argv.slice(2));
