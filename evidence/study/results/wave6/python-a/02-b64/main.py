import re
import sys

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
VALUES = {ch: i for i, ch in enumerate(ALPHABET)}
MAX_INPUT = 1_000_000


class UsageError(Exception):
    pass


class DecodeError(Exception):
    pass


def parse_args(argv):
    decode = False
    width = 76
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-d":
            decode = True
        elif arg == "-w":
            i += 1
            if i >= len(argv):
                raise UsageError("-w needs a value")
            if not re.fullmatch(r"[0-9]{1,4}", argv[i]):
                raise UsageError(f"bad width: {argv[i]}")
            width = int(argv[i])
        else:
            raise UsageError(f"unexpected argument: {arg}")
        i += 1
    return decode, width


def encode(data, width):
    if not data:
        return b""
    out = []
    for i in range(0, len(data), 3):
        chunk = data[i:i + 3]
        n = int.from_bytes(chunk, "big") << (8 * (3 - len(chunk)))
        chars = [ALPHABET[(n >> shift) & 63] for shift in (18, 12, 6, 0)]
        keep = len(chunk) + 1
        out.append("".join(chars[:keep]) + "=" * (4 - keep))
    text = "".join(out)
    if width == 0:
        lines = [text]
    else:
        lines = [text[i:i + width] for i in range(0, len(text), width)]
    return "".join(line + "\n" for line in lines).encode("ascii")


def decode(data):
    text = data.replace(b"\n", b"").replace(b"\r", b"")
    if len(text) % 4 != 0:
        raise DecodeError("length is not a multiple of 4")
    try:
        s = text.decode("ascii")
    except UnicodeDecodeError:
        raise DecodeError("non-ASCII character")
    stripped = s.rstrip("=")
    pad = len(s) - len(stripped)
    if pad > 2:
        raise DecodeError("too much padding")
    if any(ch not in VALUES for ch in stripped):
        raise DecodeError("invalid character")
    vals = [VALUES[ch] for ch in stripped]
    if pad == 2 and vals[-1] & 0x0F:
        raise DecodeError("non-zero unused bits")
    if pad == 1 and vals[-1] & 0x03:
        raise DecodeError("non-zero unused bits")
    out = bytearray()
    for i in range(0, len(vals), 4):
        group = vals[i:i + 4]
        n = 0
        for v in group:
            n = (n << 6) | v
        n <<= 6 * (4 - len(group))
        out += n.to_bytes(3, "big")[:len(group) - 1]
    return bytes(out)


def main(argv):
    try:
        decoding, width = parse_args(argv)
    except UsageError as e:
        print(f"b64: {e}", file=sys.stderr)
        return 2
    data = sys.stdin.buffer.read(MAX_INPUT)
    if decoding:
        try:
            result = decode(data)
        except DecodeError as e:
            print(f"b64: invalid input: {e}", file=sys.stderr)
            return 1
    else:
        result = encode(data, width)
    sys.stdout.buffer.write(result)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
