import re
import sys

sys.setrecursionlimit(10000)


class ExpressionError(Exception):
    pass


class Parser:
    def __init__(self, expression):
        self.tokens = []
        position = 0
        while position < len(expression):
            match = re.match(r' +|[0-9]+|[a-z][a-z0-9_]*|[+*/%()-]', expression[position:])
            if match is None:
                raise ExpressionError('syntax')
            token = match.group()
            position += len(token)
            if token[0] == ' ':
                continue
            if token[0].isdigit() and len(token) > 15:
                raise ExpressionError('syntax')
            self.tokens.append(token)
        self.position = 0

    def peek(self):
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def parse(self, level=0):
        if level < 2:
            node = self.parse(level + 1)
            operators = ('+', '-') if level == 0 else ('*', '/', '%')
            while self.peek() in operators:
                operator = self.peek()
                self.position += 1
                node = (operator, node, self.parse(level + 1))
            return node
        token = self.peek()
        self.position += 1
        if token == '-':
            return ('negate', self.parse(2))
        if token == '(':
            node = self.parse()
            if self.peek() != ')':
                raise ExpressionError('syntax')
            self.position += 1
            return node
        if token is not None and token[0].isdigit():
            return ('number', int(token))
        if token is not None and token[0].islower():
            return ('name', token)
        raise ExpressionError('syntax')


def evaluate(node, variables):
    operator = node[0]
    if operator == 'number':
        return node[1]
    if operator == 'name':
        if node[1] not in variables:
            raise ExpressionError('undefined ' + node[1])
        return variables[node[1]]
    left = evaluate(node[1], variables)
    if operator == 'negate':
        return -left
    right = evaluate(node[2], variables)
    if operator == '+':
        result = left + right
    elif operator == '-':
        result = left - right
    elif operator == '*':
        result = left * right
    else:
        if right == 0:
            raise ExpressionError('division by zero')
        quotient = abs(left) // abs(right)
        if (left < 0) != (right < 0):
            quotient = -quotient
        result = quotient if operator == '/' else left - quotient * right
    if abs(result) > 999999999999999:
        raise ExpressionError('overflow')
    return result


def main():
    variables = {}
    expressions = []
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg == '-D':
                definition = next(args)
                if not re.fullmatch(r'[a-z][a-z0-9_]{0,15}=-?[0-9]{1,15}', definition):
                    raise ValueError
                name, value = definition.split('=')
                variables[name] = int(value)
            else:
                expressions.append(arg)
        if len(expressions) != 1:
            raise ValueError
    except (ValueError, StopIteration):
        print('Invalid arguments', file=sys.stderr)
        return 2
    try:
        parser = Parser(expressions[0])
        tree = parser.parse()
        if parser.peek() is not None:
            raise ExpressionError('syntax')
        print(evaluate(tree, variables))
        return 0
    except ExpressionError as error:
        print('error: ' + str(error))
        return 1


if __name__ == '__main__':
    sys.exit(main())
