# calc: tokenizer, recursive-descent parser, tree-walking evaluator.
import sys
import threading

MAX_DEPTH = 1000
MAX_NESTING = 200
INT_MAX = 9223372036854775807
INT_MIN = -9223372036854775808


class CalcError(Exception):
    pass


KEYWORDS = {"let", "fn", "if", "then", "else"}
SIMPLE = {"+": "+", "-": "-", "*": "*", "/": "/", "%": "%", "(": "(", ")": ")", ",": ","}


def utf8_len(c):
    return 4 if c >= 240 else 3 if c >= 224 else 2 if c >= 192 else 1


# A token is (kind, text, num, col); kind is the keyword/operator text, "num",
# "ident" or "end". Columns are 1-based byte offsets.
def tokenize(line):
    s = line.encode()
    n = len(s)
    toks = []
    i = 0
    while i < n:
        c = s[i]
        start = i
        if c in b" \t\r":
            i += 1
        elif c == 0x2F and i + 1 < n and s[i + 1] == 0x2F:
            i = n
        elif 0x30 <= c <= 0x39:
            while i < n and 0x30 <= s[i] <= 0x39:
                i += 1
            text = s[start:i].decode()
            v = int(text)
            if v > INT_MAX:
                raise CalcError("integer literal %s is too large at column %d" % (text, start + 1))
            toks.append(("num", text, v, start + 1))
        elif 0x61 <= c <= 0x7A or 0x41 <= c <= 0x5A or c == 0x5F:
            while i < n and (0x61 <= s[i] <= 0x7A or 0x41 <= s[i] <= 0x5A or s[i] == 0x5F or 0x30 <= s[i] <= 0x39):
                i += 1
            text = s[start:i].decode()
            toks.append((text if text in KEYWORDS else "ident", text, 0, start + 1))
        else:
            ch = chr(c)
            nxt = chr(s[i + 1]) if i + 1 < n else ""
            kind = None
            width = 1
            if ch in SIMPLE:
                kind = ch
            elif ch == "=":
                kind, width = ("==", 2) if nxt == "=" else ("=", 1)
            elif ch == "!":
                if nxt == "=":
                    kind, width = "!=", 2
            elif ch == "<":
                kind, width = ("<=", 2) if nxt == "=" else ("<", 1)
            elif ch == ">":
                kind, width = (">=", 2) if nxt == "=" else (">", 1)
            if kind is None:
                bad = s[i:min(i + utf8_len(c), n)].decode(errors="replace")
                raise CalcError("unexpected character '%s' at column %d" % (bad, i + 1))
            toks.append((kind, s[i:i + width].decode(), 0, i + 1))
            i += width
    toks.append(("end", "", 0, n + 1))
    return toks


# Expressions: ("num", n) ("var", name) ("neg", e) ("bin", op, l, r)
#              ("if", c, a, b) ("call", name, args)
class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.pos = 0
        self.depth = 0

    def peek(self):
        return self.toks[self.pos]

    def next(self):
        t = self.toks[self.pos]
        if t[0] != "end":
            self.pos += 1
        return t

    @staticmethod
    def describe(t):
        return "end of line" if t[0] == "end" else "'%s'" % t[1]

    def unexpected(self, t, wanted):
        return CalcError("expected %s but found %s at column %d" % (wanted, self.describe(t), t[3]))

    def expect(self, kind, wanted):
        t = self.peek()
        if t[0] != kind:
            raise self.unexpected(t, wanted)
        return self.next()

    def finish(self):
        t = self.peek()
        if t[0] != "end":
            raise CalcError("unexpected %s at column %d" % (self.describe(t), t[3]))

    def enter(self):
        self.depth += 1
        if self.depth > MAX_NESTING:
            raise CalcError("expression nested too deeply (limit %d) at column %d" % (MAX_NESTING, self.peek()[3]))

    def expr(self):
        self.enter()
        r = self.equality()
        self.depth -= 1
        return r

    def equality(self):
        left = self.relational()
        while self.peek()[0] in ("==", "!="):
            op = self.next()[0]
            left = ("bin", op, left, self.relational())
        return left

    def relational(self):
        left = self.additive()
        while self.peek()[0] in ("<", "<=", ">", ">="):
            op = self.next()[0]
            left = ("bin", op, left, self.additive())
        return left

    def additive(self):
        left = self.term()
        while self.peek()[0] in ("+", "-"):
            op = self.next()[0]
            left = ("bin", op, left, self.term())
        return left

    def term(self):
        left = self.unary()
        while self.peek()[0] in ("*", "/", "%"):
            op = self.next()[0]
            left = ("bin", op, left, self.unary())
        return left

    def unary(self):
        if self.peek()[0] == "-":
            self.enter()
            self.next()
            operand = self.unary()
            self.depth -= 1
            return ("neg", operand)
        return self.primary()

    def call_args(self):
        args = []
        if self.peek()[0] == ")":
            self.next()
            return args
        while True:
            args.append(self.expr())
            if self.peek()[0] == ",":
                self.next()
            else:
                self.expect(")", "',' or ')'")
                break
        return args

    def primary(self):
        t = self.peek()
        k = t[0]
        if k == "num":
            self.next()
            return ("num", t[2])
        if k == "ident":
            self.next()
            if self.peek()[0] == "(":
                self.next()
                return ("call", t[1], self.call_args())
            return ("var", t[1])
        if k == "(":
            self.next()
            inner = self.expr()
            self.expect(")", "')'")
            return inner
        if k == "if":
            self.next()
            cond = self.expr()
            self.expect("then", "'then'")
            yes = self.expr()
            self.expect("else", "'else'")
            no = self.expr()
            return ("if", cond, yes, no)
        raise self.unexpected(t, "an expression")

    def params(self):
        names = []
        if self.peek()[0] == ")":
            self.next()
            return names
        while True:
            t = self.expect("ident", "a parameter name")
            if t[1] in names:
                raise CalcError("duplicate parameter '%s' at column %d" % (t[1], t[3]))
            names.append(t[1])
            if self.peek()[0] == ",":
                self.next()
            else:
                self.expect(")", "',' or ')'")
                break
        return names


def parse_line(line):
    toks = tokenize(line)
    if len(toks) == 1:
        return None
    p = Parser(toks)
    first = p.peek()
    if first[0] == "let":
        p.next()
        name = p.expect("ident", "a variable name")
        p.expect("=", "'='")
        e = p.expr()
        p.finish()
        return ("defvar", name[1], e)
    if first[0] == "fn":
        p.next()
        name = p.expect("ident", "a function name")
        p.expect("(", "'('")
        params = p.params()
        p.expect("=", "'='")
        body = p.expr()
        p.finish()
        return ("deffn", name[1], params, body)
    e = p.expr()
    p.finish()
    return ("show", e)


def check(v, msg):
    if v > INT_MAX or v < INT_MIN:
        raise CalcError(msg)
    return v


def tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


class Interp:
    def __init__(self):
        self.vars = {}
        self.fns = {}

    def eval(self, e, env, depth):
        tag = e[0]
        if tag == "num":
            return e[1]
        if tag == "bin":
            a = self.eval(e[2], env, depth)
            b = self.eval(e[3], env, depth)
            op = e[1]
            if op == "+":
                return check(a + b, "integer overflow in %d + %d" % (a, b))
            if op == "-":
                return check(a - b, "integer overflow in %d - %d" % (a, b))
            if op == "*":
                return check(a * b, "integer overflow in %d * %d" % (a, b))
            if op == "/":
                if b == 0:
                    raise CalcError("division by zero")
                return check(tdiv(a, b), "integer overflow in %d / -1" % a)
            if op == "%":
                if b == 0:
                    raise CalcError("division by zero")
                return a - b * tdiv(a, b)
            if op == "==":
                return int(a == b)
            if op == "!=":
                return int(a != b)
            if op == "<":
                return int(a < b)
            if op == "<=":
                return int(a <= b)
            if op == ">":
                return int(a > b)
            return int(a >= b)
        if tag == "var":
            name = e[1]
            if name in env:
                return env[name]
            if name in self.vars:
                return self.vars[name]
            if name in self.fns:
                raise CalcError("'%s' is a function, not a variable" % name)
            raise CalcError("unknown variable '%s'" % name)
        if tag == "neg":
            x = self.eval(e[1], env, depth)
            return check(-x, "integer overflow in -(%d)" % x)
        if tag == "if":
            if self.eval(e[1], env, depth) != 0:
                return self.eval(e[2], env, depth)
            return self.eval(e[3], env, depth)
        return self.call(e[1], e[2], env, depth)

    def call(self, name, args, env, depth):
        f = self.fns.get(name)
        if f is None:
            if name in self.vars or name in env:
                raise CalcError("'%s' is not a function" % name)
            raise CalcError("unknown function '%s'" % name)
        params, body = f
        if len(args) != len(params):
            raise CalcError("function '%s' takes %d argument%s, got %d" % (
                name, len(params), "" if len(params) == 1 else "s", len(args)))
        inner = {}
        for i in range(len(args)):
            inner[params[i]] = self.eval(args[i], env, depth)
        if depth >= MAX_DEPTH:
            raise CalcError("call depth limit (%d) exceeded in '%s'" % (MAX_DEPTH, name))
        return self.eval(body, inner, depth + 1)

    # Returns the text to print, or None.
    def run(self, stmt):
        tag = stmt[0]
        if tag == "defvar":
            name = stmt[1]
            if name in self.fns:
                raise CalcError("'%s' is already defined as a function" % name)
            self.vars[name] = self.eval(stmt[2], {}, 0)
            return None
        if tag == "deffn":
            name = stmt[1]
            if name in self.vars:
                raise CalcError("'%s' is already defined as a variable" % name)
            self.fns[name] = (stmt[2], stmt[3])
            return None
        return str(self.eval(stmt[1], {}, 0))


def main():
    interp = Interp()
    out = []
    statements = errors = 0
    for raw in sys.stdin.buffer:
        line = raw
        if line.endswith(b"\n"):
            line = line[:-1]
            if line.endswith(b"\r"):
                line = line[:-1]
        try:
            stmt = parse_line(line.decode())
            if stmt is None:
                continue
            text = interp.run(stmt)
            if text is not None:
                out.append(text)
            statements += 1
        except CalcError as ex:
            statements += 1
            errors += 1
            out.append("error: %s" % ex)
    out.append("bye (%d statements, %d errors)" % (statements, errors))
    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()
    return 1 if errors else 0


def entry():
    global status
    status = main()


if __name__ == "__main__":
    sys.setrecursionlimit(200000)
    threading.stack_size(512 * 1024 * 1024)
    status = 0
    t = threading.Thread(target=entry)
    t.start()
    t.join()
    sys.exit(status)
