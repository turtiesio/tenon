"""Standard-library I/O and exact-token helpers; no task behavior shared."""
import re
import sys
from pathlib import Path

def match(pattern, text): return re.fullmatch(pattern, text, flags=re.ASCII) is not None

def fail(code=1):
    print('invalid input or arguments', file=sys.stderr)
    raise SystemExit(code)

def split(text):
    rows = text.split('\n')
    if rows[-1] == '': rows.pop()
    return [r[:-1] if r.endswith('\r') else r for r in rows]

def read(path):
    try: return Path(path).read_bytes().decode('utf-8')
    except (OSError, UnicodeError): fail()

def emit(s):
    sys.stdout.write(s)
    sys.stdout.flush()
