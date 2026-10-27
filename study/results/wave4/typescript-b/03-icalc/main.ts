type Token =
  | { kind: "num"; value: bigint }
  | { kind: "name"; name: string }
  | { kind: "op"; op: string };

type Node =
  | { kind: "num"; value: bigint }
  | { kind: "var"; name: string }
  | { kind: "neg"; operand: Node }
  | { kind: "bin"; op: string; left: Node; right: Node };

class SyntaxErr extends Error {}

class EvalErr extends Error {}

const LIMIT = 999_999_999_999_999n;

function usage(msg: string): never {
  process.stderr.write(`icalc: ${msg}\nusage: icalc [-D NAME=VALUE]... EXPR\n`);
  process.exit(2);
}

function tokenize(src: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  while (i < src.length) {
    const ch = src[i];
    if (ch === " ") {
      i++;
    } else if (ch >= "0" && ch <= "9") {
      let j = i;
      while (j < src.length && src[j] >= "0" && src[j] <= "9") j++;
      if (j - i > 15) throw new SyntaxErr();
      tokens.push({ kind: "num", value: BigInt(src.slice(i, j)) });
      i = j;
    } else if (ch >= "a" && ch <= "z") {
      let j = i + 1;
      while (j < src.length && /[a-z0-9_]/.test(src[j])) j++;
      tokens.push({ kind: "name", name: src.slice(i, j) });
      i = j;
    } else if ("+-*/%()".includes(ch)) {
      tokens.push({ kind: "op", op: ch });
      i++;
    } else {
      throw new SyntaxErr();
    }
  }
  return tokens;
}

class Parser {
  private pos = 0;
  private readonly tokens: Token[];

  constructor(tokens: Token[]) {
    this.tokens = tokens;
  }

  parseAll(): Node {
    const node = this.expr();
    if (this.pos !== this.tokens.length) throw new SyntaxErr();
    return node;
  }

  private peekOp(): string | null {
    const t = this.tokens[this.pos];
    return t !== undefined && t.kind === "op" ? t.op : null;
  }

  private expr(): Node {
    let left = this.term();
    for (let op = this.peekOp(); op === "+" || op === "-"; op = this.peekOp()) {
      this.pos++;
      left = { kind: "bin", op, left, right: this.term() };
    }
    return left;
  }

  private term(): Node {
    let left = this.unary();
    for (let op = this.peekOp(); op === "*" || op === "/" || op === "%"; op = this.peekOp()) {
      this.pos++;
      left = { kind: "bin", op, left, right: this.unary() };
    }
    return left;
  }

  private unary(): Node {
    if (this.peekOp() === "-") {
      this.pos++;
      return { kind: "neg", operand: this.unary() };
    }
    return this.primary();
  }

  private primary(): Node {
    const t = this.tokens[this.pos];
    if (t === undefined) throw new SyntaxErr();
    this.pos++;
    if (t.kind === "num") return { kind: "num", value: t.value };
    if (t.kind === "name") return { kind: "var", name: t.name };
    if (t.op === "(") {
      const inner = this.expr();
      if (this.peekOp() !== ")") throw new SyntaxErr();
      this.pos++;
      return inner;
    }
    throw new SyntaxErr();
  }
}

function evaluate(node: Node, vars: Map<string, bigint>): bigint {
  switch (node.kind) {
    case "num":
      return node.value;
    case "var": {
      const v = vars.get(node.name);
      if (v === undefined) throw new EvalErr(`undefined ${node.name}`);
      return v;
    }
    case "neg":
      return -evaluate(node.operand, vars);
    case "bin": {
      const a = evaluate(node.left, vars);
      const b = evaluate(node.right, vars);
      let r: bigint;
      switch (node.op) {
        case "+": r = a + b; break;
        case "-": r = a - b; break;
        case "*": r = a * b; break;
        default:
          if (b === 0n) throw new EvalErr("division by zero");
          // BigInt division truncates toward zero; % takes the sign of a.
          r = node.op === "/" ? a / b : a % b;
      }
      if (r > LIMIT || r < -LIMIT) throw new EvalErr("overflow");
      return r;
    }
  }
}

function main(): void {
  const args = process.argv.slice(2);
  const vars = new Map<string, bigint>();
  const exprs: string[] = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "-D") {
      if (i + 1 >= args.length) usage("-D requires a value");
      const def = args[++i];
      const m = /^([a-z][a-z0-9_]{0,15})=(-?[0-9]{1,15})$/.exec(def);
      if (m === null) usage(`malformed definition: ${def}`);
      vars.set(m[1], BigInt(m[2]));
    } else {
      exprs.push(args[i]);
    }
  }
  if (exprs.length !== 1) usage(exprs.length === 0 ? "missing EXPR" : "more than one EXPR");

  let ast: Node;
  try {
    ast = new Parser(tokenize(exprs[0])).parseAll();
  } catch (err) {
    if (!(err instanceof SyntaxErr)) throw err;
    process.stdout.write("error: syntax\n");
    process.exit(1);
  }
  try {
    process.stdout.write(`${evaluate(ast, vars)}\n`);
  } catch (err) {
    if (!(err instanceof EvalErr)) throw err;
    process.stdout.write(`error: ${err.message}\n`);
    process.exit(1);
  }
}

main();
