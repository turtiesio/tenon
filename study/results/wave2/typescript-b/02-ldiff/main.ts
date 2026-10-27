import * as fs from "node:fs";

interface Options {
  ignoreCase: boolean;
  ignoreTrailing: boolean;
  quiet: boolean;
  summary: boolean;
}

// Files are read as latin1 so that each byte maps to one char and is written back unchanged.
function readLines(path: string): string[] {
  const text = fs.readFileSync(path, "latin1");
  if (text === "") {
    return [];
  }
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") {
    lines.pop();
  }
  return lines;
}

function comparisonKey(line: string, options: Options): string {
  let key = line;
  if (options.ignoreTrailing) {
    key = key.replace(/[ \t]+$/, "");
  }
  if (options.ignoreCase) {
    key = key.replace(/[A-Z]/g, (c) => c.toLowerCase());
  }
  return key;
}

type Step = { kind: "common" | "delete" | "insert"; text: string };

function diff(a: string[], b: string[], options: Options): Step[] {
  const keysA = a.map((line) => comparisonKey(line, options));
  const keysB = b.map((line) => comparisonKey(line, options));
  const n = a.length;
  const m = b.length;
  const width = m + 1;
  const table = new Int32Array((n + 1) * width);
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      if (keysA[i] === keysB[j]) {
        table[i * width + j] = table[(i + 1) * width + j + 1] + 1;
      } else {
        table[i * width + j] = Math.max(table[(i + 1) * width + j], table[i * width + j + 1]);
      }
    }
  }

  const steps: Step[] = [];
  let i = 0;
  let j = 0;
  while (i < n || j < m) {
    if (i === n) {
      steps.push({ kind: "insert", text: b[j] });
      j++;
    } else if (j === m) {
      steps.push({ kind: "delete", text: a[i] });
      i++;
    } else if (keysA[i] === keysB[j]) {
      steps.push({ kind: "common", text: a[i] });
      i++;
      j++;
    } else if (table[(i + 1) * width + j] >= table[i * width + j + 1]) {
      steps.push({ kind: "delete", text: a[i] });
      i++;
    } else {
      steps.push({ kind: "insert", text: b[j] });
      j++;
    }
  }
  return steps;
}

const PREFIX: Record<Step["kind"], string> = {
  common: "  ",
  delete: "- ",
  insert: "+ ",
};

function main(argv: string[]): number {
  const options: Options = { ignoreCase: false, ignoreTrailing: false, quiet: false, summary: false };
  const files: string[] = [];
  for (const arg of argv) {
    if (!arg.startsWith("-")) {
      files.push(arg);
      continue;
    }
    switch (arg) {
      case "-i":
        options.ignoreCase = true;
        break;
      case "-b":
        options.ignoreTrailing = true;
        break;
      case "-q":
        options.quiet = true;
        break;
      case "-s":
        options.summary = true;
        break;
      default:
        process.stderr.write(`ldiff: unknown option ${arg}\n`);
        return 2;
    }
  }
  if (options.quiet && options.summary) {
    process.stderr.write("ldiff: -q and -s are mutually exclusive\n");
    return 2;
  }
  if (files.length !== 2) {
    process.stderr.write("usage: ldiff [-i] [-b] [-q | -s] FILE1 FILE2\n");
    return 2;
  }

  let a: string[];
  let b: string[];
  try {
    a = readLines(files[0]);
    b = readLines(files[1]);
  } catch (err) {
    process.stderr.write(`ldiff: ${(err as Error).message}\n`);
    return 2;
  }

  const steps = diff(a, b, options);
  const counts = { common: 0, delete: 0, insert: 0 };
  for (const step of steps) {
    counts[step.kind]++;
  }

  if (options.summary) {
    process.stdout.write(`+${counts.insert} -${counts.delete} =${counts.common}\n`);
  } else if (!options.quiet) {
    const out = steps.map((step) => PREFIX[step.kind] + step.text + "\n").join("");
    process.stdout.write(Buffer.from(out, "latin1"));
  }
  return counts.insert + counts.delete > 0 ? 1 : 0;
}

process.exitCode = main(process.argv.slice(2));
