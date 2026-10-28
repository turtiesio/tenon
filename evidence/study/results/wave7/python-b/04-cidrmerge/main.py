import ipaddress
import re
import sys


def main():
    if sys.argv[1:] not in ([], ['-r']):
        print('invalid usage', file=sys.stderr)
        return 2
    ranges = []
    failed = False
    lines = sys.stdin.buffer.read().decode('ascii').split('\n')
    for index, line in enumerate(lines, 1):
        line = line.removesuffix('\r')
        if not line or line.startswith('#'):
            continue
        try:
            if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(/(0|[1-9][0-9]*))?', line):
                raise ValueError('invalid syntax')
            network = ipaddress.IPv4Network(line, strict=True)
            ranges.append((int(network.network_address), int(network.broadcast_address)))
        except ValueError:
            print(f'bad line {index}', file=sys.stderr)
            failed = True
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    for start, end in merged:
        first, last = ipaddress.IPv4Address(start), ipaddress.IPv4Address(end)
        if sys.argv[1:]:
            print(f'{first}-{last} {end-start+1}')
        else:
            for network in ipaddress.summarize_address_range(first, last):
                print(network)
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
