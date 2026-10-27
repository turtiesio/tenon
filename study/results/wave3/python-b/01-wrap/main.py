import re
import sys


def main():
    width, indent, justify = 72, 0, False
    args = iter(sys.argv[1:])
    seen = set()
    try:
        for arg in args:
            if arg not in ('-w', '-i', '-j') or arg in seen:
                raise ValueError('invalid option')
            seen.add(arg)
            if arg == '-j':
                justify = True
            else:
                value = next(args)
                if not re.fullmatch(r'[0-9]{1,4}', value):
                    raise ValueError('invalid number')
                if arg == '-w':
                    width = int(value)
                else:
                    indent = int(value)
        if not 1 <= width <= 1000 or not 0 <= indent < width:
            raise ValueError('invalid width or indent')
    except (ValueError, StopIteration):
        print('invalid arguments', file=sys.stderr)
        return 2
    paragraphs = []
    words = []
    for line in sys.stdin.buffer.read().split(b'\n'):
        line = line.removesuffix(b'\r')
        if any(c < 32 or c > 126 for c in line):
            print('invalid input', file=sys.stderr)
            return 1
        if line.strip(b' '):
            words.extend(line.decode('ascii').split())
        elif words:
            paragraphs.append(words)
            words = []
    if words:
        paragraphs.append(words)
    output = []
    for words in paragraphs:
        lines = []
        current = []
        pad = indent
        length = pad
        for word in words:
            if current and length + 1 + len(word) > width:
                lines.append((pad, current))
                current, pad, length = [], 0, 0
            length += len(word) + bool(current)
            current.append(word)
        lines.append((pad, current))
        rendered = []
        for i, (pad, line) in enumerate(lines):
            if justify and i < len(lines) - 1 and len(line) > 1:
                base, extra = divmod(width - pad - sum(map(len, line)), len(line) - 1)
                text = line[0] + ''.join(' ' * (base + (j < extra)) + word for j, word in enumerate(line[1:]))
            else:
                text = ' '.join(line)
            rendered.append(' ' * pad + text)
        output.append('\n'.join(rendered))
    if output:
        sys.stdout.write('\n\n'.join(output) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
