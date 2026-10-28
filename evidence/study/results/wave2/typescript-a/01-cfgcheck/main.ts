import { readFileSync } from 'node:fs';

function lines(text: string): string[] {
  const result = text.split('\n');
  if (result.at(-1) === '') result.pop();
  return result.map(line => line.replace(/\r$/, ''));
}
const trim = (text: string) => text.replace(/^[ \t]+|[ \t]+$/g, '');
const args = process.argv.slice(2);
const paths = args.filter(arg => !arg.startsWith('-'));
if (paths.length !== 2 || args.some(arg => arg.startsWith('-') && !['--strict', '-q'].includes(arg))) process.exit(2);
let schemaText: string;
try { schemaText = readFileSync(paths[0], 'utf8'); } catch { process.exit(2); }
type Entry = { name: string; type: string; required: boolean; arg?: string; min?: bigint; max?: bigint };
const schema = new Map<string, Entry>();
for (const raw of lines(schemaText)) {
  const line = trim(raw);
  if (!line || line.startsWith('#')) continue;
  const [name, type, presence, arg, extra] = line.split(/[ \t]+/);
  if (extra !== undefined || !/^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$/.test(name) || schema.has(name) || !['required', 'optional'].includes(presence)) process.exit(3);
  const entry: Entry = { name, type, required: presence === 'required', arg };
  if (type === 'int') {
    if (arg !== undefined) {
      const match = /^(-?[0-9]{1,18})\.\.(-?[0-9]{1,18})$/.exec(arg);
      if (!match) process.exit(3);
      entry.min = BigInt(match[1]);
      entry.max = BigInt(match[2]);
      if (entry.min > entry.max) process.exit(3);
    }
  } else if (type === 'string') {
    if (arg !== undefined && !/^maxlen=[0-9]{1,7}$/.test(arg)) process.exit(3);
  } else if (type === 'bool') {
    if (arg !== undefined) process.exit(3);
  } else if (type === 'enum') {
    if (!arg || arg.split(',').some(value => !value)) process.exit(3);
  } else process.exit(3);
  schema.set(name, entry);
}
let config: string;
try { config = readFileSync(paths[1], 'utf8'); } catch { process.exit(2); }
const errors: string[] = [];
const seen = new Set<string>();
let section: string | undefined;
for (const [index, raw] of lines(config).entries()) {
  const line = trim(raw);
  if (!line || /^[#;]/.test(line)) continue;
  const header = /^\[([a-z][a-z0-9_]*)\]$/.exec(line);
  if (header) { section = header[1]; continue; }
  const eq = line.indexOf('=');
  const key = trim(line.slice(0, eq));
  const value = trim(line.slice(eq + 1));
  let error: string | undefined;
  if (eq < 0 || !/^[a-z][a-z0-9_]*$/.test(key)) error = 'syntax error';
  else if (section === undefined) error = 'key outside section';
  else {
    const name = `${section}.${key}`;
    if (seen.has(name)) error = `duplicate key ${name}`;
    else {
      seen.add(name);
      const entry = schema.get(name);
      if (!entry) {
        if (args.includes('--strict')) error = `unknown key ${name}`;
      } else {
        let problem: string | undefined;
        if (entry.type === 'int') {
          if (!/^-?[0-9]{1,18}$/.test(value)) problem = 'not an integer';
          else if (entry.min !== undefined && (BigInt(value) < entry.min || BigInt(value) > entry.max!)) problem = `out of range ${entry.arg}`;
        } else if (entry.type === 'bool' && !['true', 'false'].includes(value)) problem = 'not a boolean';
        else if (entry.type === 'string' && entry.arg && value.length > Number(entry.arg.slice(7))) problem = `longer than ${entry.arg.slice(7)}`;
        else if (entry.type === 'enum' && !entry.arg!.split(',').includes(value)) problem = `not one of ${entry.arg}`;
        if (problem) error = `${name}: ${problem}`;
      }
    }
  }
  if (error) errors.push(`${index + 1}: ${error}`);
}
for (const entry of schema.values()) {
  if (entry.required && !seen.has(entry.name)) errors.push(`missing: ${entry.name}`);
}
if (!args.includes('-q')) console.log([...errors, errors.length ? `errors: ${errors.length}` : 'OK'].join('\n'));
process.exitCode = errors.length ? 1 : 0;
