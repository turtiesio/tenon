"""Shared I/O only; all task behavior is local to each reference."""
import re
import sys

def match(pattern, value):
    return re.fullmatch(pattern, value) is not None

def fail(code, message='invalid input'):
    print(message, file=sys.stderr)
    raise SystemExit(code)

def lf_lines(data, cr=True):
    result = data.split('\n')
    if result[-1] == '':
        result.pop()
    return [s[:-1] if cr and s.endswith('\r') else s for s in result]

def incoming():
    for raw in sys.stdin.buffer:
        s = raw.decode('ascii')
        if s.endswith('\n'): s = s[:-1]
        if s.endswith('\r'): s = s[:-1]
        yield s

def say(text):
    print(text, flush=True)

def money(cents):
    return ('-' if cents < 0 else '') + str(abs(cents)//100) + '.%02d' % (abs(cents)%100)
