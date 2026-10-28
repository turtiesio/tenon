# Tenon builtin API and standard library

The companion of [docs/reference.md](reference.md), the language (cited here
as "reference §N"). This page describes the methods of the builtin types, the
operations of the capabilities and the standard library modules. The full
list with signatures is the prelude, `lib/prelude.tn` in the repository
(`docs/prelude.tn` in a study kit), which is ordinary Tenon source and the
single source of the builtin API. Every claim here is checked by a test in
`tests/` (run `./check`).

## Builtin types and capabilities


- `Str`: `len byte slice find split lines words trim trim_start trim_end
  starts_with ends_with contains to_int to_float upper lower replace chars
  find_from is_digits strip_prefix strip_suffix (Option) trim_chars (remove
  given ASCII bytes from both ends, e.g. `s.trim_chars(" \t")`)
  trim_start_chars trim_end_chars (from one end only:
  `"0250".trim_end_chars("0") == "025"`, `"0250".trim_chars("0") == "25"`)
  repeat pad_left pad_right is_empty rfind split_once rsplit_once to_int_radix
  bytes char_count all_bytes`; `Int.char()` makes a one-character string from
  a code point (`'A'.char() == "A"`, `233.char() == "é"`); `Str.from_utf8(bytes)`
  and `Str.from_utf8_lossy(bytes)` make text from bytes (see "Bytes" below).
  - Bytes and characters: `s.len()` is the length in **bytes** (UTF-8), and
    `byte`, `slice`, `find` and the other offsets are byte offsets.
    `s.char_count()` is the number of code points (`"Zürich".len() == 7`,
    `"Zürich".char_count() == 6`). `s.chars()` returns the code points, each as
    a one-character string (`"Zü".chars() == ["Z", "ü"]`; a combining accent
    is a code point of its own).
  - `s.pad_left(width, fill)` / `s.pad_right(width, fill)` add `fill` until
    the string is `width` **code points** long (like Python's `rjust`/`ljust`),
    so `"Zürich".pad_right(8, ".") == "Zürich.."`; a longer string is returned
    unchanged. `fill` must be exactly one character (one code point),
    otherwise the call traps (`pad_left: fill must be exactly one character`).
    Characters that a terminal shows double-width (`"東京"`) still count as one.
  - `s.rfind(sub)` is the byte offset of the last match. `s.split_once(sep)` /
    `s.rsplit_once(sep)` split around the first / last `sep`:
    `"k=v=w".split_once("=") == Some(("k", "v=w"))`, `None` if `sep` is absent.
    The pieces share the original's bytes, like `slice`.
  - `s.split(sep)` keeps empty pieces: `"a,,b,".split(",")` is
    `["a", "", "b", ""]` and `"".split(",")` is `[""]`.
  - `s.lines()` gives the lines `Console.read_line` would read from `s`: it
    splits on `"\n"`, drops a final empty piece (the text after a last
    `"\n"`), then removes one trailing `"\r"` from every line, also from the
    last. So `"".lines() == []`, `"\n".lines() == [""]`,
    `"a\n\nb\n".lines() == ["a", "", "b"]`, `"a\r\nb\r".lines() == ["a", "b"]`,
    `"a\r\r\n".lines() == ["a\r"]`, `"\r".lines() == [""]`. (Before study
    wave 6 it kept the `"\r"`.) `s.words()` splits on runs of spaces, tabs,
    `"\r"` and `"\n"` (not `\v` or `\f`).
  - `trim_chars`, `trim_start_chars` and `trim_end_chars` remove bytes that
    occur in `chars`; only ASCII bytes count, so a non-ASCII character is
    never removed (`"xéx".trim_chars("x") == "é"`).
  - `s.to_int()` accepts an optional `+`/`-` and decimal digits only (no spaces,
    no `_`), and gives `None` on overflow. `s.to_int_radix(base)` (base 2-36,
    otherwise a trap) accepts an optional `-` (no `+`) and one or more digits
    `0-9a-z`, letters in either case, each below `base`; no prefix such as `0x`,
    no spaces or `_`; `None` if invalid or out of range (`INT_MIN` parses):
    `"ff".to_int_radix(16) == Some(255)`. `s.to_float()` also accepts `1.5`,
    `.5`, `5.`, `1e-3`, `inf` and `nan`.
  - `trim`, `trim_start` and `trim_end` remove the bytes `' '`, `'\t'`,
    `'\n'`, `'\r'` and form feed (12), not vertical tab (11);
    `upper`/`lower` change ASCII letters only.
  - `s.all_bytes(pred)` is true when `pred` holds for every byte (and for
    `""`), for validation with the `Int` classes below:
    `name.all_bytes(fn(b) => b.is_lower() or b.is_digit() or b == '_')`.
- `List[T]`: `len push pop insert remove clear slice sort sort_by reverse get
  sort_by_desc sort_with swap first last index_of contains extend sorted reversed map filter retain any all count
  is_empty binary_search max_by min_by group_by`, `+` concatenates; `List[Str].join`, `List[Int].sum`.
  - `xs.retain(keep)` keeps, in place and in order, the elements for which
    `keep` is true (`filter` in place; needs a mutable place, also a deep one:
    `self.res[r].queue.retain(fn(w) => w != name)`).
  - `xs.max_by(key)` / `xs.min_by(key)` give the element with the largest /
    smallest key as an `Option` (`None` for an empty list); of several equal
    keys, the first one in the list. Keys compare with the derived ordering, so
    tuples break ties: `ps.max_by(fn(p) => (p.score, p.name))`.
  - `xs.group_by(key)` gives a `Map[K, List[T]]` of every element by key: keys
    in the order of their first occurrence, each group in list order
    (`["ab", "c", "de"].group_by(fn(s) => s.len()) == [2: ["ab", "de"], 1: ["c"]]`).
    Equal keys need not be adjacent (unlike Python's `itertools.groupby`).
  - `xs.binary_search(x)` (`Result[Int, Int]`) needs `xs` sorted ascending by
    the derived ordering (as `sort()` leaves it; otherwise the result is
    unspecified). `Ok(i)`: `i` is the first index with `xs[i] == x`; `Err(i)`:
    `x` is absent and `xs.insert(i, x)` keeps the list sorted. O(log n):
    `[1, 3, 5].binary_search(3) == Ok(1)`, `[1, 3, 5].binary_search(4) == Err(2)`.
- `Map[K, V]`: `m[k]` (traps if missing), `get` (Option), `get_or`,
  `update(k, default, f)` (store `f` of the current or default value), `insert`,
  `or_insert`, `remove`, `contains`, `keys`, `values`, `entries`, `len`,
  `is_empty`. Removing a key keeps the order of the others; inserting a key
  again puts it last.
  - `m.or_insert(k, v)` inserts `v` only if `k` is absent, so grouping is
    `m.or_insert(k, []); m[k].push(x)` (the push changes the entry in place).
- `Heap[T]`: a priority queue: `Heap.new()`, `push`, `pop` (smallest first, as
  `Option`), `peek`, `len`, `is_empty`. For largest first push negated keys.
- `Set[T]`: `Set.new()`, `Set.of(list)`, `insert` (false if already present),
  `remove` (false if absent), `contains`, `len`, `is_empty`, `items` (insertion order).
- `xs.enumerate()` gives `[(0, a), (1, b), ...]` (`for (i, x) in xs.enumerate()`).
- `List.filled(n, x)` makes a list of n copies of x; `xs.sort_with(fn(a, b) => ...)`
  sorts stably by a comparison (negative: a first).
- `Option[T]`: `unwrap expect unwrap_or is_some is_none map map_or and_then filter is_some_and ok_or`.
- `Result[T, E]`: `unwrap expect unwrap_or is_ok is_err ok err map map_err
  map_or and_then is_ok_and is_err_and` (as for `Option`; `err` gives the error
  as an `Option`; `and_then` keeps the error type).
- `Int`: `abs min max to_float to_str char pow`; `checked_add checked_sub
  checked_mul checked_div checked_pow` give `None` instead of trapping (also for a
  division by zero or a negative exponent); `x.pow(e)` traps on overflow and on
  `e < 0` (`0.pow(0) == 1`); `x.to_str_radix(base)` writes `x` in base 2-36
  (lowercase digits, `-` for negatives; another base traps):
  `255.to_str_radix(16) == "ff"`; `rem_euclid` and
  `div_euclid` (the remainder is never negative; no intermediate overflow: only
  `INT_MIN.div_euclid(-1)`, whose quotient does not fit, traps); `fmt_fixed(scale)` writes a
  fixed-point integer (`1234.fmt_fixed(2) == "12.34"`, for money in cents; any `Int`, `INT_MIN` included); constants
  `INT_MAX`, `INT_MIN`; and for code points
  `is_digit is_alpha is_alnum is_space is_upper is_lower` (ASCII only:
  `'é'.is_alpha()` is false; `is_space` is exactly `' '`, `'\t'`, `'\n'` and
  `'\r'` (32, 9, 10, 13), not vertical tab or form feed (11, 12); `s.byte(i).is_digit()`, `'7' - '0'`), and `char`
  (the code point as a one-character `Str`); `Float`: `to_int floor ceil round
  sqrt abs min max`, and `to_fixed(decimals)` (exactly that many digits; rounds the
  binary value half to even, like printf). There are no bitwise operators: use
  `/`, `%` and `pow` (`x / 2.pow(k)` shifts right by `k` for `x >= 0`).
- `Console`: `print println eprintln read_line read_all flush read_all_bytes
  read_bytes write_bytes`. `read_line` returns `None` at end of input; it removes the
  line's `"\n"` and then one trailing `"\r"` from every line, including a
  last line that has no `"\n"` (`"a\r\r\nb\r"` reads as `"a\r"`, `"b"`);
  `read_all` keeps every `"\r"`.
  Standard output is buffered: it is flushed before any blocking read and at
  exit; a program that answers requests line by line while another process
  waits calls `flush()` after each answer.
- `Fs`: `read write append exists is_dir remove rename list mkdir mkdir_one
  within read_only read_bytes write_bytes append_bytes truncate` (details in reference §10).
  `mkdir` creates missing parents, `mkdir_one` exactly one directory; `rename`
  is atomic and replaces the target; `remove` deletes a file or an empty
  directory.
- Bytes are a `List[Int]` whose elements are 0..255.
  - `fs.read_bytes(path)` (`Result[List[Int], IoError]`) reads any file;
    `fs.write_bytes(path, data)` replaces a file atomically like `write`,
    `fs.append_bytes(path, data)` appends like `append`.
    `con.read_all_bytes()` returns the rest of standard input unchanged
    (after any lines `read_line` took); `con.read_bytes(n)` returns the next
    `n` bytes, waiting for them, and fewer only at the end of input (`[]`
    there, and for `n <= 0`), so a header line read with `read_line` can
    announce a body of exactly `n` bytes; `con.write_bytes(data)` writes to
    standard output. Writing an element outside 0..255 traps, before any file
    is touched.
  - `s.bytes()` is the UTF-8 encoding of `s`. `Str.from_utf8(bytes)` is
    `None` if the bytes are not valid UTF-8 (overlong forms, surrogates, code
    points above U+10FFFF and truncated sequences are invalid) or an element
    is outside 0..255. `Str.from_utf8_lossy(bytes)` replaces each maximal
    invalid sequence with U+FFFD (the rule below) and traps on an element
    outside 0..255.
  - In a C build a byte list costs 8 bytes per byte; `read_bytes` of a 10 MB
    file takes about 5 ms (one allocation, sized from the file).

  ```tenon
  let data = sys.fs.read_bytes("blob.bin")?                // e.g. [0, 255, 104, 105]
  let hex = data.map(fn(b) => b.to_str_radix(16).pad_left(2, "0")).join(" ")
  let text = Str.from_utf8(data).unwrap_or("<binary>")
  sys.fs.write_bytes("copy.bin", data)?
  ```
- Invalid UTF-8 on input. A `Str` is always valid UTF-8, so every API that
  turns outside bytes into text decides what to do with invalid bytes:
  - `Fs.read`: `Err(Failed("path: invalid UTF-8"))`; nothing is replaced.
  - Replaced with U+FFFD (bytes EF BF BD, one per maximal invalid sequence, as
    `Str.from_utf8_lossy` does): `Console.read_line`, `Console.read_all`,
    `sys.args`, the names from `Fs.list`, `Conn.read_line`, `Conn.read`, and
    `Data` from `Poller.wait` (a multi-byte character split between two reads
    becomes U+FFFD; reference §15).
  - `decode` (reference §14) rejects a string literal whose escapes do not make valid
    UTF-8.
  - The byte APIs above never change a byte.
- Line endings: `s.lines()`, `Console.read_line` and `Conn.read_line` all
  remove the `"\n"` and then one trailing `"\r"` from every line, also from a
  last line without `"\n"`, so CRLF and LF input read the same
  (`"a\r\nb".lines() == ["a", "b"]`); `s.words()` treats `"\r"` as a
  separator; `read_all`, `Fs.read` and `s.split("\n")` keep every `"\r"`.
- Paths: `path_join(a, b)`, `path_parent(p)`, `path_base(p)` (reference §10).
- `Clock`: `now_ms mono_ns sleep_ms`.
- `Proc`: `run run_with exit env`. `p.run(cmd, args)` (`Result[Int, IoError]`) runs the
  program `cmd` (looked up in `PATH` unless it contains a `/`) with the
  arguments `args`, no shell involved, sharing standard input, output and
  error; standard output is flushed first. It waits and gives the exit
  status: `Ok(3)` for a command that exits with 3. `Err(NotFound(cmd))` if
  there is no such program, `Err(Denied(cmd))` if it is not executable,
  `Err(Failed("cmd: reason"))` otherwise (`"sh: terminated by signal 9"`, or
  `"argument contains a NUL byte"`). `p.env(name)` (`Option[Str]`) reads an
  environment variable (`None` if unset, or if `name` is empty or contains
  `=` or a NUL byte; invalid UTF-8 becomes U+FFFD). A `Proc` is the whole
  authority of the user (a command can do anything), so hand it only to
  the code that must run commands: `fn build(p: Proc, out: Str)` says so in
  its signature.
  `p.run_with(cmd, args, dir, input, timeout_ms)` (`Result[ProcOut, IoError]`)
  runs `cmd` the same way but in directory `dir` (`""`: the current one;
  `Err(NotFound(dir))` if it is not a directory), with the bytes `input`
  (`List[Int]`, each 0..255, else a trap) as its standard input, and captures
  its standard output and error: `ProcOut { status, signal, timed_out, out,
  err }` with `out` and `err` as bytes (`Str.from_utf8_lossy(o.out)` for
  text). A command still running after `timeout_ms > 0` milliseconds is
  killed (SIGKILL) together with every process it started (the command runs
  in a process group of its own, and the whole group is killed) and
  `timed_out` is `true`; `0` waits for ever. `status` is
  the exit status, or `-1` when the command was ended by a signal (`signal`
  is then its number, else 0). `p.exit(status)` ends the program at once with
  `status` after flushing standard output: any value 0-255, including the
  runtime's reserved codes (70, 71, 72, 74), so a program that runs other
  programs (an interpreter, a test runner) can pass their status on; a value
  outside 0-255 traps. Both need the `Proc` authority, like `run`.

## Standard library

- Standard library modules: `journal` (append-only, checksummed, crash-safe
  record log) and `regex` (below). Their source is `lib/std/journal.tn` and
  `lib/std/regex.tn` in the repository, `docs/std-journal.tn` and
  `docs/std-regex.tn` in a study kit; either way `import journal` and
  `import regex` find them.
- `journal` has its own on-disk format: each record is one line
  `BODY #CHECKSUM`, and `load` archives and drops any line that does not
  check (also one that gained a `"\r"` at its end). It cannot read or write
  a file format that a task fixes (one command per line, say): for that use
  `Fs.append` (durable), `Fs.write` (atomic) and `Fs.truncate` directly.

### `regex`

Regular expressions, written in Tenon (`lib/std/regex.tn`, or `docs/std-regex.tn`
in a study kit; its header comment is the full specification). Matching is by backtracking, character by character over
UTF-8; offsets are byte offsets.

```tenon
import regex

let date = regex.compile(r"(\d{4})-(\d{2})-(\d{2})").unwrap()     // Result[Regex, Str]
match date.full("2024-03-15") {                                   // Option[List[Str]]
    Some(g) => con.println("{g[1]} {g[2]} {g[3]}"),                 // g[0] is the whole match
    None => con.println("not a date"),
}
```

- `regex.compile(pattern) -> Result[Regex, Str]`; the error text is
  `"<problem> at byte <offset>"` (offset into the pattern).
- `re.full(s) -> Option[List[Str]]`: the whole string must match; the list holds
  the whole match, then one entry per capture group (`""` if it did not take part).
  `re.is_full(s) -> Bool`.
- `re.find(s) -> Option[(Int, List[Str])]`: the leftmost match, its start byte
  offset and its groups. `re.find_all(s) -> List[Str]`: non-overlapping matches
  (an empty match advances by one character).
  `re.replace_all(s, with) -> Str`: `with` is literal text.
- Syntax: literals, `.` (not `"\n"`), `[abc]` `[a-z0-9_]` `[^...]`, `\d \w \s \D \W \S`
  (ASCII), `\b \B`, escaped punctuation (`\.` `\\` `\[`), `^ $` (start / end of the
  string), `( )` and `(?: )`, `|`, greedy `* + ? {m} {m,} {m,n}` and lazy `*? +? ?? {m,n}?`.
  Write patterns as raw strings (`r"\d{2}:\d{2}"`, reference §2), so that backslashes and
  braces are taken as they are. In a normal string each regex backslash must be
  doubled and `{` written `\{` (`"\\d\{2}"`): `"\d{2}"` is an error and
  `"\\d{2}"` interpolates `{2}`.
  Not supported: backreferences, lookaround, named groups, flags.
- A pattern that would take more than about a million backtracking steps (for
  example `(a+)+b` on a long run of `a`) stops the program with `panic`, naming the pattern.
