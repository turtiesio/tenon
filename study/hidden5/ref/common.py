"""Only I/O and validation primitives shared by private references."""
import re
import sys

def fail(code):
    print('invalid input or arguments', file=sys.stderr)
    raise SystemExit(code)

def match(pattern, value):
    return re.fullmatch(pattern, value) is not None

def lines(text):
    if not text:
        return []
    result = text.split('\n')
    if result[-1] == '':
        result.pop()
    return [x[:-1] if x.endswith('\r') else x for x in result]

def stdin_lines():
    return lines(sys.stdin.buffer.read().decode('utf-8'))

def money(cents):
    return f'{abs(cents)//100}.{abs(cents)%100:02d}'

def emit(response):
    print(response, flush=True)
