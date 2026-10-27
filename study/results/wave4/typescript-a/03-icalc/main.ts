const args = process.argv.slice(2);
const variables = new Map<string, bigint>();
let expression: string | undefined;
function usage(): never { console.error('Invalid arguments'); process.exit(2); }
for (let i = 0; i < args.length; i++) {
  if (args[i] === '-D') {
    const value = args[++i];
    if (value === undefined || !/^[a-z][a-z0-9_]{0,15}=-?[0-9]{1,15}$/.test(value)) usage();
    const [name, number] = value.split('=');
    variables.set(name, BigInt(number));
  } else {
    if (expression !== undefined) usage();
    expression = args[i];
  }
}
if (expression === undefined) usage();
type Node = {kind: 'number'; value: bigint} | {kind: 'name'; name: string} | {kind: 'neg'; child: Node} | {kind: 'binary'; op: string; left: Node; right: Node};
let pos = 0;
const source = expression;
function peek(): string { while (source[pos] === ' ') pos++; return source[pos] ?? ''; }
function primary(): Node {
  const c = peek();
  if (c === '(') { pos++; const node = expr(); if (peek() !== ')') throw new Error('syntax'); pos++; return node; }
  if (/[0-9]/.test(c) && c !== '') {
    const start = pos; while (pos < source.length && /[0-9]/.test(source[pos])) pos++;
    if (pos - start > 15) throw new Error('syntax');
    return {kind: 'number', value: BigInt(source.slice(start, pos))};
  }
  if (/[a-z]/.test(c) && c !== '') {
    const start = pos++; while (pos < source.length && /[a-z0-9_]/.test(source[pos])) pos++;
    return {kind: 'name', name: source.slice(start, pos)};
  }
  throw new Error('syntax');
}
function unary(): Node { if (peek() === '-') { pos++; return {kind: 'neg', child: unary()}; } return primary(); }
function term(): Node {
  let left = unary();
  while (['*', '/', '%'].includes(peek())) { const op = source[pos++]; left = {kind: 'binary', op, left, right: unary()}; }
  return left;
}
function expr(): Node {
  let left = term();
  while (['+', '-'].includes(peek())) { const op = source[pos++]; left = {kind: 'binary', op, left, right: term()}; }
  return left;
}
function evaluate(node: Node): bigint {
  switch (node.kind) {
    case 'number': return node.value;
    case 'name': { const value = variables.get(node.name); if (value === undefined) throw new Error(`undefined ${node.name}`); return value; }
    case 'neg': return -evaluate(node.child);
    case 'binary': {
      const a = evaluate(node.left), b = evaluate(node.right);
      if ((node.op === '/' || node.op === '%') && b === 0n) throw new Error('division by zero');
      let result: bigint;
      switch (node.op) {
        case '+': result = a + b; break;
        case '-': result = a - b; break;
        case '*': result = a * b; break;
        case '/': result = a / b; break;
        default: result = a % b;
      }
      if (result > 999999999999999n || result < -999999999999999n) throw new Error('overflow');
      return result;
    }
  }
}
try {
  const tree = expr();
  if (peek() !== '') throw new Error('syntax');
  console.log(evaluate(tree).toString());
} catch (error) { console.log(`error: ${(error as Error).message}`); process.exitCode = 1; }
