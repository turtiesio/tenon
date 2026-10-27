import * as fs from "node:fs";

class UsageError extends Error {}
class DataError extends Error {}

interface Options {
  leftJoin: boolean;
  key: string;
  leftPath: string;
  rightPath: string;
}

interface Table {
  header: string[];
  rows: string[][];
}

function parseArgs(args: string[]): Options {
  let leftJoin = false;
  let key = "id";
  const paths: string[] = [];
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "-l") leftJoin = true;
    else if (arg === "-k") {
      if (i + 1 >= args.length) throw new UsageError("-k requires a column name");
      key = args[++i];
    } else if (arg.startsWith("-")) throw new UsageError(`unknown option: ${arg}`);
    else paths.push(arg);
  }
  if (paths.length !== 2) throw new UsageError("expected exactly two files");
  if (key === "") throw new UsageError("key name must not be empty");
  return { leftJoin, key, leftPath: paths[0], rightPath: paths[1] };
}

function parseCsv(text: string, path: string): string[][] {
  const records: string[][] = [];
  const n = text.length;
  let i = 0;
  let line = 1;
  const fail = (msg: string): never => {
    throw new DataError(`${path}: line ${line}: ${msg}`);
  };
  // Returns the length of the record terminator at position j, or 0.
  const terminatorAt = (j: number): number => {
    if (text[j] === "\n") return 1;
    if (text[j] === "\r" && text[j + 1] === "\n") return 2;
    return 0;
  };

  while (i < n) {
    const blank = terminatorAt(i);
    if (blank > 0) {
      i += blank;
      line++;
      continue;
    }
    const record: string[] = [];
    for (;;) {
      let field = "";
      if (text[i] === '"') {
        i++;
        for (;;) {
          if (i >= n) fail("unterminated quoted field");
          const c = text[i];
          if (c === '"') {
            if (text[i + 1] === '"') {
              field += '"';
              i += 2;
            } else {
              i++;
              break;
            }
          } else {
            if (c === "\n") line++;
            field += c;
            i++;
          }
        }
        if (i < n && text[i] !== "," && terminatorAt(i) === 0) fail("unexpected character after closing quote");
      } else {
        const start = i;
        while (i < n && text[i] !== "," && text[i] !== "\n" && text[i] !== "\r") {
          if (text[i] === '"') fail("quote inside unquoted field");
          i++;
        }
        if (text[i] === "\r" && text[i + 1] !== "\n") fail("stray carriage return");
        field = text.slice(start, i);
      }
      record.push(field);
      if (text[i] === ",") {
        i++;
        continue;
      }
      const term = terminatorAt(i);
      i += term;
      if (term > 0) line++;
      break;
    }
    records.push(record);
  }
  return records;
}

function loadTable(path: string): Table {
  let text: string;
  try {
    text = fs.readFileSync(path, "latin1");
  } catch (e) {
    throw new DataError(`${path}: cannot read: ${(e as Error).message}`);
  }
  const records = parseCsv(text, path);
  if (records.length === 0) throw new DataError(`${path}: no header row`);
  const [header, ...rows] = records;
  const seen = new Set<string>();
  for (const name of header) {
    if (seen.has(name)) throw new DataError(`${path}: duplicate column name: ${name}`);
    seen.add(name);
  }
  rows.forEach((row, r) => {
    if (row.length !== header.length) {
      throw new DataError(`${path}: record ${r + 2} has ${row.length} fields, header has ${header.length}`);
    }
  });
  return { header, rows };
}

function formatField(field: string): string {
  return /[,"\r\n]/.test(field) ? `"${field.replace(/"/g, '""')}"` : field;
}

function formatRecord(fields: string[]): string {
  return fields.map(formatField).join(",") + "\n";
}

function join(left: Table, right: Table, opts: Options): string {
  const leftKey = left.header.indexOf(opts.key);
  const rightKey = right.header.indexOf(opts.key);
  if (leftKey < 0) throw new DataError(`${opts.leftPath}: no column named ${opts.key}`);
  if (rightKey < 0) throw new DataError(`${opts.rightPath}: no column named ${opts.key}`);

  const leftNames = new Set(left.header);
  const rightColumns = right.header.map((_, i) => i).filter((i) => i !== rightKey);
  const header = [
    ...left.header,
    ...rightColumns.map((i) => (leftNames.has(right.header[i]) ? `r.${right.header[i]}` : right.header[i])),
  ];

  const byKey = new Map<string, string[][]>();
  for (const row of right.rows) {
    const k = row[rightKey];
    const bucket = byKey.get(k);
    if (bucket) bucket.push(row);
    else byKey.set(k, [row]);
  }

  const out = [formatRecord(header)];
  for (const row of left.rows) {
    const matches = byKey.get(row[leftKey]) ?? [];
    for (const match of matches) {
      out.push(formatRecord([...row, ...rightColumns.map((i) => match[i])]));
    }
    if (matches.length === 0 && opts.leftJoin) {
      out.push(formatRecord([...row, ...rightColumns.map(() => "")]));
    }
  }
  return out.join("");
}

function main(): number {
  try {
    const opts = parseArgs(process.argv.slice(2));
    const left = loadTable(opts.leftPath);
    const right = loadTable(opts.rightPath);
    process.stdout.write(join(left, right, opts));
    return 0;
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`csvjoin: ${e.message}\nusage: csvjoin [-l] [-k NAME] LEFT RIGHT\n`);
      return 2;
    }
    if (e instanceof DataError) {
      process.stderr.write(`csvjoin: ${e.message}\n`);
      return 1;
    }
    throw e;
  }
}

process.exitCode = main();
