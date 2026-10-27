import os
from pathlib import Path
import re
import sys

NAME = r'[a-z][a-z0-9_]{0,31}'
INTEGER = r'-?[0-9]{1,15}'
RECORD = re.compile(f'([SA]) ({NAME}) ({INTEGER})|D ({NAME})')
COMMAND = re.compile(f'(SET|ADD) ({NAME}) ({INTEGER})|(GET|DEL) ({NAME})|LIST|INFO|COMPACT')

def main():
    if len(sys.argv) != 2:
        return 2
    directory = Path(sys.argv[1])
    log = directory / 'tally.log'
    temporary = directory / 'tally.log.tmp'
    state = {}
    records = 0
    try:
        if not directory.exists():
            directory.mkdir()
        if not directory.is_dir():
            return 1
        temporary.unlink(missing_ok=True)
        valid_bytes = 0
        if log.exists():
            with log.open('rb') as source:
                for line in source:
                    if not line.endswith(b'\n'):
                        break
                    try:
                        match = RECORD.fullmatch(line[:-1].decode('ascii'))
                    except UnicodeError:
                        break
                    if match is None:
                        break
                    action, name, value, deleted = match.groups()
                    if deleted is not None:
                        state.pop(deleted, None)
                    elif action == 'S':
                        state[name] = int(value)
                    else:
                        state[name] = state.get(name, 0) + int(value)
                    records += 1
                    valid_bytes += len(line)
            with log.open('r+b') as output:
                output.truncate(valid_bytes)
        output = log.open('ab', buffering=0)
    except OSError:
        return 1
    def append(record):
        nonlocal records
        output.write((record + '\n').encode('ascii'))
        records += 1
    try:
        for line in sys.stdin:
            line = line.removesuffix('\n').removesuffix('\r')
            match = COMMAND.fullmatch(line)
            if match is None:
                response = 'ERR bad command'
            else:
                command = line.split(' ', 1)[0]
                if command in ('SET', 'ADD'):
                    _, name, value = line.split(' ')
                    value = int(value)
                    append(f'{"S" if command == "SET" else "A"} {name} {value}')
                    state[name] = value if command == 'SET' else state.get(name, 0) + value
                    response = 'OK' if command == 'SET' else str(state[name])
                elif command in ('GET', 'DEL'):
                    name = line.split(' ')[1]
                    if name not in state:
                        response = 'NONE'
                    elif command == 'GET':
                        response = str(state[name])
                    else:
                        append(f'D {name}')
                        del state[name]
                        response = 'OK'
                elif command == 'LIST':
                    response = str(len(state)) + ''.join(f' {name}={value}' for name, value in sorted(state.items()))
                elif command == 'INFO':
                    response = f'counters={len(state)} log_records={records}'
                else:
                    with temporary.open('wb') as snapshot:
                        for name, value in sorted(state.items()):
                            snapshot.write(f'S {name} {value}\n'.encode('ascii'))
                    os.replace(temporary, log)
                    output.close()
                    output = log.open('ab', buffering=0)
                    records = len(state)
                    response = f'OK {records}'
            print(response, flush=True)
    finally:
        output.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())
