import { readFileSync } from "node:fs";

type SchemaType =
  | { kind: "int"; range: { minText: string; maxText: string; min: bigint; max: bigint } | null }
  | { kind: "string"; maxlen: { text: string; value: number } | null }
  | { kind: "bool" }
  | { kind: "enum"; argText: string; values: string[] };

interface SchemaEntry {
  id: string;
  required: boolean;
  type: SchemaType;
}

const NAME_RE = /^[a-z][a-z0-9_]*$/;
const INT_RE = /^-?[0-9]{1,18}$/;

function splitLines(text: string): string[] {
  const lines = text.split("\n");
  if (lines.length > 0 && lines[lines.length - 1] === "") {
    lines.pop();
  }
  return lines.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line));
}

function trimBlanks(text: string): string {
  return text.replace(/^[ \t]+/, "").replace(/[ \t]+$/, "");
}

function parseType(typeName: string, arg: string | undefined): SchemaType | null {
  switch (typeName) {
    case "int": {
      if (arg === undefined) {
        return { kind: "int", range: null };
      }
      const match = /^(-?[0-9]{1,18})\.\.(-?[0-9]{1,18})$/.exec(arg);
      if (match === null) {
        return null;
      }
      const min = BigInt(match[1]);
      const max = BigInt(match[2]);
      if (min > max) {
        return null;
      }
      return { kind: "int", range: { minText: match[1], maxText: match[2], min, max } };
    }
    case "string": {
      if (arg === undefined) {
        return { kind: "string", maxlen: null };
      }
      const match = /^maxlen=([0-9]{1,7})$/.exec(arg);
      if (match === null) {
        return null;
      }
      return { kind: "string", maxlen: { text: match[1], value: Number(match[1]) } };
    }
    case "bool":
      return arg === undefined ? { kind: "bool" } : null;
    case "enum": {
      if (arg === undefined) {
        return null;
      }
      const values = arg.split(",");
      if (values.some((value) => value === "")) {
        return null;
      }
      return { kind: "enum", argText: arg, values };
    }
    default:
      return null;
  }
}

function parseSchema(text: string): SchemaEntry[] | null {
  const entries: SchemaEntry[] = [];
  const seen = new Set<string>();
  for (const line of splitLines(text)) {
    const trimmed = trimBlanks(line);
    if (trimmed === "" || trimmed.startsWith("#")) {
      continue;
    }
    const tokens = trimmed.split(/[ \t]+/);
    if (tokens.length < 3 || tokens.length > 4) {
      return null;
    }
    const [id, typeName, presence, arg] = tokens;
    const parts = id.split(".");
    if (parts.length !== 2 || !NAME_RE.test(parts[0]) || !NAME_RE.test(parts[1])) {
      return null;
    }
    if (presence !== "required" && presence !== "optional") {
      return null;
    }
    const type = parseType(typeName, arg);
    if (type === null || seen.has(id)) {
      return null;
    }
    seen.add(id);
    entries.push({ id, required: presence === "required", type });
  }
  return entries;
}

function checkValue(entry: SchemaEntry, value: string): string | null {
  const type = entry.type;
  switch (type.kind) {
    case "int": {
      if (!INT_RE.test(value)) {
        return "not an integer";
      }
      if (type.range !== null) {
        const number = BigInt(value);
        if (number < type.range.min || number > type.range.max) {
          return `out of range ${type.range.minText}..${type.range.maxText}`;
        }
      }
      return null;
    }
    case "bool":
      return value === "true" || value === "false" ? null : "not a boolean";
    case "string":
      if (type.maxlen !== null && value.length > type.maxlen.value) {
        return `longer than ${type.maxlen.text}`;
      }
      return null;
    case "enum":
      return type.values.includes(value) ? null : `not one of ${type.argText}`;
  }
}

function checkConfig(text: string, schema: SchemaEntry[], strict: boolean): string[] {
  const byId = new Map(schema.map((entry) => [entry.id, entry]));
  const diagnostics: string[] = [];
  const seenKeys = new Set<string>();
  let section: string | null = null;

  splitLines(text).forEach((line, index) => {
    const lineNumber = index + 1;
    const trimmed = trimBlanks(line);
    if (trimmed === "" || trimmed.startsWith("#") || trimmed.startsWith(";")) {
      return;
    }
    const header = /^\[([a-z][a-z0-9_]*)\]$/.exec(trimmed);
    if (header !== null) {
      section = header[1];
      return;
    }
    const eq = line.indexOf("=");
    if (eq < 0) {
      diagnostics.push(`${lineNumber}: syntax error`);
      return;
    }
    const key = trimBlanks(line.slice(0, eq));
    const value = trimBlanks(line.slice(eq + 1));
    if (!NAME_RE.test(key)) {
      diagnostics.push(`${lineNumber}: syntax error`);
      return;
    }
    if (section === null) {
      diagnostics.push(`${lineNumber}: key outside section`);
      return;
    }
    const id = `${section}.${key}`;
    if (seenKeys.has(id)) {
      diagnostics.push(`${lineNumber}: duplicate key ${id}`);
      return;
    }
    seenKeys.add(id);
    const entry = byId.get(id);
    if (entry === undefined) {
      if (strict) {
        diagnostics.push(`${lineNumber}: unknown key ${id}`);
      }
      return;
    }
    const problem = checkValue(entry, value);
    if (problem !== null) {
      diagnostics.push(`${lineNumber}: ${id}: ${problem}`);
    }
  });

  for (const entry of schema) {
    if (entry.required && !seenKeys.has(entry.id)) {
      diagnostics.push(`missing: ${entry.id}`);
    }
  }
  return diagnostics;
}

function readText(path: string): string | null {
  try {
    return readFileSync(path, "latin1");
  } catch {
    return null;
  }
}

function main(): number {
  let strict = false;
  let quiet = false;
  const paths: string[] = [];
  for (const arg of process.argv.slice(2)) {
    if (arg === "--strict") {
      strict = true;
    } else if (arg === "-q") {
      quiet = true;
    } else if (arg.startsWith("-")) {
      console.error(`unknown option: ${arg}`);
      return 2;
    } else {
      paths.push(arg);
    }
  }
  if (paths.length !== 2) {
    console.error("usage: cfgcheck [--strict] [-q] SCHEMA CONFIG");
    return 2;
  }

  const schemaText = readText(paths[0]);
  if (schemaText === null) {
    console.error(`cannot read ${paths[0]}`);
    return 2;
  }
  const schema = parseSchema(schemaText);
  if (schema === null) {
    console.error("invalid schema");
    return 3;
  }
  const configText = readText(paths[1]);
  if (configText === null) {
    console.error(`cannot read ${paths[1]}`);
    return 2;
  }

  const diagnostics = checkConfig(configText, schema, strict);
  if (!quiet) {
    const summary = diagnostics.length === 0 ? "OK" : `errors: ${diagnostics.length}`;
    process.stdout.write([...diagnostics, summary].join("\n") + "\n");
  }
  return diagnostics.length === 0 ? 0 : 1;
}

process.exitCode = main();
