"""Private WAL oracle. Uses unbuffered append before each acknowledgment."""
import os
from pathlib import Path
import re
import sys
NAME = rb'[a-z][a-z0-9_]{0,31}'
INT = rb'-?[0-9]{1,15}'
RECORD = re.compile(rb'(?:[SA] '+NAME+rb' '+INT+rb'|D '+NAME+rb')\n')

def main(args):
    if len(args) != 1:
        return 2
    directory = Path(args[0])
    try:
        if not directory.exists():
            directory.mkdir()
        if not directory.is_dir():
            return 1
        log = directory / 'tally.log'; tmp = directory / 'tally.log.tmp'
        if tmp.exists():
            tmp.unlink()
        data = log.read_bytes() if log.exists() else b''
    except OSError:
        return 1
    counters = {}; records = 0; end = 0
    for raw in data.splitlines(keepends=True):
        if not RECORD.fullmatch(raw):
            break
        v = raw[:-1].decode('ascii').split(' ')
        if v[0] == 'D':
            counters.pop(v[1], None)
        else:
            counters[v[1]] = int(v[2]) + (counters.get(v[1],0) if v[0] == 'A' else 0)
        end += len(raw); records += 1
    if end != len(data):
        log.write_bytes(data[:end])
    forms = [rb'(?:SET|ADD) '+NAME+rb' '+INT, rb'(?:GET|DEL) '+NAME, rb'(?:LIST|INFO|COMPACT)']
    for raw in sys.stdin.buffer:
        line = raw.removesuffix(b'\n').removesuffix(b'\r')
        if not any(re.fullmatch(f,line) for f in forms):
            print('ERR bad command', flush=True); continue
        v = line.decode('ascii').split(' '); cmd = v[0]; record = None
        if cmd == 'SET':
            counters[v[1]] = int(v[2]); response = 'OK'; record = f'S {v[1]} {v[2]}\n'
        elif cmd == 'ADD':
            counters[v[1]] = counters.get(v[1],0)+int(v[2]); response = str(counters[v[1]]); record = f'A {v[1]} {v[2]}\n'
        elif cmd == 'DEL':
            if v[1] in counters:
                del counters[v[1]]; response = 'OK'; record = f'D {v[1]}\n'
            else:
                response = 'NONE'
        elif cmd == 'GET':
            response = str(counters[v[1]]) if v[1] in counters else 'NONE'
        elif cmd == 'LIST':
            response = str(len(counters)) + ''.join(f' {k}={value}' for k,value in sorted(counters.items()))
        elif cmd == 'INFO':
            response = f'counters={len(counters)} log_records={records}'
        else:
            with tmp.open('wb') as f:
                for k,value in sorted(counters.items()):
                    f.write(f'S {k} {value}\n'.encode())
            os.replace(tmp, log); records = len(counters); response = f'OK {records}'
        if record is not None:
            with log.open('ab', buffering=0) as f:
                f.write(record.encode('ascii'))
            records += 1
        print(response, flush=True)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
