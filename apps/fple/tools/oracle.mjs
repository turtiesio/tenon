// Differential request-validation evidence from the actual FPLE validator.
import { readFile, writeFile } from 'node:fs/promises';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { sourceLoader } from './source-loader.mjs';
const app = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(process.argv[2] ?? `${process.env.HOME}/dev/fple`);
sourceLoader(source);
const load = file => import(pathToFileURL(join(source, file)).href);
const [{ nativeOperationContracts: operations }, { compileNativeSchema }] = await Promise.all([
  load('packages/commerce/src/composition/modules/native-operation-contracts.ts'),
  load('packages/commerce/src/shared-kernel/schema/schema.ts'),
]);
const definition = JSON.parse(await readFile(join(app, 'definition/system.json'), 'utf8'));
const byId = new Map(definition.operations.map(operation => [operation.id, operation]));
const patterns = {
  '^(?!(?:[Rr][Ee][Aa][Dd][Yy]|[Tt][Bb][Dd])(?:$|[-_\\s]))[A-Za-z0-9-]+$': '1234-5678',
  '^[0-9]{9,11}$': '01012345678', '^[a-z0-9-]+$': 'example-shop', '^[0-9]{4}$': '1234',
  '^[0-9]{13,16}$': '1234567890123', '^[0-9]{2}$': '12', '^[0-9]{6,10}$': '123456',
  '^[A-Za-z0-9_-]+$': 'abc-123', '^[0-9]+$': '1234', '^[0-9]+\\.[0-9]{2,6}$': '1234.50',
  '^[0-9]{4}-[0-9]{2}-[0-9]{2}$': '2026-10-28', '^[0-9]{8}$': '12345678',
  '^[0-9]{10}$': '1234567890', '^[0-9-]+$': '1234-5678', '^[0-9]{4}-(0[1-9]|1[0-2])$': '2026-10',
  '^[0-9-]{10}$': '2026-10-28', '^[a-f0-9]{64}$': 'a'.repeat(64), '^01[016789][0-9]{7,8}$': '01012345678',
  '^\\d{5}$': '12345', '^\\d{4}-\\d{2}-\\d{2}$': '2026-10-28', '^[0-9]{4}-[0-9]{2}$': '2026-10',
  '^[0-9+()\\s-]{8,24}$': '+82 (10) 1234-5678',
};
function sample(schema) {
  if ('const' in schema) return schema.const;
  if (schema.enum) return schema.enum[0];
  if (schema.anyOf) return sample(schema.anyOf.find(child => child.type !== 'null') ?? schema.anyOf[0]);
  switch (schema.type) {
    case 'null': return null;
    case 'boolean': return false;
    case 'integer': return Math.ceil(Math.max(schema.minimum ?? 0, Math.min(schema.maximum ?? 1, 1)));
    case 'number': return Math.max(schema.minimum ?? 0, Math.min(schema.maximum ?? 1, 1));
    case 'string': {
      if (schema.pattern) {
        if (!(schema.pattern in patterns)) throw new Error(`Missing source pattern example: ${schema.pattern}`);
        const example = patterns[schema.pattern];
        return example.padEnd(schema.minLength ?? 0, /[0-9]$/.test(example) ? "0" : "x");
      }
      if (schema.format === 'date-time') return '2026-10-28T00:00:00.000Z';
      if (schema.format === 'date') return '2026-10-28';
      if (schema.format === 'url') return 'https://example.com';
      return 'x'.repeat(Math.max(schema.minLength ?? 0, 1));
    }
    case 'array': return Array.from({ length: schema.minItems ?? 0 }, () => sample(schema.items));
    case 'object': return Object.fromEntries((schema.required ?? []).map(key => [key, sample(schema.properties[key])]));
    case undefined: return {};
    default: throw new Error(`Unknown example schema ${schema.type}`);
  }
}
function constraints(input, rules) {
  function update(value, path, rule) {
    if (!path.length) {
      if (rule.format === 'url') return 'https://example.com';
      if (rule.format === 'email') return 'user@example.com';
      return value;
    }
    const [head, ...tail] = path;
    if (head === '*' && Array.isArray(value)) return value.map(item => update(item, tail, rule));
    if (value !== null && typeof value === 'object' && head in value) return { ...value, [head]: update(value[head], tail, rule) };
    return value;
  }
  return rules.reduce((value, rule) => update(value, rule.path, rule), input);
}
const quote = text => JSON.stringify(text).replaceAll('\\u0000', '\\0');
function native(value) {
  if (value === null) return 'VNull';
  if (typeof value === 'boolean') return `VBool(${value})`;
  if (typeof value === 'number') return Number.isInteger(value) ? `VInt(${value})` : `VDecimal(${value})`;
  if (typeof value === 'string') return `VText(${quote(value)})`;
  if (Array.isArray(value)) return `VList([${value.map(native).join(', ')}])`;
  const fields = Object.entries(value).map(([key, child]) => `${quote(key)}: ${native(child)}`);
  return `VObject(${fields.length ? `[${fields.join(', ')}]` : '[:]'})`;
}
const cases = [];
for (const operation of operations) {
  const validator = compileNativeSchema(operation.inputSchema, operation.inputValidation ?? []);
  const valid = constraints(sample(operation.inputSchema), operation.inputValidation ?? []);
  if (!validator.Check(valid)) {
    try { validator.Parse(valid); } catch (error) { throw new Error(`Invalid positive example ${operation.id}: ${error.message}`); }
    throw new Error(`Invalid positive example ${operation.id}`);
  }
  const row = byId.get(operation.id);
  const candidates = [valid, null, { ...valid, __unexpected: true }];
  const required = operation.inputSchema.required ?? [];
  if (required.length) { const missing = { ...valid }; delete missing[required[0]]; candidates.push(missing); }
  for (const input of candidates) {
    const valid = validator.Check(input);
    const expected = valid ? validator.Parse(input) : null;
    cases.push(`(${quote(operation.id)}, ${row.inputSchema}, ${native(input)}, ${valid}, ${native(expected)})`);
  }
}
const codec = `[${cases.join(', ')}]`;
const text = `// @generated by tools/oracle.mjs from FPLE's actual validator.\nimport fple_model\n\npub fn cases() -> Result[List[(Str, Int, fple_model.Value, Bool, fple_model.Value)], Str] {\n    decode(${quote(codec).replaceAll('{', '\\{')})\n}\n`;
const target = join(app, 'tests/full/source_validation.tn');
if (process.argv.includes('--check')) { if (await readFile(target, 'utf8') !== text) throw new Error('Stale source validation oracle'); }
else await writeFile(target, text);
console.log(`Source differential oracle: ${operations.length} operations, ${cases.length} request cases`);
