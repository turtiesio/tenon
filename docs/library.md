# Tenon builtin API and standard library

The companion of [docs/reference.md](reference.md), the language (cited here
as "reference §N"). This page describes the methods of the builtin types, the
operations of the capabilities and the standard library modules. Every
function, method, constant and type of the prelude is listed with its full
signature and its behaviour, edge cases included, in "Every prelude item"
at the end of this page. The prelude itself is `lib/prelude.tn` in the
repository (`docs/prelude.tn` in a study kit): ordinary Tenon source and the
single source of the builtin API; `ops/gates/libtable.tn` keeps the table
equal to it. Every claim here is checked by a test in `tests/` (run
`./check`; the tests behind each section are named in an HTML comment at its
start).

## Builtin types and capabilities

<!-- test: tests/run/strings.tn tests/run/str_char_count_pad.tn tests/run/str_split_once.tn tests/run/str_lines_cr.tn tests/run/str_trim_sides.tn tests/run/radix_pow.tn tests/run/charclass.tn tests/run/lists.tn tests/run/list_retain.tn tests/run/list_by_helpers.tn tests/run/list_binary_search.tn tests/run/maps.tn tests/run/sets.tn tests/run/prelude_more.tn tests/run/prelude_more2.tn tests/run/result_combinators.tn tests/run/fmt_fixed_extremes.tn tests/run/trap_euclid_extremes.tn tests/run/io_cr.tn tests/run/io_lossy.tn tests/run/bytes_fs.tn tests/run/bytes_read_n.tn tests/run/bytes_stdin.tn tests/run/bytes_str.tn tests/run/bytes_trap.tn tests/run/path_helpers.tn tests/run/proc_run_with.tn tests/run/cap_probe_proc.tn tests/run/doc_wave6_claims.tn tests/run/doc_library_table.tn -->

- `Str` (every method: "Every prelude item", Str). Text is immutable UTF-8;
  `Int.char()` makes a one-character string from a code point
  (`'A'.char() == "A"`, `233.char() == "é"`); `Str.from_utf8(bytes)` and
  `Str.from_utf8_lossy(bytes)` make text from bytes (see "Bytes" below).
  Finding: `find`, `find_from`, `rfind` and `List.index_of` give an
  `Option[Int]` (`None` when absent), never -1. `s.is_digits()` is true for a
  non-empty string of ASCII digits only (`""`, `"-1"` and `"+1"` are false);
  for a number with a sign use `to_int()`.
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
  - `s.slice(start, end)` traps when an end falls inside a multi-byte
    character (`"é".slice(0, 1)`: `slice [0, 1) is not on a character
    boundary`), as it does out of range; offsets from `find` and `rfind`, or
    0 and `len()`, are always boundaries.
  - `s.rfind(sub)` is the byte offset of the last match (`Option[Int]`). `s.split_once(sep)` /
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
- `List[T]` (every method: "Every prelude item", List). `a + b` is a new list
  of the elements of `a`, then those of `b` (`ds + [c]` appends one element to
  a copy; `xs.push(c)` changes `xs` in place). `xs.remove(i)` returns the
  removed element (`T`, not an `Option`) and `xs.pop()` the last as an
  `Option`; both are values, so discard them with `let _ = xs.remove(0)`.
  `xs.slice(start, end)` is half-open like `Str.slice` and traps out of range.
  `reverse` and `sort` change the list in place (a `var`); `reversed` and
  `sorted` return a copy.
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
  `or_insert`, `remove` (the removed value as an `Option`), `contains`, `keys`,
  `values`, `entries`, `len`, `is_empty`. Removing a key keeps the order of the
  others; inserting a key again after removing it puts it last (assigning an
  existing key keeps its place).
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
  within read_only read_bytes write_bytes append_bytes truncate` (details in
  reference §10; for a file format of your own, "Writing files" below).
  `exists` and `is_dir` return a plain `Bool`. `mkdir` creates missing parents, `mkdir_one` exactly one directory; `rename`
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

## Writing files

<!-- test: tests/run/io_fs.tn tests/run/fs_truncate.tn tests/run/doc_claims_wave3.tn tests/run/doc_library_table.tn -->

A task that fixes its own file format (one command per line, a snapshot
file, a journal of its own) writes it with `Fs` directly; the `journal`
module (below) has a format of its own and cannot read or write another.

- `fs.append(path, line + "\n")` adds a record durably: it returns only after
  the data is on disk (fsync), so a program that must "write before
  answering" appends, then answers. `append` creates a missing file.
- `fs.write(path, text)` replaces a whole file atomically and durably: it
  writes `path + ".tmp"`, fsyncs it and renames it over `path`, so a reader
  (or a restart after a crash) sees the old file or the new one, never a
  mix. That already is the usual snapshot protocol ("write `snapshot.tmp`,
  then rename it to `snapshot`"): call `fs.write("snapshot", text)`.
- When a spec names the temporary file itself (and, say, a test looks for it
  or a recovery step must find it), follow the spec with
  `fs.write("snapshot.tmp", text)` and then `fs.rename("snapshot.tmp",
  "snapshot")`. Each step is atomic on its own; `write` uses
  `snapshot.tmp.tmp` internally for the first. Never keep a file of your own
  named `PATH.tmp` next to a file you `write`: `write` removes and replaces it.
- `fs.truncate(path, len)` drops a torn last record in place:
  `fs.truncate(p, text.rfind("\n").map_or(0, fn(i) => i + 1))`. It needs an
  existing file; to empty or create one, `fs.write(path, "")`.
- `fs.rename(from, to)` is atomic and replaces `to`; `fs.mkdir_one(dir)`
  creates exactly one directory and fails if it exists, which makes it a
  lock or a claim.

## Standard library

<!-- test: tests/run/std_journal_cr.tn tests/run/modules.tn -->

- Standard library modules: `journal` (append-only, checksummed, crash-safe
  record log) and `regex` (below). Their source is `lib/std/journal.tn` and
  `lib/std/regex.tn` in the repository, `docs/std-journal.tn` and
  `docs/std-regex.tn` in a study kit; either way `import journal` and
  `import regex` find them.
- `journal` has its own on-disk format: each record is one line
  `BODY #CHECKSUM`, and `load` archives and drops any line that does not
  check (also one that gained a `"\r"` at its end). It cannot read or write
  a file format that a task fixes (one command per line, say): for that use
  `Fs.append` (durable), `Fs.write` (atomic) and `Fs.truncate` directly, as
  "Writing files" above describes.

### `regex`

<!-- test: tests/run/std_regex.tn tests/run/std_regex_limit.tn tests/run/doc_regex_example.tn tests/run/raw_string.tn -->

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

## Every prelude item

<!-- test: ops/gates/libtable.tn tests/run/doc_library_table.tn tests/run/strings.tn tests/run/lists.tn tests/run/maps.tn tests/run/sets.tn tests/run/prelude_more.tn tests/run/prelude_more2.tn tests/run/result_combinators.tn tests/run/radix_pow.tn tests/run/charclass.tn tests/run/path_helpers.tn tests/run/trap_index.tn tests/run/trap_pow_negative.tn tests/run/trap_radix_base.tn tests/run/trap_int_radix_base.tn tests/run/trap_pad_fill.tn tests/run/trap_slice_boundary.tn tests/run/trap_split_empty.tn tests/v2/run/workers_basic.tn tests/v2/run/workers_channels.tn tests/v2/run/workers_par_map.tn tests/v2/run/trait_show.tn -->

The table is generated from `lib/prelude.tn` and `lib/v2/prelude.tn`
(`tenon run ops/gates/libtable.tn --write`); the behaviour column is written
by hand, and `./check` fails when a signature here differs from the prelude.
A method `T.name(self, ...)` is called as `x.name(...)`, one without `self`
as `T.name(...)` (`Str.from_utf8(b)`, `List.filled(3, 0)`); `mut self` needs
a mutable place (reference §6). "Traps" means the program stops
(reference §9).

<!-- prelude-table: begin -->

#### Core (lib/prelude.tn)

| Signature | Behaviour |
|---|---|
| `enum Option[T] { Some(T), None }` | `Some(x)` or `None`; there is no null. `?` on `None` returns `None` from the function |
| `enum Result[T, E] { Ok(T), Err(E) }` | `Ok(x)` or `Err(e)`; `?` on `Err(e)` returns `Err(e)` (the same error type, no conversion) |
| `enum IoError { NotFound(Str), Denied(Str), Failed(Str) }` | every I/O failure: `NotFound(path)`, `Denied(path)`, `Failed("path: reason")` (the OS's text); prints as `NotFound("x")` |
| `struct Sys { pub console: Console, pub fs: Fs, pub clock: Clock, pub net: Net, pub proc: Proc, pub args: List[Str] }` | the authority `main` receives (reference §10); nothing else can make one |
| `panic[T](msg: Str) -> T` | traps with `msg` (`trap: msg`, exit status 70); its type fits any place |
| `assert(cond: Bool)` | traps (`assertion failed`) when `cond` is false |
| `encode[T](x: T) -> Str` | the canonical literal text of `x` with every field (strings quoted and escaped: `encode("a\n")` is the 5 characters `"a\n"`); not for functions, capabilities, linear or unique values, or values with hidden fields (reference §14) |
| `decode[T](s: Str) -> Result[T, Str]` | parses exactly the text `encode` gives back into a `T` (annotate the type); anything else is `Err("cannot decode T at byte N")` |

#### Int / Float (lib/prelude.tn)

| Signature | Behaviour |
|---|---|
| `const INT_MAX: Int = 9223372036854775807` | the largest `Int`, 2^63 - 1 |
| `const INT_MIN: Int = -9223372036854775807 - 1` | the smallest `Int`, -2^63; `INT_MIN.abs()` and `-INT_MIN` overflow (trap) |
| `Int.checked_add(self, o: Int) -> Option[Int]` | `self + o`, `None` on overflow |
| `Int.checked_sub(self, o: Int) -> Option[Int]` | `self - o`, `None` on overflow |
| `Int.checked_mul(self, o: Int) -> Option[Int]` | `self * o`, `None` on overflow |
| `Int.checked_div(self, o: Int) -> Option[Int]` | `self / o` (truncating), `None` for `o == 0` and for `INT_MIN / -1` |
| `Int.to_float(self) -> Float` | the nearest `Float` (exact up to 2^53) |
| `Int.abs(self) -> Int` | the absolute value; `INT_MIN.abs()` traps (overflow) |
| `Int.min(self, o: Int) -> Int` | the smaller of the two |
| `Int.max(self, o: Int) -> Int` | the larger of the two |
| `Int.rem_euclid(self, d: Int) -> Int` | the remainder that is never negative: `(-7).rem_euclid(3) == 2`, also for `d < 0` (`7.rem_euclid(-3) == 1`); `d == 0` traps |
| `Int.div_euclid(self, d: Int) -> Int` | the quotient that goes with `rem_euclid` (`self == q * d + r`, `0 <= r`): `(-7).div_euclid(3) == -3`, `7.div_euclid(-2) == -3`; traps for `d == 0` and `INT_MIN.div_euclid(-1)` |
| `Int.pow(self, e: Int) -> Int` | `self` to the power `e`; `0.pow(0) == 1`; traps on overflow and on `e < 0` |
| `Int.checked_pow(self, e: Int) -> Option[Int]` | `pow`, but `None` on overflow or `e < 0` |
| `Int.to_str_radix(self, base: Int) -> Str` | the digits in `base` 2-36, lowercase, `-` for negatives, no prefix: `255.to_str_radix(16) == "ff"`, `INT_MIN` works; another base traps |
| `Int.fmt_fixed(self, scale: Int) -> Str` | the integer as a fixed-point number with `scale` decimals: `1234.fmt_fixed(2) == "12.34"`, `(-5).fmt_fixed(2) == "-0.05"`, `7.fmt_fixed(3) == "0.007"`; `scale <= 0` gives `to_str()`; every `Int`, `INT_MIN` included |
| `Int.char(self) -> Str` | the code point as a one-character string: `'A'.char() == "A"`, `233.char() == "é"` |
| `Int.is_digit(self) -> Bool` | `'0'..'9'` (ASCII only) |
| `Int.is_upper(self) -> Bool` | `'A'..'Z'` (ASCII only) |
| `Int.is_lower(self) -> Bool` | `'a'..'z'` (ASCII only; `'é'.is_lower()` is false) |
| `Int.is_alpha(self) -> Bool` | an ASCII letter |
| `Int.is_alnum(self) -> Bool` | an ASCII letter or digit |
| `Int.is_space(self) -> Bool` | exactly `' '`, `'\t'`, `'\n'`, `'\r'` (not vertical tab or form feed) |
| `Float.to_int(self) -> Int` | truncates toward zero (`(-1.9).to_int() == -1`); `nan`, `inf` and values outside `Int` trap |
| `Float.sqrt(self) -> Float` | the square root; `nan` for a negative number |
| `Float.floor(self) -> Float` | the largest whole number not above it (still a `Float`) |
| `Float.ceil(self) -> Float` | the smallest whole number not below it (still a `Float`) |
| `Float.round(self) -> Float` | the nearest whole number, halves away from zero: `2.5.round() == 3.0`, `(-0.5).round() == -1.0` |
| `Float.to_fixed(self, decimals: Int) -> Str` | exactly `decimals` digits after the point, rounding the binary value half to even like printf: `2.5.to_fixed(0) == "2"`, `2.675.to_fixed(2) == "2.67"` |
| `Float.abs(self) -> Float` | the absolute value |
| `Float.min(self, o: Float) -> Float` | the smaller of the two |
| `Float.max(self, o: Float) -> Float` | the larger of the two |

#### Str (lib/prelude.tn)

| Signature | Behaviour |
|---|---|
| `Str.len(self) -> Int` | the length in bytes (UTF-8): `"Zürich".len() == 7` |
| `Str.byte(self, i: Int) -> Int` | the byte at offset `i` (0-255); `i` outside `0..len()` traps |
| `Str.slice(self, start: Int, end: Int) -> Str` | the bytes `start..end` (half-open), sharing the original's bytes; traps if `start > end`, `end > len()`, or an end falls inside a multi-byte character (`"é".slice(0, 1)`: `slice [0, 1) is not on a character boundary`) |
| `Str.find(self, sub: Str) -> Option[Int]` | the byte offset of the first match, `None` if absent; `s.find("") == Some(0)` |
| `Str.find_from(self, sub: Str, start: Int) -> Option[Int]` | the first match at or after byte `start`, `None` if absent; `start == len()` is allowed, `start` outside `0..len()` traps |
| `Str.split(self, sep: Str) -> List[Str]` | the pieces between the separators, empty ones kept: `"a,,b,".split(",") == ["a", "", "b", ""]`, `"".split(",") == [""]`; an empty `sep` traps |
| `Str.trim(self) -> Str` | without leading and trailing `' '`, `'\t'`, `'\n'`, `'\r'` and form feed (not vertical tab) |
| `Str.trim_start(self) -> Str` | `trim` at the start only |
| `Str.trim_end(self) -> Str` | `trim` at the end only |
| `Str.starts_with(self, prefix: Str) -> Bool` | true if `self` begins with `prefix` (always for `""`) |
| `Str.ends_with(self, suffix: Str) -> Bool` | true if `self` ends with `suffix` (always for `""`) |
| `Str.to_int(self) -> Option[Int]` | decimal digits with an optional `+` or `-`: `"+5"` is `Some(5)`, `"-0"` `Some(0)`; `None` for `""`, spaces, `_`, other characters and overflow |
| `Str.to_int_radix(self, base: Int) -> Option[Int]` | digits of `base` 2-36 (letters in either case) with an optional `-` (no `+`, no `0x`): `"ff".to_int_radix(16) == Some(255)`; `None` if invalid or out of range; another base traps |
| `Str.to_float(self) -> Option[Float]` | a decimal or exponent number (`1.5`, `.5`, `5.`, `1e-3`), `inf` or `nan`, with an optional sign; `None` otherwise (also with spaces) |
| `Str.upper(self) -> Str` | ASCII letters upper-cased; other characters unchanged (`"é".upper() == "é"`) |
| `Str.lower(self) -> Str` | ASCII letters lower-cased; other characters unchanged |
| `Str.replace(self, from: Str, to: Str) -> Str` | every non-overlapping match of `from`, left to right, replaced by `to`; an empty `from` traps |
| `Str.chars(self) -> List[Str]` | the code points, each as a one-character string: `"Zü".chars() == ["Z", "ü"]`, `"".chars() == []` |
| `Str.char_count(self) -> Int` | the number of code points: `"Zürich".char_count() == 6` |
| `Str.bytes(self) -> List[Int]` | the UTF-8 encoding, one `Int` 0-255 per byte |
| `Str.from_utf8(bytes: List[Int]) -> Option[Str]` | the text, or `None` if the bytes are not valid UTF-8 (overlong forms, surrogates, above U+10FFFF, truncated) or an element is outside 0-255 |
| `Str.from_utf8_lossy(bytes: List[Int]) -> Str` | the text, each maximal invalid sequence replaced by U+FFFD; an element outside 0-255 traps |
| `Str.is_empty(self) -> Bool` | `len() == 0` |
| `Str.is_digits(self) -> Bool` | true if non-empty and every byte is an ASCII digit: `"007"` is true; `""`, `"-1"`, `"+1"`, `"1.5"` and non-ASCII digits are false |
| `Str.strip_prefix(self, p: Str) -> Option[Str]` | the rest after `p`, `None` if `self` does not start with it (`Some(self)` for `p == ""`) |
| `Str.strip_suffix(self, p: Str) -> Option[Str]` | the part before `p`, `None` if `self` does not end with it |
| `Str.trim_chars(self, chars: Str) -> Str` | without the leading and trailing bytes that occur in `chars`; only ASCII bytes count: `"0250".trim_chars("0") == "25"`, `"xéx".trim_chars("x") == "é"` |
| `Str.trim_start_chars(self, chars: Str) -> Str` | `trim_chars` at the start only |
| `Str.trim_end_chars(self, chars: Str) -> Str` | `trim_chars` at the end only: `"0250".trim_end_chars("0") == "025"` |
| `Str.contains(self, sub: Str) -> Bool` | true if `sub` occurs (always for `""`) |
| `Str.all_bytes(self, pred: fn(Int) -> Bool) -> Bool` | true if `pred` holds for every byte, and for `""` |
| `Str.rfind(self, sub: Str) -> Option[Int]` | the byte offset of the last match, `None` if absent; `s.rfind("") == Some(s.len())` |
| `Str.split_once(self, sep: Str) -> Option[(Str, Str)]` | the parts before and after the first `sep`: `"k=v=w".split_once("=") == Some(("k", "v=w"))`; `None` if absent |
| `Str.rsplit_once(self, sep: Str) -> Option[(Str, Str)]` | the parts before and after the last `sep`; `None` if absent |
| `Str.lines(self) -> List[Str]` | the lines as `Console.read_line` reads them: split on `"\n"`, a final empty piece dropped, one trailing `"\r"` removed from each: `"".lines() == []`, `"\n".lines() == [""]`, `"a\r\nb".lines() == ["a", "b"]` |
| `Str.words(self) -> List[Str]` | the pieces between runs of spaces, tabs, `"\r"` and `"\n"`; no empty pieces (`"".words() == []`) |
| `Str.repeat(self, n: Int) -> Str` | `n` copies joined; `""` for `n <= 0` |
| `Str.pad_left(self, width: Int, fill: Str) -> Str` | `fill` added in front until `width` code points; a longer string is returned unchanged; `fill` must be one code point, else a trap (even when no padding is needed) |
| `Str.pad_right(self, width: Int, fill: Str) -> Str` | `fill` added at the end until `width` code points: `"Zürich".pad_right(8, ".") == "Zürich.."`; same rules as `pad_left` |

#### List (lib/prelude.tn)

| Signature | Behaviour |
|---|---|
| `List[T].len(self) -> Int` | the number of elements |
| `List[T].push(mut self, x: T)` | appends `x` (amortized O(1)) |
| `List[T].pop(mut self) -> Option[T]` | removes and returns the last element, `None` if empty (discard with `let _ =`) |
| `List[T].insert(mut self, i: Int, x: T)` | puts `x` at index `i`, shifting the rest right; `i == len()` appends; `i` outside `0..len()` traps; O(n) |
| `List[T].remove(mut self, i: Int) -> T` | removes the element at `i` and **returns it** (not an `Option`: discard with `let _ =`); `i` outside `0..len() - 1` traps; O(n), so `remove(0)` on a long queue is slow |
| `List[T].clear(mut self)` | removes every element |
| `List[T].slice(self, start: Int, end: Int) -> List[T]` | a new list of the elements `start..end` (half-open); `start > end` or `end > len()` traps |
| `List[T].sort(mut self)` | sorts ascending by the derived ordering (stable merge sort, O(n log n)) |
| `List[T].sort_by[K](mut self, key: fn(T) -> K)` | sorts by `key(x)` ascending, stable; for descending use a negated key or `sort_by_desc` |
| `List[T].sort_by_desc[K](mut self, key: fn(T) -> K)` | sorts by `key(x)` descending; stable (equal keys keep their order) |
| `List[T].reverse(mut self)` | reverses in place (needs a `var`; `reversed` returns a copy) |
| `List[Str].join(self, sep: Str) -> Str` | the strings with `sep` between them; `""` for an empty list |
| `List[T].is_empty(self) -> Bool` | `len() == 0` |
| `List[T].enumerate(self) -> List[(Int, T)]` | `[(0, a), (1, b), ...]`: `for (i, x) in xs.enumerate()` |
| `List[T].filled(n: Int, x: T) -> List[T]` | `n` copies of `x` (`List.filled(3, 0)`); `[]` for `n <= 0` |
| `List[T].swap(mut self, i: Int, j: Int)` | exchanges the elements at `i` and `j`; an index out of range traps |
| `List[T].sort_with(mut self, cmp: fn(T, T) -> Int)` | sorts stably by a comparison: `cmp(a, b) < 0` puts `a` first |
| `List[T].get(self, i: Int) -> Option[T]` | `Some(xs[i])`, `None` if `i` is out of range (also negative) |
| `List[T].first(self) -> Option[T]` | the first element, `None` if empty |
| `List[T].last(self) -> Option[T]` | the last element, `None` if empty |
| `List[T].index_of(self, x: T) -> Option[Int]` | the index of the first element equal to `x`, `None` if absent; O(n) |
| `List[T].contains(self, x: T) -> Bool` | true if an element equals `x`; O(n) |
| `List[T].binary_search(self, x: T) -> Result[Int, Int]` | on a list sorted ascending: `Ok(i)`, the first index of `x`, or `Err(i)`, where `insert(i, x)` keeps it sorted: `[1, 3, 5].binary_search(4) == Err(2)`; O(log n) |
| `List[T].extend(mut self, other: List[T])` | appends every element of `other` |
| `List[T].sorted(self) -> List[T]` | a sorted copy (`sort` on a copy) |
| `List[T].reversed(self) -> List[T]` | a reversed copy |
| `List[T].map[U](self, f: fn(T) -> U) -> List[U]` | `[f(x) for each x]`, in order |
| `List[T].filter(self, keep: fn(T) -> Bool) -> List[T]` | the elements for which `keep` is true, in order |
| `List[T].retain(mut self, keep: fn(T) -> Bool)` | keeps, in place and in order, the elements for which `keep` is true (`filter` on a `var`, also a deep place) |
| `List[T].any(self, pred: fn(T) -> Bool) -> Bool` | true if `pred` holds for some element (false for `[]`); stops at the first |
| `List[T].all(self, pred: fn(T) -> Bool) -> Bool` | true if `pred` holds for every element (true for `[]`); stops at the first failure |
| `List[T].count(self, pred: fn(T) -> Bool) -> Int` | the number of elements for which `pred` holds |
| `List[T].max_by[K](self, key: fn(T) -> K) -> Option[T]` | the element with the largest `key`, the first of equal ones; `None` for `[]` |
| `List[T].min_by[K](self, key: fn(T) -> K) -> Option[T]` | the element with the smallest `key`, the first of equal ones; `None` for `[]` |
| `List[T].group_by[K](self, key: fn(T) -> K) -> Map[K, List[T]]` | every element by `key`: keys in order of first occurrence, each group in list order; equal keys need not be adjacent |
| `rev_range(lo: Int, hi: Int) -> List[Int]` | `lo..hi` counting down: `rev_range(0, 3) == [2, 1, 0]`; `[]` if `hi <= lo`; in a C build `for i in rev_range(..)` builds no list |
| `List[Int].sum(self) -> Int` | the sum (0 for `[]`); overflow traps |

#### Map (lib/prelude.tn)

| Signature | Behaviour |
|---|---|
| `Map[K, V].len(self) -> Int` | the number of entries |
| `Map[K, V].get(self, k: K) -> Option[V]` | the value at `k`, `None` if absent (`m[k]` traps instead) |
| `Map[K, V].insert(mut self, k: K, v: V)` | sets `k` to `v` (same as `m[k] = v`); a new key goes last, an existing one keeps its place |
| `Map[K, V].remove(mut self, k: K) -> Option[V]` | removes `k` and returns its value, `None` if absent (discard with `let _ =`); the others keep their order |
| `Map[K, V].keys(self) -> List[K]` | the keys in insertion order |
| `Map[K, V].values(self) -> List[V]` | the values in insertion order |
| `Map[K, V].is_empty(self) -> Bool` | `len() == 0` |
| `Map[K, V].contains(self, k: K) -> Bool` | true if `k` has an entry |
| `Map[K, V].get_or(self, k: K, default: V) -> V` | the value at `k`, or `default` if absent |
| `Map[K, V].or_insert(mut self, k: K, v: V)` | inserts `v` only if `k` is absent: `m.or_insert(k, []); m[k].push(x)` |
| `Map[K, V].update(mut self, k: K, default: V, f: fn(V) -> V)` | stores `f` of the value at `k` (or of `default` if absent): `m.update(w, 0, fn(n) => n + 1)` |
| `Map[K, V].entries(self) -> List[(K, V)]` | the `(key, value)` pairs in insertion order (`for (k, v) in m` iterates the same) |

#### Set (lib/prelude.tn)

| Signature | Behaviour |
|---|---|
| `struct Set[T] { items_: Map[T, Unit] }` | a hash set; iteration (`items()`) follows insertion order; build with `Set.new()` or `Set.of(xs)` |
| `Set[T].new() -> Set[T]` | an empty set (annotate the type: `var s: Set[Str] = Set.new()`) |
| `Set[T].of(xs: List[T]) -> Set[T]` | the distinct elements of `xs`, in first-occurrence order |
| `Set[T].insert(mut self, x: T) -> Bool` | adds `x`; false if it was already present |
| `Set[T].remove(mut self, x: T) -> Bool` | removes `x`; false if it was absent |
| `Set[T].contains(self, x: T) -> Bool` | true if `x` is present; O(1) on average |
| `Set[T].len(self) -> Int` | the number of elements |
| `Set[T].is_empty(self) -> Bool` | `len() == 0` |
| `Set[T].items(self) -> List[T]` | the elements in insertion order (a set is not iterable itself) |

#### Heap (lib/prelude.tn)

| Signature | Behaviour |
|---|---|
| `struct Heap[T] { items_: List[T] }` | a priority queue (binary heap): `pop` gives the smallest by the derived ordering; push `(-priority, item)` for largest first |
| `Heap[T].new() -> Heap[T]` | an empty heap (annotate the type) |
| `Heap[T].len(self) -> Int` | the number of items |
| `Heap[T].is_empty(self) -> Bool` | `len() == 0` |
| `Heap[T].peek(self) -> Option[T]` | the smallest item without removing it, `None` if empty |
| `Heap[T].push(mut self, x: T)` | adds `x`; O(log n) |
| `Heap[T].pop(mut self) -> Option[T]` | removes and returns the smallest item, `None` if empty; O(log n) |

#### Option / Result (lib/prelude.tn)

| Signature | Behaviour |
|---|---|
| `Option[T].unwrap(self) -> T` | the value; traps on `None` |
| `Option[T].expect(self, msg: Str) -> T` | the value; traps with `msg` on `None` |
| `Option[T].is_some(self) -> Bool` | true for `Some` |
| `Option[T].is_none(self) -> Bool` | true for `None` |
| `Option[T].unwrap_or(self, default: T) -> T` | the value, or `default` for `None` (`default` is evaluated either way) |
| `Option[T].ok_or[E](self, err: E) -> Result[T, E]` | `Ok(x)` for `Some(x)`, `Err(err)` for `None` |
| `Option[T].map[U](self, f: fn(T) -> U) -> Option[U]` | `Some(f(x))`, `None` stays `None` |
| `Option[T].and_then[U](self, f: fn(T) -> Option[U]) -> Option[U]` | `f(x)` for `Some(x)`, `None` stays `None` |
| `Option[T].map_or[U](self, default: U, f: fn(T) -> U) -> U` | `f(x)` for `Some(x)`, `default` for `None` |
| `Option[T].filter(self, keep: fn(T) -> Bool) -> Option[T]` | `Some(x)` if `keep(x)`, otherwise `None` |
| `Option[T].is_some_and(self, pred: fn(T) -> Bool) -> Bool` | true for `Some(x)` with `pred(x)` |
| `Result[T, E].unwrap(self) -> T` | the value; traps on `Err(e)`, showing `e` |
| `Result[T, E].expect(self, msg: Str) -> T` | the value; traps with `msg` and `e` on `Err(e)` |
| `Result[T, E].is_ok(self) -> Bool` | true for `Ok` |
| `Result[T, E].is_err(self) -> Bool` | true for `Err` |
| `Result[T, E].ok(self) -> Option[T]` | `Some(x)` for `Ok(x)`, `None` for `Err` |
| `Result[T, E].unwrap_or(self, default: T) -> T` | the value, or `default` for `Err` |
| `Result[T, E].map_err[F](self, f: fn(E) -> F) -> Result[T, F]` | changes the error: `Err(f(e))`; for `?` across error types: `r.map_err(fn(e) => "{e}")?` |
| `Result[T, E].err(self) -> Option[E]` | `Some(e)` for `Err(e)`, `None` for `Ok` |
| `Result[T, E].map[U](self, f: fn(T) -> U) -> Result[U, E]` | `Ok(f(x))`, the error unchanged |
| `Result[T, E].and_then[U](self, f: fn(T) -> Result[U, E]) -> Result[U, E]` | `f(x)` for `Ok(x)` (the same error type), `Err(e)` unchanged |
| `Result[T, E].map_or[U](self, default: U, f: fn(T) -> U) -> U` | `f(x)` for `Ok(x)`, `default` for `Err` |
| `Result[T, E].is_ok_and(self, pred: fn(T) -> Bool) -> Bool` | true for `Ok(x)` with `pred(x)` |
| `Result[T, E].is_err_and(self, pred: fn(E) -> Bool) -> Bool` | true for `Err(e)` with `pred(e)` |

#### Capabilities (lib/prelude.tn)

| Signature | Behaviour |
|---|---|
| `Console.print(self, s: Str)` | writes `s` to standard output (buffered; no newline) |
| `Console.println(self, s: Str)` | writes `s` and `"\n"` to standard output (buffered: `flush()` when another process waits for the answer) |
| `Console.eprintln(self, s: Str)` | writes `s` and `"\n"` to standard error (unbuffered), after flushing standard output |
| `Console.read_line(self) -> Option[Str]` | the next line of standard input without its `"\n"` and one trailing `"\r"`, `None` at end of input; invalid UTF-8 becomes U+FFFD |
| `Console.read_all(self) -> Str` | the rest of standard input as text, every `"\r"` kept; invalid UTF-8 becomes U+FFFD |
| `Console.read_all_bytes(self) -> List[Int]` | the rest of standard input, byte for byte |
| `Console.write_bytes(self, data: List[Int])` | writes the bytes to standard output; an element outside 0-255 traps |
| `Console.flush(self)` | flushes standard output (also done before any blocking read and at exit) |
| `Console.read_bytes(self, n: Int) -> List[Int]` | the next `n` bytes of standard input, waiting for them; fewer only at the end (`[]` there, and for `n <= 0`) |
| `Fs.read(self, path: Str) -> Result[Str, IoError]` | the file as text; `Err(Failed("path: invalid UTF-8"))` if it is not UTF-8, `Err(NotFound(path))` if missing, `Failed` for a directory |
| `Fs.write(self, path: Str, data: Str) -> Result[Unit, IoError]` | replaces the file atomically and durably: writes `path + ".tmp"`, fsyncs, renames it over `path` (see "Writing files") |
| `Fs.append(self, path: Str, data: Str) -> Result[Unit, IoError]` | appends to the file (creating it), durably (fsync) before it returns; not atomic |
| `Fs.read_bytes(self, path: Str) -> Result[List[Int], IoError]` | the file as bytes, any content |
| `Fs.write_bytes(self, path: Str, data: List[Int]) -> Result[Unit, IoError]` | `write` for bytes (atomic, via `path + ".tmp"`); an element outside 0-255 traps before any file is touched |
| `Fs.append_bytes(self, path: Str, data: List[Int]) -> Result[Unit, IoError]` | `append` for bytes |
| `Fs.truncate(self, path: Str, len: Int) -> Result[Unit, IoError]` | cuts an existing file to its first `len` bytes, durably, in place (not atomic); never extends or creates: `NotFound` if missing, `Failed` for `len < 0`, `len` beyond the end, or a directory |
| `Fs.exists(self, path: Str) -> Bool` | true if `path` names a file or directory (a `Bool`, not a `Result`: also false for a path this `Fs` cannot reach, such as `..` on an attenuated one) |
| `Fs.remove(self, path: Str) -> Result[Unit, IoError]` | deletes a file or an empty directory |
| `Fs.list(self, dir: Str) -> Result[List[Str], IoError]` | the entry names (not paths) in `dir`, without `.` and `..`, sorted by bytes |
| `Fs.mkdir(self, path: Str) -> Result[Unit, IoError]` | creates the directory and any missing parents; succeeds if it exists |
| `Fs.mkdir_one(self, path: Str) -> Result[Unit, IoError]` | creates exactly one directory: `NotFound` if the parent is missing, `Failed("path: File exists")` if `path` exists (an exclusive claim) |
| `Fs.rename(self, from: Str, to: Str) -> Result[Unit, IoError]` | moves `from` to `to` atomically, replacing `to` |
| `Fs.is_dir(self, path: Str) -> Bool` | true if `path` is a directory |
| `Fs.within(self, dir: Str) -> Fs` | an `Fs` rooted at `dir`: it rejects absolute paths, `..` and symbolic links (`Denied`) |
| `Fs.read_only(self) -> Fs` | the same `Fs` without write authority (every write is `Denied`) |
| `path_join(a: Str, b: Str) -> Str` | `a/b` with one `/`: `path_join("a/", "b") == "a/b"`; an absolute `b` wins; an empty part gives the other; lexical |
| `path_parent(p: Str) -> Str` | the path without its last component: `path_parent("a/b/") == "a"`, `path_parent("a") == "."`, `path_parent("/") == "/"`; `..` is not resolved |
| `path_base(p: Str) -> Str` | the last component: `path_base("a/b/") == "b"`, `path_base("/") == "/"`, `path_base("") == ""` |
| `Net.listen(self, port: Int) -> Result[Listener, IoError]` | a `Listener` on 127.0.0.1 at `port` (0: any free port, see `port()`) |
| `Net.connect(self, host: Str, port: Int) -> Result[Conn, IoError]` | a `Conn` to `host:port` |
| `Listener.port(self) -> Int` | the port it listens on |
| `Listener.accept(self) -> Result[Conn, IoError]` | waits for the next connection (standard output is flushed first) |
| `Conn.read_line(self) -> Result[Option[Str], IoError]` | the next line without `"\n"` and one trailing `"\r"`, `Ok(None)` at end of stream |
| `Conn.read(self, n: Int) -> Result[Str, IoError]` | up to `n` bytes as text, fewer only at the end of the stream |
| `Conn.write(self, s: Str) -> Result[Unit, IoError]` | writes all of `s` |
| `enum NetEvent { Accepted(Int, Int), Data(Int, Str), Closed(Int), Timeout }` | what `Poller.wait` reports: `Accepted(listener, conn)`, `Data(conn, text)`, `Closed(conn)`, `Timeout` |
| `Net.poller(self) -> Poller` | a new event loop (a unique handle, reference §15) |
| `Poller.listen(self, port: Int) -> Result[Int, IoError]` | listens on `port`; gives the listener's id |
| `Poller.connect(self, host: Str, port: Int) -> Result[Int, IoError]` | connects to `host:port`; gives the connection's id |
| `Poller.port(self, id: Int) -> Int` | the port of listener `id` |
| `Poller.wait(self, timeout_ms: Int) -> List[NetEvent]` | waits up to `timeout_ms` (-1: no timeout) and gives the events in increasing id order, accepting new connections itself; invalid UTF-8 in `Data` becomes U+FFFD |
| `Poller.send(self, id: Int, data: Str) -> Result[Unit, IoError]` | writes all of `data` to connection `id` (may block on a slow peer) |
| `Poller.close(self, id: Int)` | closes connection or listener `id` |
| `Clock.now_ms(self) -> Int` | milliseconds since 1970-01-01 UTC (wall clock; may jump) |
| `Clock.mono_ns(self) -> Int` | a monotonic clock in nanoseconds, for measuring durations |
| `Clock.sleep_ms(self, ms: Int)` | waits `ms` milliseconds (standard output is flushed first) |
| `Proc.run(self, cmd: Str, args: List[Str]) -> Result[Int, IoError]` | runs `cmd` (looked up in `PATH` unless it has a `/`) with `args`, no shell, sharing the console; waits and gives its exit status; `NotFound(cmd)`, `Denied(cmd)` or `Failed("cmd: ...")` (also when killed by a signal) |
| `Proc.env(self, name: Str) -> Option[Str]` | the environment variable, `None` if unset or if `name` is empty or has `=` or a NUL byte |
| `struct ProcOut { pub status: Int, pub signal: Int, pub timed_out: Bool, pub out: List[Int], pub err: List[Int] }` | what `run_with` captured: `status` (-1 if ended by a signal), `signal`, `timed_out`, `out` and `err` as bytes |
| `Proc.run_with(self, cmd: Str, args: List[Str], dir: Str, input: List[Int], timeout_ms: Int) -> Result[ProcOut, IoError]` | runs `cmd` in `dir` (`""`: the current one) with `input` as standard input, capturing its output; `timeout_ms > 0` kills its whole process group after that long (`timed_out`) |
| `Proc.run_capture(self, cmd: Str, args: List[Str], dir: Str, input: List[Int], timeout_ms: Int) -> Result[List[Int], IoError]` | the packed form behind `run_with` (`[status, signal, timed_out, len(out), out..., err...]`); use `run_with` |
| `Proc.exit(self, status: Int)` | ends the program now with `status` 0-255 (reserved codes allowed), after flushing standard output; outside 0-255 traps |

#### Traits (lib/v2/prelude.tn)

| Signature | Behaviour |
|---|---|
| `trait Eq {}` | derived: types without functions, capabilities or `dyn` values; `==` and `!=` (reference §17) |
| `trait Ord {}` | derived: `Eq` types without maps; `<`, `sort` (reference §17) |
| `trait Hash {}` | derived: `Eq` types without `Float`; usable as a map key or set element (reference §17) |
| `trait Show` | `to_str()` and formatting; derived for types without functions or capabilities, and the only trait a type can implement (`impl Show for T`) |

#### Workers and channels (lib/v2/prelude.tn)

| Signature | Behaviour |
|---|---|
| `trait Send {}` | derived: the types that can go to another worker (not linear types, `Poller`, `Listener`, `Conn`) |
| `Sys.workers(self) -> Workers` | the authority to start workers (reference §18) |
| `Workers.spawn[A: Send, R: Send](self, f: fn(A) -> R, arg: A) -> Worker[R]` | runs `f(arg)` on a new thread with its own heap; the argument and result are copied; a trap there ends the program |
| `Workers.cores(self) -> Int` | the number of cores available |
| `Worker[R].join(self) -> R` | waits for the worker and gives (a copy of) its result; may be called again |
| `channel[T: Send]() -> (Sender[T], Receiver[T])` | a new unbounded channel, any number of senders and receivers; each value is received once |
| `Sender[T].send(self, x: T)` | sends a copy of `x` (a unique value is moved); never waits; traps on a closed channel |
| `Sender[T].close(self)` | closes the channel: receivers get what is left, then `None`; dropping the senders does not close it |
| `Receiver[T].recv(self) -> Option[T]` | the next value, waiting for one; `None` once closed and empty; traps with `deadlock` if nobody can send or close |
| `Receiver[T].try_recv(self) -> Option[T]` | the next value if one is there now, else `None`; never waits |
| `Workers.par_map[T: Send, U: Send](self, xs: List[T], f: fn(T) -> U) -> List[U]` | `xs.map(f)` computed by up to `cores()` workers, same order |
| `Workers.par_map_n[T: Send, U: Send](self, n: Int, xs: List[T], f: fn(T) -> U) -> List[U]` | `par_map` with at most `n` workers (`n <= 1`: plain `map`) |
| `map_chunks[T, U](todo: Receiver[(Int, List[T])], done: Sender[(Int, List[U])], f: fn(T) -> U)` | the worker loop of `par_map_n` (not meant to be called directly) |

<!-- prelude-table: end -->
