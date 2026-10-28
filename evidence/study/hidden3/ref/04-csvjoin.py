"""Private strict CSV parser and join reference (stdlib only)."""
from pathlib import Path
import sys

def parse(text):
    records = []; i = 0
    while i < len(text):
        if text[i] == '\n': i += 1; continue
        if text.startswith('\r\n',i): i += 2; continue
        row = []
        while True:
            field = []
            if i < len(text) and text[i] == '"':
                i += 1
                while True:
                    if i == len(text): raise ValueError('quote')
                    c = text[i]; i += 1
                    if c == '"':
                        if i < len(text) and text[i] == '"': field.append('"'); i += 1
                        else: break
                    else: field.append(c)
            else:
                while i < len(text) and text[i] not in ',\r\n':
                    if text[i] == '"': raise ValueError('quote')
                    field.append(text[i]); i += 1
            row.append(''.join(field))
            if i == len(text): break
            if text[i] == ',': i += 1; continue
            if text[i] == '\n': i += 1; break
            if text.startswith('\r\n',i): i += 2; break
            raise ValueError('delimiter')
        records.append(row)
    return records

def emit(row):
    def quote(s):
        return '"'+s.replace('"','""')+'"' if any(c in s for c in ',"\r\n') else s
    return ','.join(map(quote,row))+'\n'

def main():
    paths = []; key = 'id'; left = False
    a = iter(sys.argv[1:])
    for x in a:
        if x == '-l': left = True
        elif x == '-k':
            key = next(a,'')
            if not key: return 2
        elif x.startswith('-'): return 2
        else: paths.append(x)
    if len(paths) != 2: return 2
    try:
        tables = [parse(Path(p).read_bytes().decode('ascii')) for p in paths]
        for table in tables:
            if not table or len(set(table[0])) != len(table[0]) or key not in table[0]: return 1
            if any(len(row) != len(table[0]) for row in table): return 1
    except (OSError,ValueError,UnicodeError): return 1
    a,b = tables; ka,kb = a[0].index(key),b[0].index(key)
    columns = [i for i in range(len(b[0])) if i != kb]
    rows = [a[0]+[('r.'+b[0][i] if b[0][i] in a[0] else b[0][i]) for i in columns]]
    index = {}
    for row in b[1:]: index.setdefault(row[kb],[]).append(row)
    for row in a[1:]:
        found = index.get(row[ka],[])
        if found:
            rows.extend(row+[r[i] for i in columns] for r in found)
        elif left: rows.append(row+['']*len(columns))
    sys.stdout.write(''.join(map(emit,rows)))
    return 0

if __name__ == '__main__':
    status = main()
    if status: print('csvjoin: error',file=sys.stderr)
    sys.exit(status)
