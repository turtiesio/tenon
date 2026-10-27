import re
import sys

LIMIT = 10**15 - 1
DEFINE_RE = re.compile(r"([a-z][a-z0-9_]{0,15})=(-?[0-9]{1,15})")
TOKEN_RE = re.compile(r"([0-9]+)|([a-z][a-z0-9_]*)|([-+*/%()])")

sys.setrecursionlimit(10000)


class SyntaxErr(Exception):
    pass


class EvalErr(Exception):
    pass


def usage(msg):
    print(f"icalc: {msg}", file=sys.stderr)
    sys.exit(2)


def parse_args(argv):
    variables = {}
    exprs = []
    i = 0
    while i < len(argv):
        if argv[i] == "-D":
            if i + 1 >= len(argv):
                usage("-D needs a value")
            m = DEFINE_RE.fullmatch(argv[i + 1])
            if not m:
                usage(f"bad -D value: {argv[i + 1]!r}")
            variables[m.group(1)] = int(m.group(2))
            i += 2
        else:
            exprs.append(argv[i])
            i += 1
    if len(exprs) != 1:
        usage("expected exactly one expression")
    return variables, exprs[0]


def tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        if text[pos] == " ":
            pos += 1
            continue
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise SyntaxErr
        number, name, op = m.groups()
        if number is not None:
            if len(number) > 15:
                raise SyntaxErr
            tokens.append(("num", int(number)))
        elif name is not None:
            tokens.append(("name", name))
        else:
            tokens.append(("op", op))
        pos = m.end()
    return tokens


class Parser:
    """Recursive-descent parser producing a tuple-based AST."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek_op(self):
        if self.pos < len(self.tokens):
            kind, value = self.tokens[self.pos]
            if kind == "op":
                return value
        return None

    def parse(self):
        node = self.expr()
        if self.pos != len(self.tokens):
            raise SyntaxErr
        return node

    def binary(self, operand, ops):
        node = operand()
        while self.peek_op() in ops:
            op = self.tokens[self.pos][1]
            self.pos += 1
            node = ("bin", op, node, operand())
        return node

    def expr(self):
        return self.binary(self.term, ("+", "-"))

    def term(self):
        return self.binary(self.unary, ("*", "/", "%"))

    def unary(self):
        if self.peek_op() == "-":
            self.pos += 1
            return ("neg", self.unary())
        return self.primary()

    def primary(self):
        if self.pos >= len(self.tokens):
            raise SyntaxErr
        kind, value = self.tokens[self.pos]
        self.pos += 1
        if kind == "num":
            return ("num", value)
        if kind == "name":
            return ("var", value)
        if value == "(":
            node = self.expr()
            if self.peek_op() != ")":
                raise SyntaxErr
            self.pos += 1
            return node
        raise SyntaxErr


def apply_op(op, a, b):
    if op == "+":
        result = a + b
    elif op == "-":
        result = a - b
    elif op == "*":
        result = a * b
    else:
        if b == 0:
            raise EvalErr("division by zero")
        quotient = abs(a) // abs(b)
        if (a < 0) != (b < 0):
            quotient = -quotient
        result = quotient if op == "/" else a - quotient * b
    if abs(result) > LIMIT:
        raise EvalErr("overflow")
    return result


def evaluate(node, variables):
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "var":
        if node[1] not in variables:
            raise EvalErr(f"undefined {node[1]}")
        return variables[node[1]]
    if kind == "neg":
        return -evaluate(node[1], variables)
    left = evaluate(node[2], variables)
    right = evaluate(node[3], variables)
    return apply_op(node[1], left, right)


def main():
    variables, text = parse_args(sys.argv[1:])
    try:
        tree = Parser(tokenize(text)).parse()
        print(evaluate(tree, variables))
    except SyntaxErr:
        print("error: syntax")
        sys.exit(1)
    except EvalErr as e:
        print(f"error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
