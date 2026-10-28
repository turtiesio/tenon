import re
import sys
from itertools import islice

NUMBER = re.compile(r"-?[0-9]{1,18}")
COUNT = re.compile(r"[0-9]{1,9}")


class UsageError(Exception):
    pass


def parse(args):
    sep = "\n"
    width = False
    limit = None
    numbers = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-s":
            if i + 1 >= len(args):
                raise UsageError("-s needs a value")
            sep = args[i + 1]
            i += 2
        elif arg == "-n":
            if i + 1 >= len(args):
                raise UsageError("-n needs a value")
            if not COUNT.fullmatch(args[i + 1]):
                raise UsageError("bad -n value: " + args[i + 1])
            limit = int(args[i + 1])
            i += 2
        elif arg == "-w":
            width = True
            i += 1
        else:
            if not NUMBER.fullmatch(arg):
                raise UsageError("malformed number: " + arg)
            numbers.append(int(arg))
            i += 1
    if len(numbers) == 2:
        first, last = numbers
        step = 1
    elif len(numbers) == 3:
        first, step, last = numbers
    else:
        raise UsageError("expected 2 or 3 numbers")
    if step == 0:
        raise UsageError("step must not be zero")
    return sep, width, limit, first, step, last


def sequence(first, step, last):
    if step > 0:
        return range(first, last + 1, step)
    return range(first, last - 1, step)


def pad(text, w):
    if text.startswith("-"):
        return "-" + text[1:].zfill(w - 1)
    return text.zfill(w)


def main():
    try:
        sep, width, limit, first, step, last = parse(sys.argv[1:])
    except UsageError as e:
        print("seqx: " + str(e), file=sys.stderr)
        return 2
    values = sequence(first, step, last)
    if limit is not None:
        values = islice(values, limit)
    texts = [str(v) for v in values]
    if width and texts:
        w = max(len(t) for t in texts)
        texts = [pad(t, w) for t in texts]
    if texts:
        sys.stdout.write(sep.join(texts) + "\n")
    return 0


sys.exit(main())
