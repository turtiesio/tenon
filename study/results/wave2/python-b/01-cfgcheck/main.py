import re
import sys

NAME = r'[a-z][a-z0-9_]*'
INTEGER = r'-?[0-9]{1,18}'

def lines(path):
    with open(path, encoding='ascii', newline='') as f:
        text = f.read()
    parts = text.split('\n')
    if parts[-1] == '':
        parts.pop()
    return [line[:-1] if line.endswith('\r') else line for line in parts]

def main():
    args = sys.argv[1:]
    if any(a.startswith('-') and a not in ('--strict', '-q') for a in args):
        return 2
    paths = [a for a in args if not a.startswith('-')]
    if len(paths) != 2:
        return 2
    try:
        source = lines(paths[0])
    except (OSError, UnicodeError):
        return 2
    schema = {}
    for line in source:
        line = line.strip(' \t')
        if not line or line.startswith('#'):
            continue
        tokens = re.split(r'[ \t]+', line)
        if len(tokens) not in (3, 4):
            return 3
        key, kind, presence = tokens[:3]
        arg = tokens[3] if len(tokens) == 4 else None
        if not re.fullmatch(NAME + r'\.' + NAME, key) or key in schema or presence not in ('required', 'optional'):
            return 3
        if kind == 'int':
            if arg is not None:
                match = re.fullmatch('(' + INTEGER + r')\.\.(' + INTEGER + ')', arg)
                if not match or int(match[1]) > int(match[2]):
                    return 3
        elif kind == 'string':
            if arg is not None and not re.fullmatch(r'maxlen=[0-9]{1,7}', arg):
                return 3
        elif kind == 'bool':
            if arg is not None:
                return 3
        elif kind == 'enum':
            if arg is None or any(not value for value in arg.split(',')):
                return 3
        else:
            return 3
        schema[key] = (kind, presence, arg)
    try:
        config = lines(paths[1])
    except (OSError, UnicodeError):
        return 2
    errors, seen = [], set()
    section = None
    for number, line in enumerate(config, 1):
        stripped = line.strip(' \t')
        if not stripped or stripped.startswith(('#', ';')):
            continue
        header = re.fullmatch(r'\[(' + NAME + r')\]', stripped)
        if header:
            section = header[1]
            continue
        if '=' not in line or not re.fullmatch(NAME, line.split('=', 1)[0].strip(' \t')):
            errors.append(f'{number}: syntax error')
            continue
        key, value = (part.strip(' \t') for part in line.split('=', 1))
        if section is None:
            errors.append(f'{number}: key outside section')
            continue
        key = section + '.' + key
        if key in seen:
            errors.append(f'{number}: duplicate key {key}')
            continue
        seen.add(key)
        if key not in schema:
            if '--strict' in args:
                errors.append(f'{number}: unknown key {key}')
            continue
        kind, _, arg = schema[key]
        problem = None
        if kind == 'int':
            if not re.fullmatch(INTEGER, value):
                problem = 'not an integer'
            elif arg:
                low, high = map(int, arg.split('..'))
                if not low <= int(value) <= high:
                    problem = f'out of range {arg}'
        elif kind == 'bool' and value not in ('true', 'false'):
            problem = 'not a boolean'
        elif kind == 'string' and arg and len(value) > int(arg[7:]):
            problem = f'longer than {arg[7:]}'
        elif kind == 'enum' and value not in arg.split(','):
            problem = f'not one of {arg}'
        if problem:
            errors.append(f'{number}: {key}: {problem}')
    errors.extend(f'missing: {key}' for key, entry in schema.items() if entry[1] == 'required' and key not in seen)
    if '-q' not in args:
        print('\n'.join(errors + ([f'errors: {len(errors)}'] if errors else ['OK'])))
    return int(bool(errors))

if __name__ == '__main__':
    sys.exit(main())
