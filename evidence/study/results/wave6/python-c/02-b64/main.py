"""b64: strict Base64 encoder and decoder (RFC 4648 standard alphabet)."""
import base64
import re
import sys

ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
VALUE = {c: i for i, c in enumerate(ALPHABET)}
WIDTH_RE = re.compile(r"[0-9]{1,4}")
# Full groups, then optionally one padded final group.
CANONICAL_RE = re.compile(
    rb"(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?"
)


class UsageError(Exception):
    pass


def parse_args(argv: list[str]) -> tuple[bool, int]:
    decode = False
    width = 76
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-d":
            decode = True
        elif arg == "-w":
            if i + 1 >= len(argv):
                raise UsageError("-w needs a value")
            value = argv[i + 1]
            if not WIDTH_RE.fullmatch(value):
                raise UsageError(f"invalid width: {value}")
            width = int(value)
            i += 1
        else:
            raise UsageError(f"unexpected argument: {arg}")
        i += 1
    return decode, width


def encode(data: bytes, width: int) -> bytes:
    if not data:
        return b""
    text = base64.b64encode(data)
    if width == 0:
        return text + b"\n"
    return b"".join(text[i:i + width] + b"\n" for i in range(0, len(text), width))


def decode(data: bytes) -> bytes:
    """Decode canonical Base64; raise ValueError if the text is not canonical."""
    text = data.replace(b"\n", b"").replace(b"\r", b"")
    if not CANONICAL_RE.fullmatch(text):
        raise ValueError("invalid Base64 text")
    if text.endswith(b"=="):
        if VALUE[text[-3]] & 0x0F:
            raise ValueError("non-zero padding bits")
    elif text.endswith(b"="):
        if VALUE[text[-2]] & 0x03:
            raise ValueError("non-zero padding bits")
    return base64.b64decode(text, validate=True)


def main(argv: list[str]) -> int:
    try:
        decoding, width = parse_args(argv)
    except UsageError as e:
        print(f"b64: {e}", file=sys.stderr)
        print("usage: b64 [-d] [-w N]", file=sys.stderr)
        return 2
    data = sys.stdin.buffer.read()
    if decoding:
        try:
            out = decode(data)
        except ValueError as e:
            print(f"b64: {e}", file=sys.stderr)
            return 1
    else:
        out = encode(data, width)
    sys.stdout.buffer.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
