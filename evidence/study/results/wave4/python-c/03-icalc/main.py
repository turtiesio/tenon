"""icalc: evaluate one integer arithmetic expression."""
import re
import sys
from dataclasses import dataclass

USAGE = "usage: icalc [-D NAME=VALUE]... EXPR"
LIMIT = 10**15 - 1
DEFINE_RE = re.compile(r"([a-z][a-z0-9_]{0,15})=(-?[0-9]{1,15})")
TOKEN_RE = re.compile(r"(?P<num>[0-9]+)|(?P<name>[a-z][a-z0-9_]*)|(?P<op>[-+*/%()])")


class UsageError(Exception):
    pass


class SyntaxErr(Exception):
    pass


class EvalError(Exception):
    pass


# AST nodes
@dataclass
class Num:
    value: int


@dataclass
class Name:
    name: str


@dataclass
class Neg:
    operand: object


@dataclass
class BinOp:
    op: str
    left: object
    right: object


def tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        if text[pos] == " ":
            pos += 1
            continue
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise SyntaxErr()
        if m.lastgroup == "num":
            if len(m.group()) > 15:
                raise SyntaxErr()
            tokens.append(("num", int(m.group())))
        else:
            tokens.append((m.lastgroup, m.group()))
        pos = m.end()
    return tokens


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def take(self):
        tok = self.peek()
        if tok[0] is None:
            raise SyntaxErr()
        self.pos += 1
        return tok

    def parse(self):
        node = self.expr()
        if self.pos != len(self.tokens):
            raise SyntaxErr()
        return node

    def expr(self):
        node = self.term()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.take()[1]
            node = BinOp(op, node, self.term())
        return node

    def term(self):
        node = self.unary()
        while self.peek() in (("op", "*"), ("op", "/"), ("op", "%")):
            op = self.take()[1]
            node = BinOp(op, node, self.unary())
        return node

    def unary(self):
        # Iterative over the minus run so long "----x" chains do not recurse deeply.
        count = 0
        while self.peek() == ("op", "-"):
            self.take()
            count += 1
        node = self.primary()
        for _ in range(count):
            node = Neg(node)
        return node

    def primary(self):
        kind, value = self.take()
        if kind == "num":
            return Num(value)
        if kind == "name":
            return Name(value)
        if (kind, value) == ("op", "("):
            node = self.expr()
            if self.take() != ("op", ")"):
                raise SyntaxErr()
            return node
        raise SyntaxErr()


def checked(value):
    if abs(value) > LIMIT:
        raise EvalError("overflow")
    return value


def truncdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def evaluate(node, env):
    if isinstance(node, Num):
        return node.value
    if isinstance(node, Name):
        if node.name not in env:
            raise EvalError(f"undefined {node.name}")
        return env[node.name]
    if isinstance(node, Neg):
        return -evaluate(node.operand, env)
    a = evaluate(node.left, env)
    b = evaluate(node.right, env)
    if node.op == "+":
        return checked(a + b)
    if node.op == "-":
        return checked(a - b)
    if node.op == "*":
        return checked(a * b)
    if b == 0:
        raise EvalError("division by zero")
    q = truncdiv(a, b)
    return checked(q if node.op == "/" else a - q * b)


def parse_args(argv):
    env, exprs = {}, []
    i = 0
    while i < len(argv):
        if argv[i] == "-D":
            if i + 1 >= len(argv):
                raise UsageError("-D requires a value")
            m = DEFINE_RE.fullmatch(argv[i + 1])
            if not m:
                raise UsageError(f"malformed definition: {argv[i + 1]!r}")
            env[m.group(1)] = int(m.group(2))
            i += 2
        else:
            exprs.append(argv[i])
            i += 1
    if len(exprs) != 1:
        raise UsageError("exactly one EXPR is required")
    return env, exprs[0]


def main(argv):
    try:
        env, text = parse_args(argv)
    except UsageError as e:
        print(f"icalc: {e}\n{USAGE}", file=sys.stderr)
        return 2
    try:
        tree = Parser(tokenize(text)).parse()
    except SyntaxErr:
        print("error: syntax")
        return 1
    try:
        result = evaluate(tree, env)
    except EvalError as e:
        print(f"error: {e}")
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    sys.exit(main(sys.argv[1:]))
