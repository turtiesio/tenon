// Rebuild the exact front-to-back source inventory. No source checkout writes.
import { createHash } from 'node:crypto';
import { readFile, writeFile, readdir, mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, join, relative, resolve, extname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';
import { brotliDecompressSync } from 'node:zlib';
import { sourceLoader } from './source-loader.mjs';

const app = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(process.argv[2] ?? `${process.env.HOME}/dev/fple`);
const check = process.argv.includes('--check');
const requireSource = createRequire(join(source, 'package.json'));
const ts = requireSource('typescript');
sourceLoader(source);
const load = file => import(pathToFileURL(join(source, file)).href);
const [{ nativeOperationContracts: contracts }, { routeTable: routes }, client, roles, docs] = await Promise.all([
  load('packages/commerce/src/composition/modules/native-operation-contracts.ts'),
  load('packages/contracts/src/runtime/route-table.ts'),
  load('packages/contracts/generated/runtime/usg/commerce-client.usg.ts'),
  load('packages/contracts/src/identity/role-defaults.ts'),
  load('packages/contracts/src/runtime/route-docs.ts'),
]);
const digest = text => createHash('sha256').update(text).digest('hex');
const clean = value => JSON.parse(JSON.stringify(value));
const operations = contracts.map(clean).sort((a, b) => a.id.localeCompare(b.id, 'en'));
const operationIds = new Set(operations.map(operation => operation.id));
if (operationIds.size !== operations.length) throw new Error('Duplicate operation ID');
const snapshot = JSON.parse(await readFile(join(source, 'packages/commerce/generated/artifacts/contract-snapshot.json'), 'utf8'));
if (JSON.stringify([...operationIds].sort()) !== JSON.stringify([...snapshot.v1.operations].sort()))
  throw new Error('Authored operation registry and generated source snapshot disagree');

async function walk(directory) {
  const result = [];
  for (const entry of (await readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name, 'en'))) {
    if (['node_modules', 'generated', 'dist', '.git', '.cache', 'test', 'tests', 'vendor', 'public'].includes(entry.name)) continue;
    const path = join(directory, entry.name);
    if (entry.isDirectory()) result.push(...await walk(path));
    else if (/\.(?:ts|tsx|mjs)$/.test(entry.name) && !/\.(?:test|spec|d)\.(?:ts|tsx)$/.test(entry.name) && !/\.gen\.tsx?$/.test(entry.name)) result.push(path);
  }
  return result;
}
const paths = [];
for (const pkg of await readdir(join(source, 'packages'))) {
  const root = join(source, 'packages', pkg, 'src');
  try { paths.push(...await walk(root)); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
}
const pathSet = new Set(paths);
function localImport(file, specifier) {
  const base = specifier.startsWith('@/') ? join(source, 'packages/web/src', specifier.slice(2))
    : specifier.startsWith('.') ? resolve(dirname(file), specifier) : null;
  if (base === null) return null;
  for (const candidate of [base, `${base}.ts`, `${base}.tsx`, `${base}.mjs`, join(base, 'index.ts'), join(base, 'index.tsx')]) {
    if (pathSet.has(candidate)) return relative(source, candidate);
  }
  return null;
}
function propertyParts(node) {
  if (ts.isIdentifier(node)) return [node.text];
  if (ts.isPropertyAccessExpression(node)) return [...propertyParts(node.expression), node.name.text];
  if (ts.isElementAccessExpression(node) && ts.isStringLiteral(node.argumentExpression)) return [...propertyParts(node.expression), node.argumentExpression.text];
  return [];
}
function opReference(node) {
  const parts = propertyParts(node);
  if (parts[0] !== 'op') return null;
  let value = client.op;
  for (const name of parts.slice(1)) value = value?.[name];
  return typeof value === 'string' && operationIds.has(value) ? value : null;
}
const files = [];
let symbolCount = 0;
const owners = new Map();
const screens = [];
for (const path of paths.sort()) {
  const text = await readFile(path, 'utf8');
  const file = relative(source, path);
  const ast = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, extname(path) === '.tsx' ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  if (ast.parseDiagnostics.length) throw new Error(`Source parse failure: ${file}`);
  const references = new Set();
  const imports = new Set();
  const external = new Set();
  const routesHere = [];
  const functions = [];
  function visit(node) {
    if (ts.isStringLiteralLike(node) && operationIds.has(node.text)) references.add(node.text);
    const reference = opReference(node);
    if (reference) references.add(reference);
    if (ts.isPropertyAssignment(node) && node.name.getText(ast).replaceAll('"', '') === 'id' && ts.isStringLiteralLike(node.initializer) && operationIds.has(node.initializer.text)) {
      if (/\/(?:contract|runtime-contracts)\//.test(file) || (file.includes('/platform/') && file.endsWith('.operations.ts'))) {
        const entries = owners.get(node.initializer.text) ?? [];
        entries.push(file); owners.set(node.initializer.text, entries);
      }
    }
    let imported;
    if (ts.isImportDeclaration(node) && !node.importClause?.isTypeOnly) imported = node.moduleSpecifier;
    if (ts.isExportDeclaration(node) && !node.isTypeOnly) imported = node.moduleSpecifier;
    if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) imported = node.arguments[0];
    if (imported && ts.isStringLiteralLike(imported)) {
      const local = localImport(path, imported.text);
      if (local) imports.add(local); else external.add(imported.text);
    }
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'createFileRoute' && ts.isStringLiteralLike(node.arguments[0])) routesHere.push(node.arguments[0].text);
    if ((ts.isFunctionDeclaration(node) || ts.isMethodDeclaration(node) || ts.isGetAccessor(node) || ts.isArrowFunction(node) || ts.isFunctionExpression(node)) && node.body) {
      let name = node.name?.getText(ast);
      if (!name && ts.isVariableDeclaration(node.parent)) name = node.parent.name.getText(ast);
      const line = ast.getLineAndCharacterOfPosition(node.getStart(ast)).line + 1;
      functions.push([line, name ?? '<callback>']);
      symbolCount++;
    }
    ts.forEachChild(node, visit);
  }
  visit(ast);
  const owner = /packages\/commerce\/src\/verticals\/([^/]+)/.exec(file)?.[1]
    ?? (file.startsWith('packages/commerce/src/platform/') ? 'platform' : file.split('/')[1]);
  files.push({ path: file, owner, hash: digest(text), lines: text.split('\n').length, imports: [...imports].sort(), external: [...external].sort(), operations: [...references].sort(), functions });
  for (const route of routesHere) screens.push({ path: route, file });
}
const fileIndex = new Map(files.map(file => [file.path, file]));
function reachable(file) {
  const seen = new Set();
  const found = new Set();
  const pending = [file];
  while (pending.length) {
    const next = pending.pop();
    if (seen.has(next)) continue;
    seen.add(next);
    const item = fileIndex.get(next);
    if (!item) continue;
    for (const operation of item.operations) found.add(operation);
    pending.push(...item.imports);
  }
  return { modules: [...seen].sort(), operations: [...found].sort() };
}
for (const screen of screens) Object.assign(screen, reachable(screen.file));
for (const operation of operations) {
  const declarations = [...new Set(owners.get(operation.id) ?? [])].sort();
  if (declarations.length !== 1) throw new Error(`Expected one authored owner for ${operation.id}: ${declarations.join(', ')}`);
  operation.source = declarations[0];
  operation.owner = /\/verticals\/([^/]+)\//.exec(operation.source)?.[1] ?? 'platform';
  operation.references = files.filter(file => file.operations.includes(operation.id) && !file.path.includes('/contract/')).map(file => file.path);
}
for (const route of routes) for (const id of route.operationRefs ?? []) {
  if (!operationIds.has(id)) throw new Error(`Route ${route.key} references unknown operation ${id}`);
}
const sourceRevision = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: source, encoding: 'utf8' }).trim();
const policies = Object.fromEntries(Object.entries(docs).filter(([name]) => name.toLowerCase().includes('polic')));
const schemas = [];
const schemaIndex = new Map();
const schemaKeywords = new Set(['type','enum','const','properties','required','items','additionalProperties','anyOf','minLength','maxLength','pattern','format','minimum','maximum','minItems','maxItems','uniqueItems']);
function internSchema(schema) {
  if (typeof schema !== 'object' || schema === null || Array.isArray(schema)) throw new Error('Invalid schema node');
  const node = {};
  for (const [key, value] of Object.entries(schema)) {
    if (!key.startsWith('x-') && !schemaKeywords.has(key)) throw new Error(`Unsupported schema keyword: ${key}`);
    if (key === 'properties') node[key] = Object.fromEntries(Object.entries(value).map(([field, child]) => [field, internSchema(child)]));
    else if (key === 'items' || (key === 'additionalProperties' && typeof value === 'object')) node[key] = internSchema(value);
    else if (key === 'anyOf') node[key] = value.map(internSchema);
    else node[key] = value;
  }
  const key = JSON.stringify(node);
  if (schemaIndex.has(key)) return schemaIndex.get(key);
  const id = schemas.length;
  schemas.push(node); schemaIndex.set(key, id);
  return id;
}
for (const operation of operations) {
  operation.inputSchema = internSchema(operation.inputSchema);
  operation.outputSchema = internSchema(operation.outputSchema);
  if (operation.scope) operation.scope.schema = internSchema(operation.scope.schema);
}
const packedBoot = await readFile(join(source, 'packages/commerce/generated/runtime-assets/cfg-runtime-boot.txt'), 'utf8');
const boot = JSON.parse(brotliDecompressSync(Buffer.from(packedBoot, 'base64')).toString('utf8'));
if (boot.kind !== 'cfgRuntimeBoot' || boot.programRevision !== snapshot.programRevision) throw new Error('Source boot metadata and source snapshot disagree');
function lowerSchema(schema) {
  const constraints = schema.constraints ?? {};
  let result;
  switch (schema.kind) {
    case 'model': case 'optional': result = lowerSchema(schema.item); break;
    case 'nullable': result = { anyOf: [lowerSchema(schema.item), { type: 'null' }] }; break;
    case 'id': result = { type: 'string', minLength: 1 }; break;
    case 'datetime': result = { type: 'string', format: 'date-time' }; break;
    case 'boolean': result = { type: 'boolean' }; break;
    case 'enum': result = { type: 'string', enum: schema.values }; break;
    case 'string': result = { type: 'string', ...Object.fromEntries(['minLength','maxLength','pattern','format'].filter(key => constraints[key] !== undefined).map(key => [key, constraints[key]])) }; break;
    case 'int': case 'number': result = { type: schema.kind === 'int' ? 'integer' : 'number',
      ...(constraints.min === undefined ? {} : { minimum: constraints.min }), ...(constraints.max === undefined ? {} : { maximum: constraints.max }) }; break;
    case 'array': result = { type: 'array', items: lowerSchema(schema.item),
      ...(constraints.min === undefined ? {} : { minItems: constraints.min }), ...(constraints.max === undefined ? {} : { maxItems: constraints.max }) }; break;
    case 'input': case 'object': result = { type: 'object', properties: Object.fromEntries(Object.entries(schema.fields ?? {}).map(([key, child]) => [key, lowerSchema(child)])),
      required: Object.entries(schema.fields ?? {}).filter(([, child]) => child.kind !== 'optional').map(([key]) => key), additionalProperties: false }; break;
    default: throw new Error(`Unknown source SchemaIR kind: ${schema.kind}`);
  }
  if (schema.metadata) result['x-fple-metadata'] = schema.metadata;
  if (schema.name) result['x-fple-name'] = schema.name;
  return result;
}
function validationConstraints(schema, path = []) {
  const constraints = schema.constraints ?? {};
  const current = Object.fromEntries(['normalize','format','uniqueBy'].filter(key => constraints[key] !== undefined).map(key => [key, constraints[key]]));
  const result = Object.keys(current).length ? [{ path, ...current }] : [];
  if (schema.item) result.push(...validationConstraints(schema.item, schema.kind === 'array' ? [...path, '*'] : path));
  for (const [key, child] of Object.entries(schema.fields ?? {})) result.push(...validationConstraints(child, [...path, key]));
  return result;
}
const invariantIndex = new Map(boot.invariants);
const entities = boot.entities.map(([name, entity]) => ({ name, schema: internSchema(lowerSchema({ kind: 'object', fields: entity.fields })),
  immutable: entity.immutableFields, indexes: entity.index, unique: entity.unique,
  invariants: invariantIndex.get(name) ?? [], schemaVersion: entity.schemaVersion,
  validation: validationConstraints({ kind: 'object', fields: entity.fields }),
}));
const signals = boot.events.map(([name, event]) => ({ name, schema: internSchema(lowerSchema(event.payload)), validation: validationConstraints(event.payload), metadata: event.metadata }));
const hostPorts = boot.ports.map(([name, port]) => ({ name, inputSchema: internSchema(lowerSchema(port.input)), outputSchema: internSchema(lowerSchema(port.output)),
  inputValidation: validationConstraints(port.input), outputValidation: validationConstraints(port.output) }));
const definition = { sourceRevision, sourceDigest: digest(files.map(file => `${file.path}\0${file.hash}`).join('\n')),
  schemas, operations, routes: clean(routes), screens: screens.sort((a, b) => a.path.localeCompare(b.path, 'en')),
  roles: clean({ platform: roles.PLATFORM_ROLE_DEFAULTS, seller: roles.SELLER_ROLE_DEFAULTS }),
  policies: clean(policies), entities, signals, hostPorts, events: snapshot.v1.events,
};
const inventory = { sourceRevision, sourceDigest: definition.sourceDigest, counts: {
  files: files.length, symbols: symbolCount, schemas: schemas.length, operations: operations.length, routes: routes.length,
  screens: screens.length, entities: definition.entities.length, events: definition.events.length,
  owners: [...new Set(operations.map(operation => operation.owner))].length,
}, files };
await mkdir(join(app, 'definition'), { recursive: true });
for (const [name, value] of [['system.json', definition], ['source.json', inventory]]) {
  // One fact per line rather than a recursively expanded copy of the source.
  const output = '{\n' + Object.entries(value).map(([key, item]) =>
    `  ${JSON.stringify(key)}: ` + (Array.isArray(item)
      ? '[\n' + item.map(row => '    ' + JSON.stringify(row)).join(',\n') + '\n  ]'
      : JSON.stringify(item))).join(',\n') + '\n}\n';
  const target = join(app, 'definition', name);
  if (check) {
    if (await readFile(target, 'utf8') !== output) throw new Error(`Stale definition: ${target}`);
  } else await writeFile(target, output);
}
console.log(JSON.stringify(inventory.counts));
