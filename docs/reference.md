# Tenon language reference

This is the single source document for the language. Together with the one-page
docs/quickstart.md (a translation table from Python and TypeScript) it is the
only documentation given to authors in the usability study, so it must be
enough to write real programs. Builtin APIs are listed in the prelude (`src/prelude.tn` in the repository; `docs/prelude.tn` in a study kit),
which is ordinary Tenon source and the single source of the builtin API.

Every claim here is checked by a test in `tests/` (run `./check`).

## 1. A first program

```tenon
fn main(sys: Sys) -> Result[Unit, Str] {
    let con = sys.console
    var counts: Map[Str, Int] = [:]
    for word in con.read_all().words() {
        counts[word] = counts.get_or(word, 0) + 1
    }
    for (w, n) in counts {
        con.println("{w}: {n}")
    }
    Ok(())
}
```

Run it with the reference interpreter (`tenon run prog.tn`) or compile it to a
native executable through C (`tenon build prog.tn -o prog`). Both must behave
identically; the test suite checks this for every test program.

## 2. Lexical structure

- Comments: `// to end of line`.
- Statements end at a newline (or `;`). A line that begins with `.`, `else`,
  `and`, `or` or a binary operator other than `-` (`+ * / % == != < <= > >=`)
  continues the previous line, and so does anything inside `( )` or `[ ]`.
- Names: types and enum variants start with an uppercase letter; functions,
  variables and fields start with a lowercase letter. The compiler enforces this.
- Literals: `42`, `1_000`, `3.14`, `1e-9`, `true`, `false`, `"text"`, integers
  in hex `0xFF`, binary `0b1010` and octal `0o17` (lowercase prefix, digits in
  either case; `_` separators allowed in any integer: `0xFF_FF`), and
  character literals `'a'`, `'\n'`, `'\''`, `'é'`, which are the character's
  code point as an `Int` (`'a'` is `97`; compare with `s.byte(i)`).
  Escapes: `\n \t \r \0 \\ \" \{ \}`. `"{expr}"` interpolates any value (see §8); write `\{` for a literal `{` (a lone `}` is literal).
- `()` is the only value of type `Unit`.

## 3. Types

| Type | Meaning |
|---|---|
| `Int` | 64-bit signed integer. Overflow **traps**. `/` and `%` truncate toward zero (`-7 / 2 == -3`, `-7 % 2 == -1`); dividing by zero traps. |
| `Float` | 64-bit IEEE float. |
| `Bool` | `true` / `false`. |
| `Str` | Immutable UTF-8 text. Offsets are byte offsets. |
| `Unit` | No information; written `()`. |
| `List[T]` | Growable sequence with value semantics. |
| `Map[K, V]` | Hash map; iteration follows insertion order. |
| `(A, B, ...)` | Tuple; fields `.0`, `.1`, ... |
| `fn(A, B) -> R` | Function value (named function or closure). |
| `Option[T]` | `Some(T)` or `None`. There is no null. |
| `Result[T, E]` | `Ok(T)` or `Err(E)`. |
| `Console`, `Fs`, `Clock` | Capabilities (§10). |

There is **no implicit conversion** of any kind: `1 + 2.0` is a type error;
write `1.to_float() + 2.0`.

### Value semantics

Every value behaves as if it were copied on assignment. Lists and maps are
shared until one copy is modified (copy-on-write), so copying is cheap:

```tenon
var a = [1, 2]
let b = a
a.push(3)      // b is still [1, 2]
```

### Performance model

- Copying a value (`let b = a`, passing an argument, returning) never copies
  a list, map or string: it shares it and bumps a reference count. A copy is
  made only when a shared value is changed (copy-on-write).
- Changing a value in place through a `var` is cheap, also deep inside it:
  `self.sides[i].levels[p].qty -= n`, `m[k].push(x)`. Copying a part out,
  changing it, and writing it back (`var g = m[k]; g.x += 1; m[k] = g`) is
  also correct, but costs a copy of the part while two references exist.
- `s += t` on a `var` string appends in place (amortized O(1)); building a
  string piece by piece is fine. `slice`, `split`, `lines` and `words` return
  views that share the original's bytes.
- `a + b` makes a new string. When nested functions each return a string
  that the caller appends (`out += esc(x)`), every level copies its output
  once more; passing one buffer down (`fn esc(out: mut Str, s: Str)`, called
  as `esc(mut out, x)`) writes each byte once.
- `Map` and `Set` lookups and inserts are O(1) on average; small maps (up to
  8 entries) are scanned. `m[k] = m.get_or(k, 0) + 1` is compiled to a single
  lookup. Iteration follows insertion order.
- `List.push`/`pop` are amortized O(1); `insert`/`remove` at the front are O(n).
  `sort`/`sort_by` are stable O(n log n) merge sorts.
- For dense integer keys `0..n`, index a `List` (`List.filled(n, x)`, or
  `List[Option[V]]` for "not computed yet") instead of a `Map[Int, V]`: a map
  hashes on every access. Measured with the C backend, filling and reading
  2,500 keys is about 5x faster with a list, 1,000,000 keys about 20x; in the
  interpreter about 2.5x.
- A `mut` argument that is a field of a value which is also passed by value
  (`self.value(i, mut self.memo)`) is legal, but the callee's copy of `self`
  still references the field, so the first change through the `mut` argument
  copies it, on every call. Move the field out first and put it back after:
  `var memo = self.memo; self.memo = []; ... self.value(i, mut memo) ...; self.memo = memo`.
- Integers are 64-bit machine integers with an overflow check; structs,
  tuples and non-recursive enums are stored inline, without allocation.

## 4. Declarations

```tenon
struct Point { x: Int, y: Int }
struct Pair[A, B] { first: A, second: B }

enum Shape { Circle(Int), Rect(Int, Int), Empty }
enum Tree[T] { Leaf, Node(Tree[T], T, Tree[T]) }   // recursion through enums is fine

fn area(s: Shape) -> Int { ... }                    // return type Unit if omitted
fn largest[T](xs: List[T]) -> Option[T] { ... }      // generic function

const MAX_USERS: Int = 1000                          // constant: capitals; any expression
fn Point.origin() -> Point { Point { x: 0, y: 0 } }  // associated function: Point.origin()
fn Point.norm1(self) -> Int { self.x.abs() + self.y.abs() }   // method: p.norm1()
fn Point.shift(mut self, d: Int) { self.x += d }     // mutating method: needs a `var` receiver
fn Pair[A, B].swap(self) -> Pair[B, A] { ... }       // methods on generic types
fn List[Int].total(self) -> Int { ... }              // methods for specific instantiations
```

- A struct may not contain itself directly; use an enum or a `List`.
- Variants are used unqualified (`Circle(3)`) unless two enums share a variant
  name, then qualify: `Shape.Circle(3)`.
- Every type automatically supports `==`, `!=`, ordering (`<` ...; maps are
  not ordered), hashing (usable as a map key), and `to_str()`. Functions and
  capabilities cannot be compared.
- Derived ordering: numbers numerically; `false < true`; strings by bytes
  (so `"B" < "a"`); lists and tuples lexicographically, element by element;
  structs field by field in declaration order; enums by variant declaration
  order, then payload. `sort` and `sort_by` are stable. For descending order
  sort by a negated key (`xs.sort_by(fn(p) => (-p.score, p.name))`).
- Struct update: `Point { x: 3, ..p }` copies the other fields from `p`
  (the `..base` part comes last).

## 5. Functions and closures

The last expression of a block is its value. `return` exits early.

```tenon
fn fib(n: Int) -> Int { if n < 2 { n } else { fib(n - 1) + fib(n - 2) } }

let add = fn(a: Int, b: Int) -> Int { a + b }   // closure, full form
let inc = fn(x) => x + 1                         // short form; types inferred from use
let names = people.map(fn(p) => p.name)
```

Closures capture variables **by value** at creation; they cannot assign to
captured variables. Inside a method a closure may use `self`: it captures a copy
of `self` as it is when the closure is created (also in a `mut self` method;
later changes are not seen by the closure). A parameter named `_` is ignored
(`xs.map(fn(_) => 0)`).

Functions and methods may be used before their definition, and may be
mutually recursive.

Generic functions are compiled once per type they are used with, so a
function that calls itself at ever larger types (`f([x])` inside `f`) runs in
the interpreter but is rejected by `tenon build`. Named functions and variants can be used as values:
`xs.map(Some)`, `words.map(Str.len)`.

## 6. Variables and mutation

- `let x = ...` is immutable; `var x = ...` is mutable. Types are inferred;
  annotate with `let x: List[Int] = []` when needed.
- Names may not be redeclared inside a function (no shadowing). This includes
  parameters and names bound by patterns: `let v = f()` followed by
  `match v { Some(v) => ... }` is rejected; use another name (`Some(x)`).
- A file may define its own item with a prelude name (`path_join`, `Result`,
  ...); it hides the prelude's in that file only (§13).
- Assignment targets: `x = v`, `p.field = v`, `xs[i] = v`, `m[k] = v`
  (inserts or replaces), and compound forms `+= -= *= /= %=`. Evaluation
  order: the target's index expressions, then the right-hand side, then (for
  compound forms) the target's current value is read.
- Mutating methods (`push`, `insert`, `sort`, user methods with `mut self`)
  need a mutable place: a `var`, or a field/element of one, including map
  entries: `m[k].push(x)` and `m[k] += 1` update the entry in place (the key
  must exist; `m[k] = v` inserts).
- Function parameters are immutable, except `mut` parameters: the caller
  passes a place marked `mut`, and the function's changes are visible to the
  caller after the call. Two `mut` arguments cannot refer to the same variable.

  ```tenon
  fn visit(node: Str, path: mut List[Str]) { path.push(node) }
  visit("a", mut path)
  ```

## 7. Control flow

```tenon
if a > b { ... } else if a == b { ... } else { ... }   // also an expression
while cond { ... }
for i in 0..n { ... }            // half-open range
for x in xs { ... }              // over a snapshot of the list
for (k, v) in m { ... }          // over map entries in insertion order
for x in set.items() { ... }     // a Set is not iterable itself
break; continue; return value
```

`match` must be exhaustive, and an arm that can never match is an error:

```tenon
match shape {
    Circle(r) if r > 100 => "big circle",
    Circle(_) => "circle",
    Rect(w, h) | ... => ...,
    _ => "other",
}
```

`if let` runs a block when a value matches a pattern; the pattern's names are
visible only in that block. It is an expression like `if`, and chains with
`else if` / `else if let`. `while let` loops while the pattern matches
(`break`/`continue` work as in `while`; it always can finish). Any `match`
pattern works, including `|` and patterns that always match:

```tenon
if let Some(rest) = line.strip_prefix("push ") { push(rest) }
else if let Some(n) = line.to_int() { use(n) } else { skip() }
while let Some(job) = queue.pop() { run(job) }
```

`if let P = e { a } else { b }` means `match e { P => a, _ => b }`, so a linear
value cannot be the matched value (the `else` path would drop it).

`let ... else` unwraps or leaves; the `else` block must end with `return`,
`break`, `continue` or `panic(...)`, and cannot see the pattern's names:

```tenon
let Some(i) = line.find(",") else { return Err("missing comma") }
let Rect(w, h) = shape else { continue }
```

Patterns: `_`, a name, literals (`3`, `-1`, `"text"`, `'a'`, `true`), tuples
`(a, b)`, variants `Some(x)` / `Shape.Rect(w, h)`, and alternatives `p | q`
(each alternative binds the same names). There are no struct patterns
(`Cell { kind: Formula(t), .. }`) and no list patterns: bind the value and read
its fields or elements. `let (a, b) = pair` and
`for (k, v) in m` take patterns that always match.

Reserved words: `and break continue else enum extern false fn for if import
in let linear match mut not or pub ref return self struct true unique var while`.

`()` as a pattern matches the Unit value (`Ok(()) => ...`).

`if` without `else`, and statements in general, must produce `Unit`: a value
cannot be silently dropped. Discard explicitly with `let _ = expr`.

There is no separate `loop` keyword: `while true { ... }` with no `break`
never finishes, so a function may end with it, also a function that returns a
value: the loop can then only be left by `return`, and no value is needed
after it. If the loop has a `break` of its own (one in a nested loop does not
count), the function must give a value after the loop.
`break` and `continue` can appear anywhere inside the loop body, including
inside `match` arms. Unary minus works on any number expression (`-x`, `-e.1`).

## 8. Strings and formatting

`"{expr}"` formats any value. Top-level strings are inserted as-is; inside
containers they are quoted:

| Value | Text |
|---|---|
| `3`, `-2` | `3`, `-2` |
| `1.5`, `2.0`, `1e20`, `0.1 + 0.2` | `1.5`, `2.0`, `1e20`, `0.30000000000000004` |
| `[1, 2]`, `["a"]` | `[1, 2]`, `["a"]` |
| `["k": 1]`, empty map | `["k": 1]`, `[:]` |
| `Some(1)`, `None` | `Some(1)`, `None` |
| `Point { x: 1, y: 2 }` | `Point { x: 1, y: 2 }` |
| `(1, "a")` | `(1, "a")` |

Floats print the shortest text that reads back as the same number, in plain
notation when the exponent is in [-5, 16), otherwise as `1.5e-7`.
`x.to_str()` gives the same text. Strings concatenate with `+`.

There are no format specifiers (`{x:>3}`, `{x:x}`): use
`"{x}".pad_left(3, " ")`, `x.to_str_radix(16)`, `f.to_fixed(2)` or
`cents.fmt_fixed(2)`.

## 9. Errors: values, `?`, and traps

Expected failures are values (`Option`, `Result`). `?` returns early from the
enclosing function on `None` / `Err(e)`; the function must return an `Option`,
or a `Result` with the **same** error type (no conversion).

```tenon
fn parse_pair(s: Str) -> Option[(Int, Int)] {
    let i = s.find(",")?
    Some((s.slice(0, i).to_int()?, s.slice(i + 1, s.len()).to_int()?))
}
```

`?` may be applied to any expression, anywhere an expression may appear:
`n = n * 16 + digit(c)?`, in arguments, list literals, conditions and `"{...}"`
interpolations. Evaluation stops at the first failure.

Formatting an `IoError` shows the variant: `"{e}"` is `NotFound("data/x.txt")`.

Bugs are **traps**: integer overflow, division by zero, index out of bounds,
missing map key in `m[k]`, `unwrap()` on `None`/`Err`, `panic(msg)`, failed
`assert(cond)`. A trap prints `trap: <message>` and `at file:line:col` to
stderr and exits. Traps cannot be caught.

`main` returns `Unit`, `Int` or `Result[Unit, E]`. Returning `Err(e)` prints
`error: <e>` to stderr and exits with code 1. Returning an `Int` exits with that
status: any value 0-255 except 70, 71, 72 and 74, which are kept for the
runtime's own failures. Returning one of those four, or a value outside 0-255,
traps (`trap: exit status 70 is out of range or reserved`, exit code 70).
Returning 0 or 1 is allowed (1 is the same code `Err` produces).
Standard output is flushed before the program exits, however it ends
(return, `Err` or trap); standard error is not buffered, and `eprintln`
flushes standard output first, so the two streams stay in order.

Exit codes used by the runtime:

| Code | Meaning | `main` may return it |
|---|---|---|
| 0 | success | yes |
| 1 | `main` returned `Err` | yes |
| 70 | trap | no |
| 71 | out of memory | no |
| 72 | stack overflow | no |
| 74 | standard output could not be written | no |

## 10. Capabilities (authority)

A program can only affect the outside world through capabilities, and the only
source of capabilities is the `Sys` value passed to `main`:

```tenon
struct Sys { console: Console, fs: Fs, clock: Clock, net: Net, args: List[Str] }
```

`sys.args` holds the command-line arguments *after* the program name. Paths
given to the unattenuated `sys.fs` are relative to the current directory (or
absolute; `sys.fs.within("/srv/data")` is fine). `sys.net` is the network
capability (§15). There are no global functions for I/O, no ambient file system access, and no
way to construct a capability. Functions that need authority take it as a
parameter, so a signature shows what a function can touch. Attenuate before
passing on:

```tenon
let data = sys.fs.within("data")      // can only reach paths under data/
let ro = data.read_only()             // and only read them
```

An attenuated `Fs` rejects absolute paths, `..`, and paths through a symbolic
link (`Err(Denied(..))`); so `within` on an attenuated `Fs` takes a relative
path too.

- `Fs.write(path, data)` replaces a file atomically and durably: it writes
  `path + ".tmp"` in the same directory (removing any existing file of that
  name first), fsyncs it and renames it over `path`; on failure the temp file
  is removed. So `fs.write("todo.db", ..)` uses `todo.db.tmp`: do not keep
  your own file under that name. `Fs.append` is durable (fsync).
- `Fs.read(path)` returns the file as text; a file that is not valid UTF-8 is
  `Err(Failed("path: invalid UTF-8"))`. For binary files use the byte
  variants `read_bytes`, `write_bytes`, `append_bytes` (§11, "Bytes"), which
  follow the same path, jail and read-only rules as `read`, `write`, `append`.
- `Fs.list(dir)` gives the entry *names* (not paths) of the files and
  directories in `dir`, without `.` and `..`, sorted by bytes (`"B" < "a"`).
- `Fs.mkdir(path)` creates the directory and any missing parents, and succeeds
  if it already exists. `Fs.mkdir_one(path)` creates exactly one directory:
  `Err(NotFound(path))` if the parent is missing, `Err(Failed("path: File exists"))`
  if `path` exists (so it can claim a name exclusively).
- I/O failures are `Err(IoError)`: `NotFound(path)`, `Denied(path)`, or
  `Failed("path: reason")` (the reason is the operating system's text).

Path text is handled by three prelude functions on `/`-separated paths. They
are lexical: they never touch the disk, and `..` is not resolved.

| Call | Result |
|---|---|
| `path_join("a", "b")`, `path_join("a/", "b")` | `"a/b"` |
| `path_join("a", "/b")` | `"/b"` (an absolute second part wins) |
| `path_join("", "b")`, `path_join("a", "")` | `"b"`, `"a"` |
| `path_parent("a/b/c")`, `path_parent("a/b/")` | `"a/b"`, `"a"` (trailing `/` ignored) |
| `path_parent("a")`, `path_parent("")` | `"."`, `"."` |
| `path_parent("/a")`, `path_parent("/")` | `"/"`, `"/"` |
| `path_base("a/b")`, `path_base("a/b/")` | `"b"`, `"b"` |
| `path_base("/")`, `path_base("")` | `"/"`, `""` |

## 11. Builtin API

See the prelude (`src/prelude.tn`, or `docs/prelude.tn` in a study kit) for the full list with signatures.
Highlights:

- `Str`: `len byte slice find split lines words trim trim_start trim_end
  starts_with ends_with contains to_int to_float upper lower replace chars
  find_from is_digits strip_prefix strip_suffix (Option) trim_chars (remove
  given ASCII bytes from both ends, e.g. `s.trim_chars(" \t")`)
  repeat pad_left pad_right is_empty rfind split_once rsplit_once to_int_radix
  bytes`; `Int.char()` makes a one-character string; `Str.from_utf8(bytes)`
  and `Str.from_utf8_lossy(bytes)` make text from bytes (see "Bytes" below).
  - `s.rfind(sub)` is the byte offset of the last match. `s.split_once(sep)` /
    `s.rsplit_once(sep)` split around the first / last `sep`:
    `"k=v=w".split_once("=") == Some(("k", "v=w"))`, `None` if `sep` is absent.
    The pieces share the original's bytes, like `slice`.
  - `s.split(sep)` keeps empty pieces: `"a,,b,".split(",")` is
    `["a", "", "b", ""]` and `"".split(",")` is `[""]`.
  - `s.lines()` splits on `"\n"` and drops a final empty line; it does not
    remove `"\r"`. `s.words()` splits on runs of spaces, tabs, `"\r"` and `"\n"`.
  - `s.to_int()` accepts an optional `+`/`-` and decimal digits only (no spaces,
    no `_`), and gives `None` on overflow. `s.to_int_radix(base)` (base 2-36,
    otherwise a trap) accepts an optional `-` (no `+`) and one or more digits
    `0-9a-z`, letters in either case, each below `base`; no prefix such as `0x`,
    no spaces or `_`; `None` if invalid or out of range (`INT_MIN` parses):
    `"ff".to_int_radix(16) == Some(255)`. `s.to_float()` also accepts `1.5`,
    `.5`, `5.`, `1e-3`, `inf` and `nan`.
  - `trim` removes ASCII whitespace; `upper`/`lower` change ASCII letters only.
- `List[T]`: `len push pop insert remove clear slice sort sort_by reverse get
  sort_by_desc sort_with swap first last index_of contains extend sorted reversed map filter any all count
  is_empty`, `+` concatenates; `List[Str].join`, `List[Int].sum`.
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
  `div_euclid` (the remainder is never negative); `fmt_fixed(scale)` writes a
  fixed-point integer (`1234.fmt_fixed(2) == "12.34"`, for money in cents); constants
  `INT_MAX`, `INT_MIN`; and for code points
  `is_digit is_alpha is_alnum is_space is_upper is_lower`
  (`s.byte(i).is_digit()`, `'7' - '0'`); `Float`: `to_int floor ceil round
  sqrt abs min max`, and `to_fixed(decimals)` (exactly that many digits; rounds the
  binary value half to even, like printf). There are no bitwise operators: use
  `/`, `%` and `pow` (`x / 2.pow(k)` shifts right by `k` for `x >= 0`).
- `Console`: `print println eprintln read_line read_all flush read_all_bytes
  write_bytes`. `read_line` returns `None` at end of input and removes the
  line's `"\n"` and one `"\r"` directly before it (a last line without
  `"\n"` is returned as is, `"\r"` included); `read_all` keeps every `"\r"`.
  Standard output is buffered: it is flushed before any blocking read and at
  exit; a program that answers requests line by line while another process
  waits calls `flush()` after each answer.
- `Fs`: `read write append exists is_dir remove rename list mkdir mkdir_one
  within read_only read_bytes write_bytes append_bytes` (details in §10).
  `mkdir` creates missing parents, `mkdir_one` exactly one directory; `rename`
  is atomic and replaces the target; `remove` deletes a file or an empty
  directory.
- Bytes are a `List[Int]` whose elements are 0..255.
  - `fs.read_bytes(path)` (`Result[List[Int], IoError]`) reads any file;
    `fs.write_bytes(path, data)` replaces a file atomically like `write`,
    `fs.append_bytes(path, data)` appends like `append`.
    `con.read_all_bytes()` returns the rest of standard input unchanged
    (after any lines `read_line` took); `con.write_bytes(data)` writes to
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
    becomes U+FFFD; §15).
  - `decode` (§14) rejects a string literal whose escapes do not make valid
    UTF-8.
  - The byte APIs above never change a byte.
- Line endings: `s.lines()` splits on `"\n"` only and keeps `"\r"`
  (`"a\r\nb".lines() == ["a\r", "b"]`; use `l.trim_end()` or
  `l.strip_suffix("\r")`); `s.words()` treats `"\r"` as a separator;
  `Console.read_line` and `Conn.read_line` remove one `"\r"` before the `"\n"`.
- Paths: `path_join(a, b)`, `path_parent(p)`, `path_base(p)` (§10).
- `Clock`: `now_ms mono_ns sleep_ms`.

## 12. Obligations: linear and unique types

```tenon
linear struct Claim { job: Str }      // must be used exactly once
unique struct Handle { fd: Int }      // never copied; may be dropped
```

A **linear** value is an obligation (a claimed job, a pending reply, a held
lock). The compiler rejects any program that copies one or loses one:

- it is *consumed* by passing it by value: as an argument, as the receiver of
  a method taking `self`, by returning it, by storing it in a struct or variant
  field, or by destructuring it with `match`;
- reading fields (`c.job`), comparing and formatting do not consume it;
- every path must consume it: both branches of an `if`, every `match` arm,
  and before `return`, `break`, `continue` or `?`;
- a value from outside a loop cannot be consumed inside the loop;
- `_` patterns and `let _ =` cannot discard it, and it cannot be overwritten;
- closures cannot capture it; `List`/`Map` cannot hold it; generic functions
  other than `unwrap`/`expect` cannot take it (they might copy or drop).

Inside a method of the type itself, `self` is exempt: the type's own methods
(`fn Claim.complete(self)`) decide how a value is finished, and only the type's
module can define them (§13). A struct or enum
that contains a linear value must itself be declared `linear` (generic
wrappers such as `Option[Claim]` become linear automatically).

A **unique** value follows the same rules except that it may be dropped.

A parameter declared `x: ref T` only *inspects* its argument: the caller keeps
the value (it is not consumed by the call), and the function may read it but
not consume it. Use it for helpers that look at an obligation or a handle:

```tenon
fn respond(c: ref Conn, body: Str) -> Result[Unit, IoError] { c.write(body) }
```

## 13. Modules

```tenon
import journal                       // journal.tn next to this file, else the standard library

fn main(sys: Sys) -> Result[Unit, IoError] {
    let j = journal.open(sys.fs.within("data"), "log")   // module function
    let loaded: journal.Loaded = j.load()?                 // module type
    j.append("hello")
}
```

- `import name` looks for `name.tn` next to the importing file first, then in the
  standard library (`journal`, `regex`). A local file therefore hides a std
  module of the same name, except that a file never imports itself.
- A module is a file; `import name` makes its public items available as
  `name.item` (functions, types, `name.Type.function`) and the variants of its
  public enums by their plain names.
- Items are private unless declared `pub`; struct fields are private unless
  marked `pub`. Outside its module, a struct with private fields cannot be
  built, and its private fields cannot be read. Derived formatting shows a
  foreign type's private fields as `..`.
- A top-level item (function, constant, struct, enum) defined in a file
  hides the prelude item of the same name in that file, so a new prelude
  name never breaks a program. Other files still see the prelude's item
  (or the module's as `mod.name`), and the prelude's own code, `?` and the
  values prelude functions return always use the prelude's. Unqualified
  variant names work the same way: a variant of the file's own or an
  imported enum hides a prelude variant of the same name (`Option.Some`
  still names the prelude's; two user enums with the same variant are
  still ambiguous), and patterns follow the matched value's type. A file
  that hides `Result`, `Option` or `Sys` cannot name the prelude's type, so
  its functions cannot return one (or take `sys: Sys` in `main`);
  diagnostics show the file's own type as `<main>.Result` in the main file.
  Defining a name twice in one file is still an error, and so is a method
  the prelude already defines (`fn Str.trim`).

  ```tenon
  fn path_join(a: Str, b: Str) -> Str { a + "::" + b }   // hides the prelude's
  struct Result { code: Int }                             // a distinct type

  fn main(sys: Sys) {
      sys.console.println(path_join("a", "b"))            // a::b
      match "7".to_int().ok_or("bad") {                   // the prelude's Result
          Ok(n) => sys.console.println("{n}"),
          Err(e) => sys.console.println(e),
      }
  }
  ```
- Methods of a declared type (a `struct` or `enum`, including the prelude's
  `Option`, `Result`, `IoError`, `Sys`, `Set`, `Heap`, `NetEvent`) can only be
  defined in the module that declares the type. Together with privacy this
  makes a module the only place that can create a value of its type or finish
  a linear one: privacy is unforgeability.
- The builtin types (`Int`, `Float`, `Bool`, `Str`, `Unit`, `List`, `Map`, and
  the capabilities `Console`, `Fs`, `Clock`, `Net`, `Listener`, `Conn`,
  `Poller`) have no declaring module, so any file may add methods to them:
  `fn Str.shout(self) -> Str { self.upper() + "!" }` in a main file makes
  `"hi".shout()` work. Such a method is private to its file unless declared
  `pub` (then importers can call it too). There is one method of a given name
  per type in the whole program: defining one the prelude already has
  (`fn Str.trim`), or one that another module of the program also defines, is
  an error (`function 'Str.shout' is already defined`).
- Standard library modules: `journal` (append-only, checksummed, crash-safe
  record log) and `regex` (below). Their source is `std/journal.tn` and
  `std/regex.tn` in the repository, `docs/std-journal.tn` and
  `docs/std-regex.tn` in a study kit; either way `import journal` and
  `import regex` find them.

### `regex`

Regular expressions, written in Tenon (`std/regex.tn`, or `docs/std-regex.tn`
in a study kit; its header comment is the full specification). Matching is by backtracking, character by character over
UTF-8; offsets are byte offsets.

```tenon
import regex

let date = regex.compile("(\\d{4})-(\\d{2})-(\\d{2})").unwrap()   // Result[Regex, Str]
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
  In a Tenon string literal write each regex backslash twice and `{` as `\{`.
  Not supported: backreferences, lookaround, named groups, flags.
- A pattern that would take more than about a million backtracking steps (for
  example `(a+)+b` on a long run of `a`) stops the program with `panic`, naming the pattern.

## 14. Data codec

`encode(x)` gives the text that formatting prints for `x`, with every field;
`decode(text)` parses it back for the expected type and is strict: it accepts
exactly the canonical text and fails with `Err("cannot decode T at byte N")`
otherwise. Annotate the expected type where it is not inferred:
`let r: Result[Event, Str] = decode(line)`. Functions, capabilities,
linear/unique types and types with fields you cannot see cannot be encoded.

## 15. Networking

```tenon
let l = sys.net.listen(8080)?          // Listener on 127.0.0.1; port 0 picks one (l.port())
let c = l.accept()?                    // Conn
let line = c.read_line()?              // Option[Str]; None at end of stream
c.write("HTTP/1.1 200 OK\r\n...")?
let d = sys.net.connect("localhost", 8080)?
```

`Listener` and `Conn` are unique handles: they cannot be copied, and dropping
one closes it. Operations block; before blocking (`accept`, `connect`, reads,
`sleep_ms`, reading the console) the program's standard output is flushed.

### Many connections: the event loop

Concurrency in Tenon is a single-threaded event loop: no data races are
possible, and events arrive in a deterministic order. A `Poller` (a unique
handle from `sys.net.poller()`) owns many sockets, named by `Int` ids:

```tenon
let p = sys.net.poller()
let lid = p.listen(8080)?                   // listener id; p.port(lid) for port 0
while true {
    for ev in p.wait(-1) {                  // -1: wait without a timeout (ms otherwise)
        match ev {
            Accepted(_, id) => { let _ = p.send(id, "hello\n") }
            Data(id, text) => { let _ = p.send(id, text) }   // echo
            Closed(id) => {}
            Timeout => {}
        }
    }
}
```

`wait` accepts new connections for you, reports received bytes as text
(invalid UTF-8 becomes U+FFFD; a multi-byte character can be split across two
`Data` events), and reports peers that closed. `send` writes everything (it may
block on a slow peer); `close(id)` closes a connection or listener. Events are
reported in increasing id order. A struct holding a `Poller` must be declared
`unique struct`. See programs/chat for a complete server.

## 16. Not yet implemented

Multi-core parallelism; see `docs/log.md`.
