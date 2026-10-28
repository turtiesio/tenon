import sys
from pathlib import Path


def main():
    selected = set()
    files = []
    for arg in sys.argv[1:]:
        if arg in ('-l', '-w', '-m', '-c'):
            selected.add(arg)
        elif arg.startswith('-'):
            print(f'unknown option: {arg}', file=sys.stderr)
            return 2
        else:
            files.append(arg)
    selected = selected or {'-l', '-w', '-c'}
    order = [flag for flag in ('-l', '-w', '-m', '-c') if flag in selected]
    rows = []
    status = 0
    for name in files or [None]:
        try:
            data = Path(name).read_bytes() if name is not None else sys.stdin.buffer.read()
        except OSError as exc:
            print(f'{name}: {exc}', file=sys.stderr)
            status = 1
            continue
        counts = {'-l': data.count(b'\n'), '-w': len(data.split()), '-c': len(data)}
        if '-m' in selected:
            counts['-m'] = len(data.decode('utf-8'))
        rows.append(([counts[flag] for flag in order], name))
    if len(files) >= 2:
        rows.append(([sum(counts[i] for counts, _ in rows) for i in range(len(order))], 'total'))
    width = max((len(str(value)) for counts, _ in rows for value in counts), default=1)
    for counts, name in rows:
        print(' '.join(f'{value:{width}d}' for value in counts) + (f' {name}' if name is not None else ''))
    return status


if __name__ == '__main__':
    sys.exit(main())
