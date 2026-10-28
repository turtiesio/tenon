import { readFileSync } from "node:fs";

type Op = { kind: "common" | "delete" | "insert"; text: string };

// Files are read as latin1 so that each character is one byte; lines are
// then compared (and written back) as byte strings.
function readLines(path: string): string[] | null {
  let text: string;
  try {
    text = readFileSync(path, "latin1");
  } catch {
    return null;
  }
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") {
    lines.pop();
  }
  return lines;
}

function makeKey(line: string, ignoreCase: boolean, ignoreTrailing: boolean): string {
  let key = line;
  if (ignoreTrailing) {
    key = key.replace(/[ \t]+$/, "");
  }
  if (ignoreCase) {
    key = key.replace(/[A-Z]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) + 32));
  }
  return key;
}

function diff(a: string[], b: string[], keyA: string[], keyB: string[]): Op[] {
  const n = a.length;
  const m = b.length;
  const width = m + 1;
  const table = new Int32Array((n + 1) * width);
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      table[i * width + j] =
        keyA[i] === keyB[j]
          ? table[(i + 1) * width + j + 1] + 1
          : Math.max(table[(i + 1) * width + j], table[i * width + j + 1]);
    }
  }

  const ops: Op[] = [];
  let i = 0;
  let j = 0;
  while (i < n || j < m) {
    if (i === n) {
      ops.push({ kind: "insert", text: b[j++] });
    } else if (j === m) {
      ops.push({ kind: "delete", text: a[i++] });
    } else if (keyA[i] === keyB[j]) {
      ops.push({ kind: "common", text: a[i] });
      i++;
      j++;
    } else if (table[(i + 1) * width + j] >= table[i * width + j + 1]) {
      ops.push({ kind: "delete", text: a[i++] });
    } else {
      ops.push({ kind: "insert", text: b[j++] });
    }
  }
  return ops;
}

function main(): number {
  let ignoreCase = false;
  let ignoreTrailing = false;
  let quiet = false;
  let summary = false;
  const paths: string[] = [];
  for (const arg of process.argv.slice(2)) {
    if (arg === "-i") {
      ignoreCase = true;
    } else if (arg === "-b") {
      ignoreTrailing = true;
    } else if (arg === "-q") {
      quiet = true;
    } else if (arg === "-s") {
      summary = true;
    } else if (arg.startsWith("-")) {
      console.error(`unknown option: ${arg}`);
      return 2;
    } else {
      paths.push(arg);
    }
  }
  if ((quiet && summary) || paths.length !== 2) {
    console.error("usage: ldiff [-i] [-b] [-q | -s] FILE1 FILE2");
    return 2;
  }

  const a = readLines(paths[0]);
  const b = readLines(paths[1]);
  if (a === null || b === null) {
    console.error("cannot read input file");
    return 2;
  }

  const keyA = a.map((line) => makeKey(line, ignoreCase, ignoreTrailing));
  const keyB = b.map((line) => makeKey(line, ignoreCase, ignoreTrailing));
  const ops = diff(a, b, keyA, keyB);

  const count = (kind: Op["kind"]) => ops.filter((op) => op.kind === kind).length;
  const inserted = count("insert");
  const deleted = count("delete");

  if (!quiet) {
    let out: string;
    if (summary) {
      out = `+${inserted} -${deleted} =${count("common")}\n`;
    } else {
      const prefix = { common: "  ", delete: "- ", insert: "+ " };
      out = ops.map((op) => `${prefix[op.kind]}${op.text}\n`).join("");
    }
    process.stdout.write(Buffer.from(out, "latin1"));
  }
  return inserted + deleted > 0 ? 1 : 0;
}

process.exitCode = main();
