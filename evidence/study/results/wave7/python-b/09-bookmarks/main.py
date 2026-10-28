from pathlib import Path
import re
import sys

NAME = r'[a-z0-9-]{1,20}'
URL = r'[\x21-\x7e]{1,200}'
TAG = r'[a-z0-9]{1,12}'
PATTERNS = {
    'ADD': re.compile(f'ADD ({NAME}) ({URL})'),
    'DEL': re.compile(f'DEL ({NAME})'),
    'TAG': re.compile(f'TAG ({NAME}) ({TAG})'),
    'UNTAG': re.compile(f'UNTAG ({NAME}) ({TAG})'),
    'GET': re.compile(f'GET ({NAME})'),
    'FIND': re.compile(f'FIND ({TAG})'),
    'COMPACT': re.compile('COMPACT'),
}
MUTATIONS = {'ADD', 'DEL', 'TAG', 'UNTAG'}


def parse(line):
    action = line.split(' ', 1)[0]
    pattern = PATTERNS.get(action)
    match = pattern.fullmatch(line) if pattern else None
    return (action, match.groups()) if match else None


def format_bookmark(name, bookmark):
    url, tags = bookmark
    return f'{name} {url} {",".join(sorted(tags)) or "-"}'


def apply(state, parsed):
    action, args = parsed
    name = args[0]
    if action == 'ADD':
        if name in state:
            return 'ERR exists'
        state[name] = (args[1], set())
        return 'OK'
    if action == 'FIND':
        return ' '.join(sorted(name for name, (_, tags) in state.items() if args[0] in tags)) or '-'
    if name not in state:
        return 'ERR no such bookmark'
    if action == 'GET':
        return format_bookmark(name, state[name])
    if action == 'DEL':
        del state[name]
        return 'OK'
    tags = state[name][1]
    tag = args[1]
    if action == 'TAG':
        if tag in tags:
            return 'UNCHANGED'
        tags.add(tag)
    else:
        if tag not in tags:
            return 'UNCHANGED'
        tags.remove(tag)
    return 'OK'


def load(directory):
    state, sequence = {}, 0
    snapshot = directory / 'snapshot'
    if snapshot.exists():
        data = snapshot.read_bytes()
        if not data.endswith(b'\n'):
            raise ValueError('snapshot lacks final newline')
        # Split only on LF; other control characters must fail validation.
        lines = data.decode('ascii').split('\n')[:-1]
        header = re.fullmatch(r'bookmarks (0|[1-9][0-9]*)', lines[0])
        if not header:
            raise ValueError('invalid snapshot header')
        sequence = int(header[1])
        previous = ''
        for line in lines[1:]:
            match = re.fullmatch(f'({NAME}) ({URL}) (-|{TAG}(?:,{TAG})*)', line)
            if not match:
                raise ValueError('invalid snapshot entry')
            name, url, raw_tags = match.groups()
            tags = [] if raw_tags == '-' else raw_tags.split(',')
            if name <= previous or any(a >= b for a, b in zip(tags, tags[1:])):
                raise ValueError('unsorted snapshot')
            state[name] = (url, set(tags))
            previous = name
    journal = directory / 'journal'
    data = journal.read_bytes() if journal.exists() else b''
    complete_length = data.rfind(b'\n') + 1
    complete = data[:complete_length].decode('ascii')
    records = []
    previous = None
    for line in complete.split('\n')[:-1]:
        match = re.fullmatch(r'([1-9][0-9]*) (.+)', line)
        if not match:
            raise ValueError('invalid journal record')
        number, command = int(match[1]), parse(match[2])
        if command is None or command[0] not in MUTATIONS:
            raise ValueError('invalid journal command')
        if previous is not None and number != previous+1:
            raise ValueError('journal gap')
        records.append((number, command))
        previous = number
    if records and (records[0][0] > sequence+1 or records[-1][0] < sequence):
        raise ValueError('journal does not continue snapshot')
    for number, command in records:
        if number > sequence and apply(state, command) != 'OK':
            raise ValueError('journal operation failed')
    last = max(sequence, records[-1][0]) if records else sequence
    # Validate everything before modifying a torn journal.
    if complete_length != len(data):
        with journal.open('r+b') as stream:
            stream.truncate(complete_length)
    return state, last


def compact(directory, state, sequence):
    with (directory / 'snapshot.tmp').open('w', encoding='ascii', newline='\n') as stream:
        stream.write(f'bookmarks {sequence}\n')
        for name in sorted(state):
            stream.write(format_bookmark(name, state[name]) + '\n')
        stream.flush()
    (directory / 'snapshot.tmp').replace(directory / 'snapshot')
    with (directory / 'journal').open('wb'):
        pass


def main():
    if len(sys.argv) != 2:
        print('expected directory', file=sys.stderr)
        return 2
    try:
        directory = Path(sys.argv[1])
        if not directory.exists():
            directory.mkdir()
        if not directory.is_dir():
            raise ValueError('not a directory')
        state, sequence = load(directory)
        # Verify that the journal can be opened before accepting commands.
        with (directory / 'journal').open('ab'):
            pass
        for raw in sys.stdin.buffer:
            line = raw.removesuffix(b'\n').removesuffix(b'\r').decode('ascii')
            parsed = parse(line)
            if parsed is None:
                response = 'ERR bad command'
            elif parsed[0] == 'COMPACT':
                compact(directory, state, sequence)
                response = f'OK {sequence}'
            else:
                response = apply(state, parsed)
                if parsed[0] in MUTATIONS and response == 'OK':
                    with (directory / 'journal').open('ab') as stream:
                        stream.write(f'{sequence+1} {line}\n'.encode('ascii'))
                        stream.flush()
                    sequence += 1
            print(response, flush=True)
        return 0
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
