#!/usr/bin/env python3
"""cfgcheck: validate an INI-style config file against a small schema."""

import re
import sys
from dataclasses import dataclass

IDENT = re.compile(r"[a-z][a-z0-9_]*")
SECTION_KEY = re.compile(r"([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*)")
INT_VALUE = re.compile(r"-?[0-9]{1,18}")
INT_RANGE = re.compile(r"(-?[0-9]{1,18})\.\.(-?[0-9]{1,18})")
MAXLEN = re.compile(r"maxlen=([0-9]{1,7})")
SEPARATORS = re.compile(r"[ \t]+")

EXIT_OK, EXIT_ERRORS, EXIT_USAGE, EXIT_BAD_SCHEMA = 0, 1, 2, 3


@dataclass
class Entry:
    name: str  # SECTION.KEY
    type: str
    required: bool
    arg: str | None = None
    lo: int = 0
    hi: int = 0
    max_len: int = 0
    choices: tuple[str, ...] = ()


class SchemaError(Exception):
    pass


def read_lines(path):
    with open(path, "rb") as f:
        text = f.read().decode("latin-1")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def is_ignorable(line, comment_chars):
    stripped = line.strip(" \t")
    return stripped == "" or stripped[0] in comment_chars


def parse_entry(line):
    tokens = SEPARATORS.split(line.strip(" \t"))
    if len(tokens) not in (3, 4):
        raise SchemaError(f"wrong number of tokens: {line!r}")
    name, type_, presence = tokens[:3]
    arg = tokens[3] if len(tokens) == 4 else None

    if not SECTION_KEY.fullmatch(name):
        raise SchemaError(f"malformed SECTION.KEY: {name!r}")
    if presence not in ("required", "optional"):
        raise SchemaError(f"unknown presence: {presence!r}")
    entry = Entry(name, type_, presence == "required", arg)

    if type_ == "int":
        if arg is not None:
            m = INT_RANGE.fullmatch(arg)
            if not m:
                raise SchemaError(f"malformed int range: {arg!r}")
            entry.lo, entry.hi = int(m[1]), int(m[2])
            if entry.lo > entry.hi:
                raise SchemaError(f"empty int range: {arg!r}")
    elif type_ == "string":
        if arg is not None:
            m = MAXLEN.fullmatch(arg)
            if not m:
                raise SchemaError(f"malformed string argument: {arg!r}")
            entry.max_len = int(m[1])
    elif type_ == "bool":
        if arg is not None:
            raise SchemaError("bool takes no argument")
    elif type_ == "enum":
        if arg is None:
            raise SchemaError("enum requires values")
        values = arg.split(",")
        if any(v == "" for v in values):
            raise SchemaError(f"malformed enum values: {arg!r}")
        entry.choices = tuple(values)
    else:
        raise SchemaError(f"unknown type: {type_!r}")
    return entry


def parse_schema(lines):
    entries = {}  # insertion-ordered
    for line in lines:
        if is_ignorable(line, "#"):
            continue
        entry = parse_entry(line)
        if entry.name in entries:
            raise SchemaError(f"duplicate entry: {entry.name}")
        entries[entry.name] = entry
    return entries


def check_value(entry, value):
    """Return a diagnostic message for a bad value, or None if it is valid."""
    name = entry.name
    if entry.type == "int":
        if not INT_VALUE.fullmatch(value):
            return f"{name}: not an integer"
        if entry.arg is not None and not entry.lo <= int(value) <= entry.hi:
            return f"{name}: out of range {entry.arg}"
    elif entry.type == "bool":
        if value not in ("true", "false"):
            return f"{name}: not a boolean"
    elif entry.type == "string":
        if entry.arg is not None and len(value) > entry.max_len:
            return f"{name}: longer than {entry.max_len}"
    elif entry.type == "enum":
        if value not in entry.choices:
            return f"{name}: not one of {entry.arg}"
    return None


def check_config(lines, schema, strict):
    """Return the list of diagnostics, line diagnostics first."""
    diagnostics = []
    seen = set()
    section = None

    for number, line in enumerate(lines, start=1):
        if is_ignorable(line, "#;"):
            continue
        stripped = line.strip(" \t")

        if stripped.startswith("[") and stripped.endswith("]") and IDENT.fullmatch(stripped[1:-1]):
            section = stripped[1:-1]
            continue

        if "=" not in line:
            diagnostics.append(f"{number}: syntax error")
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(" \t"), value.strip(" \t")
        if not IDENT.fullmatch(key):
            diagnostics.append(f"{number}: syntax error")
            continue
        if section is None:
            diagnostics.append(f"{number}: key outside section")
            continue

        name = f"{section}.{key}"
        if name in seen:
            diagnostics.append(f"{number}: duplicate key {name}")
            continue
        seen.add(name)

        entry = schema.get(name)
        if entry is None:
            if strict:
                diagnostics.append(f"{number}: unknown key {name}")
            continue
        problem = check_value(entry, value)
        if problem:
            diagnostics.append(f"{number}: {problem}")

    for name, entry in schema.items():
        if entry.required and name not in seen:
            diagnostics.append(f"missing: {name}")
    return diagnostics


def main(argv):
    strict = quiet = False
    paths = []
    for arg in argv:
        if arg == "--strict":
            strict = True
        elif arg == "-q":
            quiet = True
        elif arg.startswith("-"):
            print(f"cfgcheck: unknown option {arg}", file=sys.stderr)
            return EXIT_USAGE
        else:
            paths.append(arg)
    if len(paths) != 2:
        print("usage: cfgcheck [--strict] [-q] SCHEMA CONFIG", file=sys.stderr)
        return EXIT_USAGE
    schema_path, config_path = paths

    try:
        schema_lines = read_lines(schema_path)
    except OSError as e:
        print(f"cfgcheck: {e}", file=sys.stderr)
        return EXIT_USAGE
    try:
        schema = parse_schema(schema_lines)
    except SchemaError as e:
        print(f"cfgcheck: invalid schema: {e}", file=sys.stderr)
        return EXIT_BAD_SCHEMA
    try:
        config_lines = read_lines(config_path)
    except OSError as e:
        print(f"cfgcheck: {e}", file=sys.stderr)
        return EXIT_USAGE

    diagnostics = check_config(config_lines, schema, strict)
    if not quiet:
        for d in diagnostics:
            print(d)
        print(f"errors: {len(diagnostics)}" if diagnostics else "OK")
    return EXIT_ERRORS if diagnostics else EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
