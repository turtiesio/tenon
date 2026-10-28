# Task 01: cfgcheck (INI config validator)

## Goal

Write a command-line tool that checks an INI-style configuration file against
a small schema file. The tool reports every problem it finds, one diagnostic
per line, in a fixed order, followed by a summary line. It distinguishes usage
errors, an invalid schema and an invalid configuration by exit code.

## Interface

```
cfgcheck [--strict] [-q] SCHEMA CONFIG
```

- **Arguments.** Options may appear anywhere among the arguments. Every
  argument that starts with `-` is an option. The known options are
  `--strict` and `-q`, and each may be given more than once (same effect as
  once). Exactly two non-option arguments are required: the schema file path
  and the config file path, in that order.
- **Files.** Both files are ASCII text. Lines are split on `\n`. A final line
  without `\n` is still a line, and a file ending in `\n` has no extra empty
  line after it. One trailing `\r` is removed from each line before any other
  processing. Lines are numbered from 1.
- **stdout.** Diagnostics and the summary line (formats below), each ending
  with `\n`. With `-q`, nothing is printed on stdout at all, and only the exit
  code reports the result.
- **stderr.** Messages for exit codes 2 and 3. Not tested.
- **Exit codes.**
  - `0`: the config is valid (no diagnostics).
  - `1`: the config has at least one diagnostic.
  - `2`: usage error (unknown option, wrong number of non-option arguments),
    or SCHEMA or CONFIG cannot be read. Nothing is printed on stdout.
  - `3`: the schema is invalid. Nothing is printed on stdout.

  The checks happen in this order: usage, read SCHEMA, validate the schema,
  read CONFIG, validate the config. The first failure decides the exit code.

## Schema format

- Blank lines (empty, or only spaces and tabs) are ignored. Lines whose first
  non-space, non-tab character is `#` are comments and are ignored.
- Every other line is an entry made of tokens separated by one or more spaces
  or tabs (leading and trailing spaces and tabs are ignored):

  ```
  SECTION.KEY TYPE PRESENCE [ARG]
  ```

  - `SECTION` and `KEY` each match `[a-z][a-z0-9_]*`, joined by one `.`.
  - `PRESENCE` is `required` or `optional`.
  - `TYPE` and its `ARG`:

    | TYPE | ARG | Meaning of ARG |
    |---|---|---|
    | `int` | optional, `MIN..MAX` | MIN and MAX each match `-?[0-9]{1,18}`, and MIN ≤ MAX. |
    | `string` | optional, `maxlen=N` | N matches `[0-9]{1,7}`. |
    | `bool` | none allowed | |
    | `enum` | required, `V1,V2,...` | One or more non-empty values separated by single commas. |

- The schema is **invalid** (exit 3) if any entry has the wrong number of
  tokens, an unknown TYPE or PRESENCE, a malformed `SECTION.KEY` or ARG, a
  missing `enum` ARG, an ARG for `bool`, or the same `SECTION.KEY` as an
  earlier entry. A schema with no entries is valid.

## Config format

Each line is exactly one of the following, checked in this order:

1. **Ignored**: blank (empty, or only spaces and tabs), or the first
   non-space, non-tab character is `#` or `;`.
2. **Section header**: after removing leading and trailing spaces and tabs,
   the line is `[NAME]` where NAME matches `[a-z][a-z0-9_]*`. It makes NAME the
   current section. A section may appear more than once, and its keys then
   accumulate.
3. **Key line**: the line contains `=`. KEY is the text before the **first**
   `=`, and VALUE is the text after it, both with leading and trailing spaces
   and tabs removed. KEY must match `[a-z][a-z0-9_]*`. VALUE may be empty, and
   it may contain `=`, `#` and `;` (there are no inline comments).
4. Anything else, including a key line whose KEY does not match, is a
   **syntax error**.

## Validation rules

Each config line produces **at most one** diagnostic, chosen as follows:

- A syntax error gives `<L>: syntax error`.
- A key line before any section header gives `<L>: key outside section`.
- A key line whose `SECTION.KEY` already appeared on an earlier key line gives
  `<L>: duplicate key SECTION.KEY`. Its value is not checked.
- A key line whose `SECTION.KEY` is not in the schema gives
  `<L>: unknown key SECTION.KEY` with `--strict`. Without `--strict` the line
  is silently ignored. This applies even when the whole section is unknown.
- Otherwise, the value is checked against the schema entry:

  | TYPE | Valid when | Diagnostic otherwise |
  |---|---|---|
  | `int` | VALUE matches `-?[0-9]{1,18}` (leading zeros allowed, `-0` is 0) and, if a range is given, MIN ≤ value ≤ MAX | `<L>: SECTION.KEY: not an integer` if it does not match; `<L>: SECTION.KEY: out of range MIN..MAX` if it is outside the range. MIN and MAX are printed exactly as written in the schema. |
  | `bool` | VALUE is exactly `true` or `false` | `<L>: SECTION.KEY: not a boolean` |
  | `string` | always, unless `maxlen=N` is given and VALUE is longer than N characters | `<L>: SECTION.KEY: longer than N` (N as written in the schema) |
  | `enum` | VALUE equals one of the listed values (case-sensitive) | `<L>: SECTION.KEY: not one of V1,V2,...` (the ARG exactly as written in the schema) |

- **Missing keys.** Every `required` schema entry whose `SECTION.KEY` never
  appears on a key line (inside a section) gives `missing: SECTION.KEY`. A key
  that appears with an invalid value, or more than once, is **not** missing.

## Output

1. All line diagnostics, in increasing line order.
2. All `missing:` diagnostics, in the order of the entries in the schema file.
3. A summary line: `OK` if there were no diagnostics, otherwise
   `errors: <N>`, where N is the total number of diagnostics (line and
   missing).

With `-q`, stdout is empty, and the exit code is the same as without `-q`.

Limits: each file is at most 1 MB, and a line is at most 1000 characters.

## Examples

Every line shown ends with `\n`. In `cmd`, arguments are separated by spaces.
Unless stated otherwise, the working directory contains this `schema.txt`:

```
# service settings
server.port   int     required 1..65535
server.host   string  required maxlen=10
server.debug  bool    optional
log.level     enum    required debug,info,warn
```

### Example 1: a valid config

`config.ini`:
```
[server]
port = 8080
host = localhost
debug = true

[log]
level = info
```
cmd: `cfgcheck schema.txt config.ini`

stdout:
```
OK
```
exit: `0`

### Example 2: several kinds of errors

`config.ini`:
```
; broken
[server]
port = 70000
host = a-very-long-hostname
debug = yes
port = 1
timeout = 5
[log]
garbage line
```
cmd: `cfgcheck schema.txt config.ini`

stdout:
```
3: server.port: out of range 1..65535
4: server.host: longer than 10
5: server.debug: not a boolean
6: duplicate key server.port
9: syntax error
missing: log.level
errors: 6
```
exit: `1`

(Line 7 is ignored because `--strict` is not given. `log.level` never
appears, so it is missing.)

### Example 3: strict mode, a key outside any section, an empty value

`config.ini`:
```
level = info
[log]
level = verbose
color = on
[server]
port=443
host=
```
cmd: `cfgcheck schema.txt --strict config.ini`

stdout:
```
1: key outside section
3: log.level: not one of debug,info,warn
4: unknown key log.color
errors: 3
```
exit: `1`

(`host=` has an empty value, which is a valid string of length 0. `log.level`
appears on line 3, so it is not missing.)

### Example 4: quiet mode

`config.ini` is the same as in Example 2.

cmd: `cfgcheck -q schema.txt config.ini`

stdout: (empty)

exit: `1`

### Example 5: invalid schema and usage errors

- `bad.txt` contains the single line `a.b float required`.
  cmd: `cfgcheck bad.txt config.ini` gives stdout (empty) and exit `3`
  (whatever `config.ini` contains, or even if it does not exist).
- cmd: `cfgcheck schema.txt` gives stdout (empty) and exit `2`.
- cmd: `cfgcheck -x schema.txt config.ini` gives stdout (empty) and exit `2`.
- cmd: `cfgcheck schema.txt nope.ini` (no such file) gives stdout (empty) and
  exit `2`.

## Not required

- Quoted values, escape sequences, inline comments, multi-line values.
- Non-ASCII input.
- Nested sections or keys containing dots in the config.
- Any particular stderr wording.
