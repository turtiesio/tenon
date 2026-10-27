import * as fs from "node:fs";

type IntRule = { type: "int"; range: { min: bigint; max: bigint; text: string } | null };
type StringRule = { type: "string"; maxlen: number | null; maxlenText: string };
type BoolRule = { type: "bool" };
type EnumRule = { type: "enum"; values: string[]; text: string };
type Rule = IntRule | StringRule | BoolRule | EnumRule;

interface SchemaEntry {
  name: string;
  required: boolean;
  rule: Rule;
}

const NAME_RE = /^[a-z][a-z0-9_]*$/;
const INT_RE = /^-?[0-9]{1,18}$/;

class SchemaError extends Error {}

function splitLines(text: string): string[] {
  const lines = text.split("\n");
  if (lines.length > 0 && lines[lines.length - 1] === "") {
    lines.pop();
  }
  return lines.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line));
}

function trimBlanks(s: string): string {
  return s.replace(/^[ \t]+|[ \t]+$/g, "");
}

function parseRule(type: string, arg: string | undefined): Rule {
  switch (type) {
    case "int": {
      if (arg === undefined) {
        return { type: "int", range: null };
      }
      const m = /^(-?[0-9]{1,18})\.\.(-?[0-9]{1,18})$/.exec(arg);
      if (!m) {
        throw new SchemaError(`bad int range: ${arg}`);
      }
      const min = BigInt(m[1]);
      const max = BigInt(m[2]);
      if (min > max) {
        throw new SchemaError(`empty int range: ${arg}`);
      }
      return { type: "int", range: { min, max, text: arg } };
    }
    case "string": {
      if (arg === undefined) {
        return { type: "string", maxlen: null, maxlenText: "" };
      }
      const m = /^maxlen=([0-9]{1,7})$/.exec(arg);
      if (!m) {
        throw new SchemaError(`bad string arg: ${arg}`);
      }
      return { type: "string", maxlen: Number(m[1]), maxlenText: m[1] };
    }
    case "bool":
      if (arg !== undefined) {
        throw new SchemaError("bool takes no argument");
      }
      return { type: "bool" };
    case "enum": {
      if (arg === undefined) {
        throw new SchemaError("enum requires values");
      }
      const values = arg.split(",");
      if (values.some((v) => v === "")) {
        throw new SchemaError(`bad enum values: ${arg}`);
      }
      return { type: "enum", values, text: arg };
    }
    default:
      throw new SchemaError(`unknown type: ${type}`);
  }
}

function parseSchema(text: string): SchemaEntry[] {
  const entries: SchemaEntry[] = [];
  const seen = new Set<string>();
  for (const line of splitLines(text)) {
    const trimmed = trimBlanks(line);
    if (trimmed === "" || trimmed.startsWith("#")) {
      continue;
    }
    const tokens = trimmed.split(/[ \t]+/);
    if (tokens.length < 3 || tokens.length > 4) {
      throw new SchemaError(`wrong number of tokens: ${line}`);
    }
    const [name, type, presence, arg] = tokens;
    const parts = name.split(".");
    if (parts.length !== 2 || !NAME_RE.test(parts[0]) || !NAME_RE.test(parts[1])) {
      throw new SchemaError(`bad key name: ${name}`);
    }
    if (presence !== "required" && presence !== "optional") {
      throw new SchemaError(`bad presence: ${presence}`);
    }
    const rule = parseRule(type, arg);
    if (seen.has(name)) {
      throw new SchemaError(`duplicate entry: ${name}`);
    }
    seen.add(name);
    entries.push({ name, required: presence === "required", rule });
  }
  return entries;
}

function checkValue(name: string, rule: Rule, value: string): string | null {
  switch (rule.type) {
    case "int": {
      if (!INT_RE.test(value)) {
        return `${name}: not an integer`;
      }
      if (rule.range !== null) {
        const n = BigInt(value);
        if (n < rule.range.min || n > rule.range.max) {
          return `${name}: out of range ${rule.range.text}`;
        }
      }
      return null;
    }
    case "bool":
      return value === "true" || value === "false" ? null : `${name}: not a boolean`;
    case "string":
      if (rule.maxlen !== null && value.length > rule.maxlen) {
        return `${name}: longer than ${rule.maxlenText}`;
      }
      return null;
    case "enum":
      return rule.values.includes(value) ? null : `${name}: not one of ${rule.text}`;
  }
}

function validateConfig(text: string, schema: SchemaEntry[], strict: boolean): string[] {
  const byName = new Map(schema.map((entry) => [entry.name, entry]));
  const diagnostics: string[] = [];
  const seenKeys = new Set<string>();
  let section: string | null = null;

  splitLines(text).forEach((line, index) => {
    const lineNo = index + 1;
    const trimmed = trimBlanks(line);
    if (trimmed === "" || trimmed.startsWith("#") || trimmed.startsWith(";")) {
      return;
    }
    const header = /^\[([a-z][a-z0-9_]*)\]$/.exec(trimmed);
    if (header) {
      section = header[1];
      return;
    }
    const eq = line.indexOf("=");
    if (eq < 0) {
      diagnostics.push(`${lineNo}: syntax error`);
      return;
    }
    const key = trimBlanks(line.slice(0, eq));
    const value = trimBlanks(line.slice(eq + 1));
    if (!NAME_RE.test(key)) {
      diagnostics.push(`${lineNo}: syntax error`);
      return;
    }
    if (section === null) {
      diagnostics.push(`${lineNo}: key outside section`);
      return;
    }
    const name = `${section}.${key}`;
    if (seenKeys.has(name)) {
      diagnostics.push(`${lineNo}: duplicate key ${name}`);
      return;
    }
    seenKeys.add(name);
    const entry = byName.get(name);
    if (entry === undefined) {
      if (strict) {
        diagnostics.push(`${lineNo}: unknown key ${name}`);
      }
      return;
    }
    const problem = checkValue(name, entry.rule, value);
    if (problem !== null) {
      diagnostics.push(`${lineNo}: ${problem}`);
    }
  });

  for (const entry of schema) {
    if (entry.required && !seenKeys.has(entry.name)) {
      diagnostics.push(`missing: ${entry.name}`);
    }
  }
  return diagnostics;
}

function readFile(path: string): string | null {
  try {
    return fs.readFileSync(path, "latin1");
  } catch {
    return null;
  }
}

function main(argv: string[]): number {
  let strict = false;
  let quiet = false;
  const positional: string[] = [];
  for (const arg of argv) {
    if (arg.startsWith("-")) {
      if (arg === "--strict") {
        strict = true;
      } else if (arg === "-q") {
        quiet = true;
      } else {
        process.stderr.write(`cfgcheck: unknown option ${arg}\n`);
        return 2;
      }
    } else {
      positional.push(arg);
    }
  }
  if (positional.length !== 2) {
    process.stderr.write("usage: cfgcheck [--strict] [-q] SCHEMA CONFIG\n");
    return 2;
  }
  const [schemaPath, configPath] = positional;

  const schemaText = readFile(schemaPath);
  if (schemaText === null) {
    process.stderr.write(`cfgcheck: cannot read ${schemaPath}\n`);
    return 2;
  }
  let schema: SchemaEntry[];
  try {
    schema = parseSchema(schemaText);
  } catch (err) {
    if (err instanceof SchemaError) {
      process.stderr.write(`cfgcheck: invalid schema: ${err.message}\n`);
      return 3;
    }
    throw err;
  }

  const configText = readFile(configPath);
  if (configText === null) {
    process.stderr.write(`cfgcheck: cannot read ${configPath}\n`);
    return 2;
  }
  const diagnostics = validateConfig(configText, schema, strict);
  if (!quiet) {
    const out = diagnostics.map((d) => d + "\n").join("");
    const summary = diagnostics.length === 0 ? "OK\n" : `errors: ${diagnostics.length}\n`;
    process.stdout.write(out + summary);
  }
  return diagnostics.length === 0 ? 0 : 1;
}

process.exitCode = main(process.argv.slice(2));
