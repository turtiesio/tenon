import re
import sys

NUMBER_RE = re.compile(r"-?[0-9]{1,18}")
COUNT_RE = re.compile(r"[0-9]{1,9}")


def usage(message):
    print(f"seqx: {message}", file=sys.stderr)
    print("usage: seqx [-s SEP] [-w] [-n COUNT] FIRST [STEP] LAST", file=sys.stderr)
    sys.exit(2)


def parse_args(argv):
    sep = "\n"
    width = False
    count = None
    numbers = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-s", "-n"):
            if i + 1 >= len(argv):
                usage(f"option {arg} requires a value")
            value = argv[i + 1]
            if arg == "-s":
                sep = value
            else:
                if not COUNT_RE.fullmatch(value):
                    usage(f"invalid count: {value!r}")
                count = int(value)
            i += 2
            continue
        if arg == "-w":
            width = True
        elif NUMBER_RE.fullmatch(arg):
            numbers.append(int(arg))
        else:
            usage(f"invalid number: {arg!r}")
        i += 1

    if len(numbers) == 2:
        first, last = numbers
        step = 1
    elif len(numbers) == 3:
        first, step, last = numbers
    else:
        usage("expected FIRST [STEP] LAST")
    if step == 0:
        usage("STEP must not be zero")
    return sep, width, count, first, step, last


def sequence(first, step, last, count):
    value = first
    produced = 0
    while (value <= last if step > 0 else value >= last):
        if count is not None and produced >= count:
            return
        yield value
        produced += 1
        value += step


def pad(value, width):
    if value < 0:
        return "-" + str(-value).zfill(width - 1)
    return str(value).zfill(width)


def main():
    sep, width, count, first, step, last = parse_args(sys.argv[1:])
    values = list(sequence(first, step, last, count))
    if not values:
        return
    texts = [str(v) for v in values]
    if width:
        w = max(len(t) for t in texts)
        texts = [pad(v, w) for v in values]
    sys.stdout.write(sep.join(texts) + "\n")


if __name__ == "__main__":
    main()
