"""cfgcheck: validate an INI-style config file against a schema."""
import re
import sys

NAME_RE = re.compile(r"[a-z][a-z0-9_]*")
INT_RE = re.compile(r"-?[0-9]{1,18}")
RANGE_RE = re.compile(r"(-?[0-9]{1,18})\.\.(-?[0-9]{1,18})")
MAXLEN_RE = re.compile(r"maxlen=([0-9]{1,7})")
WS = " \t"


class SchemaError(Exception):
    pass


class Entry:
    def __init__(self, name, type_, required, arg):
        self.name = name
        self.type = type_
        self.required = required
        self.arg = arg  # raw ARG text, or None
        self.range = None
        self.maxlen = None
        self.choices = None


def read_lines(path):
    with open(path, "rb") as f:
        text = f.read().decode("latin-1")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def is_ignored(line, comment_chars):
    stripped = line.lstrip(WS)
    return stripped == "" or stripped[0] in comment_chars


def parse_entry(line):
    tokens = re.split(r"[ \t]+", line.strip(WS))
    if len(tokens) not in (3, 4):
        raise SchemaError("wrong number of tokens")
    name, type_, presence = tokens[:3]
    arg = tokens[3] if len(tokens) == 4 else None

    section, dot, key = name.partition(".")
    if not dot or not NAME_RE.fullmatch(section) or not NAME_RE.fullmatch(key):
        raise SchemaError("bad name")
    if presence not in ("required", "optional"):
        raise SchemaError("bad presence")

    entry = Entry(name, type_, presence == "required", arg)
    if type_ == "int":
        if arg is not None:
            m = RANGE_RE.fullmatch(arg)
            if not m:
                raise SchemaError("bad int range")
            lo, hi = int(m.group(1)), int(m.group(2))
            if lo > hi:
                raise SchemaError("empty int range")
            entry.range = (lo, hi)
    elif type_ == "string":
        if arg is not None:
            m = MAXLEN_RE.fullmatch(arg)
            if not m:
                raise SchemaError("bad maxlen")
            entry.maxlen = int(m.group(1))
    elif type_ == "bool":
        if arg is not None:
            raise SchemaError("bool takes no arg")
    elif type_ == "enum":
        if arg is None:
            raise SchemaError("enum needs values")
        choices = arg.split(",")
        if any(c == "" for c in choices):
            raise SchemaError("empty enum value")
        entry.choices = set(choices)
    else:
        raise SchemaError("unknown type")
    return entry


def parse_schema(lines):
    entries = {}
    for line in lines:
        if is_ignored(line, "#"):
            continue
        entry = parse_entry(line)
        if entry.name in entries:
            raise SchemaError("duplicate entry")
        entries[entry.name] = entry
    return entries


def check_value(entry, value):
    """Return a diagnostic message for VALUE, or None if it is valid."""
    if entry.type == "int":
        if not INT_RE.fullmatch(value):
            return f"{entry.name}: not an integer"
        if entry.range is not None:
            lo, hi = entry.range
            if not lo <= int(value) <= hi:
                return f"{entry.name}: out of range {entry.arg}"
    elif entry.type == "bool":
        if value not in ("true", "false"):
            return f"{entry.name}: not a boolean"
    elif entry.type == "string":
        if entry.maxlen is not None and len(value) > entry.maxlen:
            return f"{entry.name}: longer than {entry.arg[len('maxlen='):]}"
    elif entry.type == "enum":
        if value not in entry.choices:
            return f"{entry.name}: not one of {entry.arg}"
    return None


def check_config(lines, schema, strict):
    diagnostics = []
    seen = set()
    section = None
    for lineno, line in enumerate(lines, 1):
        if is_ignored(line, "#;"):
            continue
        stripped = line.strip(WS)
        if (len(stripped) >= 2 and stripped[0] == "[" and stripped[-1] == "]"
                and NAME_RE.fullmatch(stripped[1:-1])):
            section = stripped[1:-1]
            continue
        key, eq, value = line.partition("=")
        key = key.strip(WS)
        value = value.strip(WS)
        if not eq or not NAME_RE.fullmatch(key):
            diagnostics.append(f"{lineno}: syntax error")
            continue
        if section is None:
            diagnostics.append(f"{lineno}: key outside section")
            continue
        name = f"{section}.{key}"
        if name in seen:
            diagnostics.append(f"{lineno}: duplicate key {name}")
            continue
        seen.add(name)
        entry = schema.get(name)
        if entry is None:
            if strict:
                diagnostics.append(f"{lineno}: unknown key {name}")
            continue
        message = check_value(entry, value)
        if message is not None:
            diagnostics.append(f"{lineno}: {message}")

    for entry in schema.values():
        if entry.required and entry.name not in seen:
            diagnostics.append(f"missing: {entry.name}")
    return diagnostics


def main(argv):
    strict = quiet = False
    paths = []
    for arg in argv:
        if arg.startswith("-"):
            if arg == "--strict":
                strict = True
            elif arg == "-q":
                quiet = True
            else:
                print(f"cfgcheck: unknown option {arg}", file=sys.stderr)
                return 2
        else:
            paths.append(arg)
    if len(paths) != 2:
        print("usage: cfgcheck [--strict] [-q] SCHEMA CONFIG", file=sys.stderr)
        return 2
    schema_path, config_path = paths

    try:
        schema_lines = read_lines(schema_path)
    except OSError as e:
        print(f"cfgcheck: {e}", file=sys.stderr)
        return 2
    try:
        schema = parse_schema(schema_lines)
    except SchemaError as e:
        print(f"cfgcheck: invalid schema: {e}", file=sys.stderr)
        return 3
    try:
        config_lines = read_lines(config_path)
    except OSError as e:
        print(f"cfgcheck: {e}", file=sys.stderr)
        return 2

    diagnostics = check_config(config_lines, schema, strict)
    if not quiet:
        out = diagnostics + [f"errors: {len(diagnostics)}" if diagnostics else "OK"]
        sys.stdout.write("".join(line + "\n" for line in out))
    return 1 if diagnostics else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
