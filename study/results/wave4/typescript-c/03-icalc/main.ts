const LIMIT = 999999999999999n;

type Token =
  | { kind: "num"; value: bigint }
  | { kind: "name"; name: string }
  | { kind: "op"; op: string };

type Node =
  | { kind: "num"; value: bigint }
  | { kind: "var"; name: string }
  | { kind: "neg"; operand: Node }
  | { kind: "bin"; op: string; left: Node; right: Node };

// Raised for any expression error; the message is the reason printed after "error: ".
class ExprError extends Error {}

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
      if (j - i > 15) throw new ExprError("syntax");
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
      throw new ExprError("syntax");
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

  parse(): Node {
    const node = this.expr();
    if (this.pos < this.tokens.length) throw new ExprError("syntax");
    return node;
  }

  private peekOp(...ops: string[]): string | null {
    const t = this.tokens[this.pos];
    return t !== undefined && t.kind === "op" && ops.includes(t.op) ? t.op : null;
  }

  private expr(): Node {
    let left = this.term();
    for (let op = this.peekOp("+", "-"); op !== null; op = this.peekOp("+", "-")) {
      this.pos++;
      left = { kind: "bin", op, left, right: this.term() };
    }
    return left;
  }

  private term(): Node {
    let left = this.unary();
    for (let op = this.peekOp("*", "/", "%"); op !== null; op = this.peekOp("*", "/", "%")) {
      this.pos++;
      left = { kind: "bin", op, left, right: this.unary() };
    }
    return left;
  }

  private unary(): Node {
    if (this.peekOp("-") !== null) {
      this.pos++;
      return { kind: "neg", operand: this.unary() };
    }
    return this.primary();
  }

  private primary(): Node {
    const t = this.tokens[this.pos];
    if (t === undefined) throw new ExprError("syntax");
    if (t.kind === "num") {
      this.pos++;
      return { kind: "num", value: t.value };
    }
    if (t.kind === "name") {
      this.pos++;
      return { kind: "var", name: t.name };
    }
    if (t.op === "(") {
      this.pos++;
      const inner = this.expr();
      if (this.peekOp(")") === null) throw new ExprError("syntax");
      this.pos++;
      return inner;
    }
    throw new ExprError("syntax");
  }
}

function checked(n: bigint): bigint {
  if (n > LIMIT || n < -LIMIT) throw new ExprError("overflow");
  return n;
}

function evaluate(node: Node, vars: Map<string, bigint>): bigint {
  switch (node.kind) {
    case "num":
      return node.value;
    case "var": {
      const v = vars.get(node.name);
      if (v === undefined) throw new ExprError(`undefined ${node.name}`);
      return v;
    }
    case "neg":
      return -evaluate(node.operand, vars);
    case "bin": {
      const a = evaluate(node.left, vars);
      const b = evaluate(node.right, vars);
      switch (node.op) {
        case "+": return checked(a + b);
        case "-": return checked(a - b);
        case "*": return checked(a * b);
        case "/":
        case "%":
          if (b === 0n) throw new ExprError("division by zero");
          // BigInt division truncates toward zero and % takes the sign of the dividend.
          return checked(node.op === "/" ? a / b : a % b);
      }
    }
  }
  throw new ExprError("syntax");
}

function main(): number {
  const args = process.argv.slice(2);
  const vars = new Map<string, bigint>();
  const exprs: string[] = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "-D") {
      if (i + 1 >= args.length) {
        console.error("icalc: -D needs a value");
        return 2;
      }
      const def = args[++i];
      const m = /^([a-z][a-z0-9_]{0,15})=(-?[0-9]{1,15})$/.exec(def);
      if (m === null) {
        console.error(`icalc: malformed definition: ${def}`);
        return 2;
      }
      vars.set(m[1], BigInt(m[2]));
    } else {
      exprs.push(args[i]);
    }
  }
  if (exprs.length !== 1) {
    console.error("icalc: expected exactly one expression");
    return 2;
  }

  try {
    const ast = new Parser(tokenize(exprs[0])).parse();
    console.log(evaluate(ast, vars).toString());
    return 0;
  } catch (e) {
    if (e instanceof ExprError) {
      console.log(`error: ${e.message}`);
      return 1;
    }
    throw e;
  }
}

process.exitCode = main();
