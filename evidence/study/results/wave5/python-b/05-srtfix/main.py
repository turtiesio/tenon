import re
import sys

TIME = r'[0-9]{2}:[0-5][0-9]:[0-5][0-9],[0-9]{3}'


def milliseconds(value):
    hours, minutes, seconds, millis = map(int, re.split('[:,]', value))
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def timestamp(value):
    seconds, millis = divmod(value, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}'


def normalize(data, offset):
    lines = data.split('\n') if data else []
    if data.endswith('\n'):
        lines.pop()
    blocks = []
    block = []
    for line in lines:
        line = line.removesuffix('\r')
        if not line.strip(' \t'):
            if block:
                blocks.append(block)
                block = []
        else:
            block.append(line)
    if block:
        blocks.append(block)
    cues = []
    for block in blocks:
        if len(block) < 3 or not re.fullmatch(r'[0-9]{1,9}', block[0]):
            raise ValueError('invalid cue')
        match = re.fullmatch(f'({TIME}) --> ({TIME})', block[1])
        if not match:
            raise ValueError('invalid timing')
        start, end = map(milliseconds, match.groups())
        if end <= start:
            raise ValueError('nonpositive duration')
        start += offset
        end += offset
        if end > 0:
            cues.append((max(0, start), end, block[2:]))
    cues.sort(key=lambda cue: cue[0])
    output = []
    for index, (start, end, text) in enumerate(cues, 1):
        output.append('\n'.join([str(index), f'{timestamp(start)} --> {timestamp(end)}', *text]) + '\n\n')
    return ''.join(output)


if __name__ == '__main__':
    if len(sys.argv) != 2 or not re.fullmatch(r'[+-]?[0-9]{1,9}', sys.argv[1]):
        print('expected millisecond offset', file=sys.stderr)
        sys.exit(2)
    try:
        output = normalize(sys.stdin.buffer.read().decode('utf-8'), int(sys.argv[1]))
    except ValueError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
    sys.stdout.write(output)
