import { readFileSync } from "node:fs";

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
    if (arg === "-l") {
      leftJoin = true;
    } else if (arg === "-k") {
      if (i + 1 >= args.length) throw new UsageError("-k needs an argument");
      key = args[++i];
      if (key === "") throw new UsageError("empty key name");
    } else if (arg.startsWith("-")) {
      throw new UsageError(`unknown option: ${arg}`);
    } else {
      paths.push(arg);
    }
  }
  if (paths.length !== 2) throw new UsageError("expected exactly two files");
  return { leftJoin, key, leftPath: paths[0], rightPath: paths[1] };
}

function parseCsv(text: string): string[][] {
  const records: string[][] = [];
  const n = text.length;
  let pos = 0;
  while (pos < n) {
    // Empty lines are skipped.
    if (text[pos] === "\n") {
      pos++;
      continue;
    }
    if (text[pos] === "\r" && text[pos + 1] === "\n") {
      pos += 2;
      continue;
    }
    const record: string[] = [];
    for (;;) {
      let field = "";
      if (text[pos] === '"') {
        pos++;
        for (;;) {
          if (pos >= n) throw new Error("unterminated quoted field");
          if (text[pos] === '"') {
            if (text[pos + 1] === '"') {
              field += '"';
              pos += 2;
            } else {
              pos++;
              break;
            }
          } else {
            field += text[pos++];
          }
        }
      } else {
        const start = pos;
        while (pos < n && !",\"\r\n".includes(text[pos])) pos++;
        if (text[pos] === '"') throw new Error("quote inside unquoted field");
        field = text.slice(start, pos);
      }
      record.push(field);
      if (pos >= n) break;
      const ch = text[pos];
      if (ch === ",") {
        pos++;
      } else if (ch === "\n") {
        pos++;
        break;
      } else if (ch === "\r" && text[pos + 1] === "\n") {
        pos += 2;
        break;
      } else {
        throw new Error("unexpected character after field");
      }
    }
    records.push(record);
  }
  return records;
}

function loadTable(path: string): Table {
  let text: string;
  try {
    text = readFileSync(path).toString("latin1");
  } catch {
    throw new DataError(`cannot read ${path}`);
  }
  let records: string[][];
  try {
    records = parseCsv(text);
  } catch (e) {
    throw new DataError(`${path}: invalid CSV: ${(e as Error).message}`);
  }
  if (records.length === 0) throw new DataError(`${path}: no header row`);
  const [header, ...rows] = records;
  if (new Set(header).size !== header.length) {
    throw new DataError(`${path}: duplicate column name`);
  }
  for (const row of rows) {
    if (row.length !== header.length) {
      throw new DataError(`${path}: record has ${row.length} fields, expected ${header.length}`);
    }
  }
  return { header, rows };
}

function csvField(field: string): string {
  return /[,"\r\n]/.test(field) ? `"${field.replaceAll('"', '""')}"` : field;
}

function csvRecord(fields: string[]): string {
  return fields.map(csvField).join(",") + "\n";
}

function join(options: Options): string {
  const left = loadTable(options.leftPath);
  const right = loadTable(options.rightPath);
  const leftKey = left.header.indexOf(options.key);
  const rightKey = right.header.indexOf(options.key);
  if (leftKey < 0 || rightKey < 0) {
    throw new DataError(`key column ${options.key} missing from a file`);
  }

  const rightKept = right.header.map((_, i) => i).filter((i) => i !== rightKey);
  const leftNames = new Set(left.header);
  const header = [
    ...left.header,
    ...rightKept.map((i) => (leftNames.has(right.header[i]) ? `r.${right.header[i]}` : right.header[i])),
  ];

  const byKey = new Map<string, string[][]>();
  for (const row of right.rows) {
    const bucket = byKey.get(row[rightKey]);
    if (bucket) bucket.push(row);
    else byKey.set(row[rightKey], [row]);
  }

  let out = csvRecord(header);
  for (const row of left.rows) {
    const matches = byKey.get(row[leftKey]);
    if (matches) {
      for (const match of matches) {
        out += csvRecord([...row, ...rightKept.map((i) => match[i])]);
      }
    } else if (options.leftJoin) {
      out += csvRecord([...row, ...rightKept.map(() => "")]);
    }
  }
  return out;
}

function main(): number {
  try {
    const output = join(parseArgs(process.argv.slice(2)));
    process.stdout.write(Buffer.from(output, "latin1"));
    return 0;
  } catch (e) {
    if (e instanceof UsageError) {
      process.stderr.write(`csvjoin: ${e.message}\n`);
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
