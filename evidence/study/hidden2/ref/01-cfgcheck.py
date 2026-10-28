"""Private, spec-only cfgcheck oracle."""
import re
import sys
from pathlib import Path

def match(p, s):
    return re.fullmatch(p, s) is not None

def lines(data):
    a = data.split('\n')
    if a[-1] == '':
        a.pop()
    return [s[:-1] if s.endswith('\r') else s for s in a]

def main(args):
    if any(a.startswith('-') and a not in ('--strict', '-q') for a in args):
        return 2
    paths = [a for a in args if not a.startswith('-')]
    if len(paths) != 2:
        return 2
    try:
        schema_data = Path(paths[0]).read_bytes().decode('ascii')
    except OSError:
        return 2
    schema = {}
    for line in lines(schema_data):
        s = line.strip(' \t')
        if not s or s.startswith('#'):
            continue
        tok = re.split('[ \t]+', s)
        if len(tok) not in (3, 4):
            return 3
        key, typ, presence = tok[:3]
        arg = tok[3] if len(tok) == 4 else None
        if not match(r'[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*', key) or key in schema:
            return 3
        if presence not in ('required', 'optional'):
            return 3
        if typ == 'int':
            if arg is not None:
                if not match(r'-?[0-9]{1,18}\.\.-?[0-9]{1,18}', arg):
                    return 3
                lo, hi = arg.split('..')
                if int(lo) > int(hi):
                    return 3
        elif typ == 'string':
            if arg is not None and not match(r'maxlen=[0-9]{1,7}', arg):
                return 3
        elif typ == 'bool':
            if arg is not None:
                return 3
        elif typ == 'enum':
            if arg is None or any(v == '' for v in arg.split(',')):
                return 3
        else:
            return 3
        schema[key] = (typ, presence, arg)
    try:
        config = Path(paths[1]).read_bytes().decode('ascii')
    except OSError:
        return 2
    section, seen, errors = None, set(), []
    for num, line in enumerate(lines(config), 1):
        s = line.strip(' \t')
        if not s or s[0] in '#;':
            continue
        if match(r'\[[a-z][a-z0-9_]*\]', s):
            section = s[1:-1]
            continue
        if '=' not in line or not match(r'[a-z][a-z0-9_]*', line.split('=', 1)[0].strip(' \t')):
            errors.append(f'{num}: syntax error')
            continue
        key, value = (x.strip(' \t') for x in line.split('=', 1))
        if section is None:
            errors.append(f'{num}: key outside section')
            continue
        full = section + '.' + key
        if full in seen:
            errors.append(f'{num}: duplicate key {full}')
            continue
        seen.add(full)
        if full not in schema:
            if '--strict' in args:
                errors.append(f'{num}: unknown key {full}')
            continue
        typ, _, arg = schema[full]
        problem = None
        if typ == 'int':
            if not match(r'-?[0-9]{1,18}', value):
                problem = 'not an integer'
            elif arg is not None and not int(arg.split('..')[0]) <= int(value) <= int(arg.split('..')[1]):
                problem = 'out of range ' + arg
        elif typ == 'bool' and value not in ('true', 'false'):
            problem = 'not a boolean'
        elif typ == 'string' and arg is not None and len(value) > int(arg[7:]):
            problem = 'longer than ' + arg[7:]
        elif typ == 'enum' and value not in arg.split(','):
            problem = 'not one of ' + arg
        if problem:
            errors.append(f'{num}: {full}: {problem}')
    errors += ['missing: ' + k for k, (_, p, _) in schema.items() if p == 'required' and k not in seen]
    if '-q' not in args:
        print('\n'.join(errors + ([f'errors: {len(errors)}'] if errors else ['OK'])))
    return int(bool(errors))

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
