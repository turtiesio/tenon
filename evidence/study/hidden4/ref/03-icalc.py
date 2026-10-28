"""Private specification reference: tokenize, parse completely, then evaluate."""
import re
import sys
sys.setrecursionlimit(10000)
LIMIT = 999999999999999

class ExpressionError(Exception): pass

class Parser:
    def __init__(self, text):
        self.tokens = []
        i = 0
        while i < len(text):
            c = text[i]
            if c == ' ': i += 1; continue
            m = re.match(r'[0-9]+|[a-z][a-z0-9_]*|[+*/%()\-]', text[i:])
            if m is None: raise ExpressionError('syntax')
            token = m[0]
            if token[0].isdigit() and len(token) > 15: raise ExpressionError('syntax')
            self.tokens.append(token)
            i += len(token)
        self.tokens.append(None)
        self.pos = 0

    def take(self):
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def expr(self, level=0):
        if level == 2:
            if self.tokens[self.pos] == '-':
                self.take()
                return ('neg', self.expr(2))
            t = self.take()
            if t == '(':
                node = self.expr()
                if self.take() != ')': raise ExpressionError('syntax')
                return node
            if t is not None and re.fullmatch(r'[0-9]+', t): return ('number', int(t))
            if t is not None and re.fullmatch(r'[a-z][a-z0-9_]*', t): return ('name', t)
            raise ExpressionError('syntax')
        left = self.expr(level+1)
        operators = ('+', '-') if level == 0 else ('*', '/', '%')
        while self.tokens[self.pos] in operators:
            op = self.take()
            left = (op, left, self.expr(level+1))
        return left

def evaluate(node, env):
    op = node[0]
    if op == 'number': return node[1]
    if op == 'name':
        if node[1] not in env: raise ExpressionError('undefined '+node[1])
        return env[node[1]]
    if op == 'neg': return -evaluate(node[1], env)
    a = evaluate(node[1], env)
    b = evaluate(node[2], env)
    if op == '+': value = a+b
    elif op == '-': value = a-b
    elif op == '*': value = a*b
    else:
        if b == 0: raise ExpressionError('division by zero')
        q = (abs(a)//abs(b)) * (-1 if (a < 0) != (b < 0) else 1)
        value = q if op == '/' else a-q*b
    if abs(value) > LIMIT: raise ExpressionError('overflow')
    return value

def main():
    env, expressions = {}, []
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg == '-D':
                value = next(args)
                if not re.fullmatch(r'[a-z][a-z0-9_]{0,15}=-?[0-9]{1,15}', value): raise ValueError()
                name, number = value.split('=')
                env[name] = int(number)
            else: expressions.append(arg)
        if len(expressions) != 1: raise ValueError()
    except (ValueError, StopIteration):
        print('usage error', file=sys.stderr)
        return 2
    try:
        p = Parser(expressions[0])
        tree = p.expr()
        if p.tokens[p.pos] is not None: raise ExpressionError('syntax')
        print(evaluate(tree, env))
        return 0
    except ExpressionError as exc:
        print('error: '+str(exc))
        return 1

if __name__ == '__main__': sys.exit(main())
