"""Private specification reference: numbered-prefix replay and unbuffered append."""
import os
import re
import sys
URL = r'[!-~]{1,200}'
CODE = r'[0-9a-z]{1,8}'

def base36(n):
    out = ''
    while n:
        n, digit = divmod(n,36)
        out = '0123456789abcdefghijklmnopqrstuvwxyz'[digit]+out
    return out or '0'

def main():
    if len(sys.argv) != 2:
        print('usage error', file=sys.stderr); return 2
    directory = sys.argv[1]
    try:
        if not os.path.exists(directory): os.mkdir(directory)
        if not os.path.isdir(directory): raise OSError('not directory')
        path = os.path.join(directory, 'journal')
        try:
            with open(path, 'rb') as f: journal = f.read()
        except FileNotFoundError: journal = b''
        links, next_id, records, prefix_len = {}, 1, 0, 0
        for raw in journal.splitlines(keepends=True):
            # Only LF terminates records. Other control bytes cannot be in a valid record.
            if not raw.endswith(b'\n'): break
            line = raw[:-1].decode('latin1')
            m = re.fullmatch(r'([1-9][0-9]{0,8}) (P|H|D) (.+)', line)
            if not m or int(m[1]) != records+1: break
            op, value = m[2], m[3]
            if op == 'P':
                if not re.fullmatch(URL, value): break
                links[base36(next_id)] = [value, 0]; next_id += 1
            else:
                if not re.fullmatch(CODE, value) or value not in links: break
                if op == 'H': links[value][1] += 1
                else: del links[value]
            records += 1; prefix_len += len(raw)
        # Discard the invalid tail before any write. Read-only startup may truncate too.
        with open(path, 'ab') as f: f.truncate(prefix_len)
        with open(path, 'ab', buffering=0) as f:
            def append(op, value):
                nonlocal records
                payload = f'{records+1} {op} {value}\n'.encode('ascii')
                while payload:
                    written = f.write(payload)
                    if not written: raise OSError('short write')
                    payload = payload[written:]
                records += 1
            for raw in sys.stdin.buffer:
                line = raw.removesuffix(b'\n').removesuffix(b'\r').decode('latin1')
                if line == 'INFO': response = f'links={len(links)} next={base36(next_id)} records={records}'
                elif re.fullmatch(r'PUT '+URL, line):
                    value = line[4:]; code = base36(next_id)
                    append('P', value); links[code] = [value,0]; next_id += 1
                    response = 'CODE '+code
                else:
                    m = re.fullmatch(r'(GET|HITS|DEL) ('+CODE+r')', line)
                    if not m: response = 'ERR bad command'
                    elif m[2] not in links: response = 'ERR not found'
                    elif m[1] == 'HITS': response = 'HITS '+str(links[m[2]][1])
                    elif m[1] == 'GET':
                        append('H', m[2]); links[m[2]][1] += 1; response = 'URL '+links[m[2]][0]
                    else:
                        append('D', m[2]); del links[m[2]]; response = 'OK'
                print(response, flush=True)
        return 0
    except OSError as exc:
        print(str(exc), file=sys.stderr); return 1
if __name__ == '__main__': sys.exit(main())
