# Tenon language reference

This is the single source document for the language. With the one-page
[docs/quickstart.md](quickstart.md) (a translation table from Python and
TypeScript), [docs/library.md](library.md) (the builtin API and the standard
library) and [docs/tools.md](tools.md) (the `tenon` command) it is the only
documentation given to authors in the usability study, so it must be enough
to write real programs. Every signature of the builtin API is in the prelude
(`lib/prelude.tn` in the repository; `docs/prelude.tn` in a study kit), which
is ordinary Tenon source.

Every claim here is checked by a test in `tests/` (run `./check`; the
doc programs themselves: `python3 ops/gates/doctest.py`).

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
identically; the test suite checks this for every test program. Every
command, flag, environment variable and exit status of `tenon` is in
[docs/tools.md](tools.md).

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
  Escapes: `\n \t \r \0 \\ \" \{ \}`. `"{expr}"` interpolates any value and
  `"{expr:SPEC}"` formats it (see §8); write `\{` for a literal `{` (a lone `}` is literal).
- Raw strings: `r"..."` has no escapes and no interpolation; every character
  up to the next `"` is taken literally, backslashes and braces included
  (`r"C:\temp"`; `r"(\d{4})"` equals `"(\\d\{4})"`). Like a normal string it
  cannot span lines, and it cannot contain `"`: use a normal string for that
  (`"say \"hi\""`), or concatenate (`r"\d+" + "\""`). The `r` must touch the
  quote. A raw string is an ordinary `Str`.
- `()` is the only value of type `Unit`.

## 3. Types

| Type | Meaning |
|---|---|
| `Int` | 64-bit signed integer. Overflow **traps**. `/` and `%` truncate toward zero (`-7 / 2 == -3`, `-7 % 2 == -1`); dividing by zero traps. |
| `Float` | 64-bit IEEE float. |
| `Bool` | `true` / `false`. |
| `Str` | Immutable UTF-8 text. Offsets and `len()` are in bytes; `char_count()` counts code points ([docs/library.md](library.md)). |
| `Unit` | No information; written `()`. |
| `List[T]` | Growable sequence with value semantics. |
| `Map[K, V]` | Hash map; iteration follows insertion order. |
| `(A, B, ...)` | Tuple; fields `.0`, `.1`, ... |
| `fn(A, B) -> R` | Function value (named function or closure). |
| `Option[T]` | `Some(T)` or `None`. There is no null. |
| `Result[T, E]` | `Ok(T)` or `Err(E)`. |
| `Console`, `Fs`, `Clock`, `Net`, `Proc` | Capabilities (§10). |
| `Workers`, `Worker[R]`, `Sender[T]`, `Receiver[T]` | Workers and channels (§18). |

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
- Reference counts are plain (non-atomic) integers, also in programs with
  workers (§18): a value is never shared between threads. What crosses to
  another worker is copied, at a cost proportional to its size.

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
fn List[Robot].find(self, name: Str) -> Option[Robot] { ... }   // also of your own types
fn Counter.bump(mut self) -> Int { self.n += 1; self.n }    // a `mut self` method may return a value
fn Counter.reset(mut self) { self = Counter { n: 0 } }      // and may assign all of `self`
```

Where methods may be defined: on your own types in their file, and on the
builtin types (`Int`, `Str`, `List[T]` or a specific `List[Robot]`, `Map`,
...) in any file. `Option`, `Result` and the other prelude enums and structs
are declared types: only the prelude can add methods to them (write a free
function such as `fn is_full(o: Option[Int]) -> Bool` instead). Details in §13.

- A struct may not contain itself directly; use an enum or a `List`.
- Variants are used unqualified (`Circle(3)`) unless two enums share a variant
  name, then qualify: `Shape.Circle(3)`.
- Every type automatically supports `==`, `!=`, ordering (`<` ...; maps are
  not ordered), hashing (usable as a map key), and `to_str()`. Functions and
  capabilities cannot be compared. These are the derived traits Eq, Ord,
  Hash and Show (§17), usable as bounds; `impl Show` changes a type's text.
- Derived ordering: numbers numerically; `false < true`; strings by bytes
  (so `"B" < "a"`); lists and tuples lexicographically, element by element;
  structs field by field in declaration order; enums by variant declaration
  order, then payload. `sort` and `sort_by` are stable. For descending order
  sort by a negated key (`xs.sort_by(fn(p) => (-p.score, p.name))`).
- Struct update: `Point { x: 3, ..p }` copies the other fields from `p`
  (the `..base` part comes last).
- Field shorthand: `Point { x, y }` means `Point { x: x, y: y }` (a field set
  from the variable of the same name). It mixes with the other forms:
  `Point { x, y: 0 }`, `Point { x, ..p }`.

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
- `var` destructures like `let`, and every name it binds is mutable:
  `var (count, label) = (1, "x")` then `count += 1`. One pattern cannot mix
  `var` and `let` names: bind with `var` (or copy the one part:
  `let (a, b) = f(); var a2 = a`).
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
for i in 0..n { ... }            // half-open range: 0, 1, ..., n - 1
for i in rev_range(0, n) { ... } // the same numbers, counting down: n - 1, ..., 0
for x in xs { ... }              // over a snapshot of the list
for (k, v) in m { ... }          // over map entries in insertion order
for x in set.items() { ... }     // a Set is not iterable itself
break; continue; return value
```

A range `a..b` is empty when `b <= a` (`for i in 5..2` runs zero times; no
step is taken backwards), and both ends are evaluated once, before the first
iteration. A range is not a value: it appears only after `for ... in`, so
there is no `(0..n).rev()`. To count down use `rev_range(lo, hi)`, a prelude
function giving `lo..hi` in descending order (`rev_range(0, 3) == [2, 1, 0]`;
empty when `hi <= lo`). It is an ordinary `List[Int]`, but `for i in
rev_range(a, b)` compiles to a plain countdown loop in a C build, without
building the list (the interpreter builds it). `while` loops work too.

`match` must be exhaustive, and an arm that can never match is an error:

```tenon
match shape {
    Circle(r) if r > 100 => "big circle",
    Circle(_) => "circle",
    Rect(w, h) | ... => ...,
    _ => "other",
}
```

A guard (`if cond` after the pattern) works on every kind of arm, including
string and number literals; when the guard is false the following arms are
tried, so the same literal may appear again without a guard:

```tenon
match t[0] {
    "ROOM" if t.len() == 3 => room(t[1], t[2]),
    "ROOM" => usage(),
    other => unknown(other),
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
inside `match` arms. A bare `return` (no value) may end a match arm or stand
anywhere an expression may: `None => return,`, `if bad { return }`.

Unary minus works on any number expression (`-x`, `-e.1`). It binds more
loosely than method calls, field access and indexing: `-x.min(y)` is
`-(x.min(y))`; write `(-x).min(y)` for the other meaning. A minus directly
before a number literal is part of the literal: `-2.abs()` is `(-2).abs()`, `2`.

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
| a variant without payload: `S`, `Shape.Empty`, `[S, X]` | `S`, `Empty`, `[S, X]` (its name, never qualified) |
| `Point { x: 1, y: 2 }` | `Point { x: 1, y: 2 }` |
| `(1, "a")` | `(1, "a")` |

Floats print the shortest text that reads back as the same number, in plain
notation when the exponent is in [-5, 16), otherwise as `1.5e-7`.
`x.to_str()` gives the same text. Strings concatenate with `+`. An
interpolation may contain string literals of its own:
`"{m.get_or("k", 0)} {names.join(", ")}"`.

### Format specs

`"{expr:SPEC}"` pads, aligns and converts an `Int`, `Float`, `Str` or `Bool`:

```
SPEC      = [[fill] align] ["0"] [width] [","] ["." precision] [radix]
align     = "<" (left) | ">" (right) | "^" (center)
fill      = any one character except "}" and "\""   (default: space)
width     = 1 to 3 digits; the minimum length in code points
precision = 1 to 3 digits, at most 100; Float only
","       = thousands separator; Int and Float, not with a radix
radix     = "x" | "X" | "b" | "o"; Int only
```

| Spec | Example | Text |
|---|---|---|
| width | `"{7:4}"`, `"{"ab":4}"` | `   7`, `ab  ` (numbers right-aligned, text left) |
| align | `"{7:<4}"`, `"{"ab":>4}"`, `"{"ab":^6}"` | `7   `, `  ab`, `  ab  ` (extra space goes right) |
| fill | `"{7:*>4}"`, `"{"ab":.^6}"` | `***7`, `..ab..` |
| zero | `"{-42:05}"`, `"{-2.5:06.2}"` | `-0042`, `-02.50` (after the sign; Int and Float) |
| radix | `"{255:x}"`, `"{255:X}"`, `"{5:b}"`, `"{8:o}"`, `"{-255:x}"` | `ff`, `FF`, `101`, `10`, `-ff` |
| radix + width | `"{255:08x}"`, `"{5:>4b}"` | `000000ff`, ` 101` |
| precision | `"{2.675:.2}"`, `"{0.5:.0}"`, `"{1.0 / 3.0:8.3}"` | `2.67`, `0`, `   0.333` |
| separator | `"{1234567:,}"`, `"{-1234:>8,}"`, `"{INT_MIN:,}"` | `1,234,567`, `  -1,234`, `-9,223,372,036,854,775,808` |
| separator + float | `"{1234567.891:,.2}"`, `"{1234.5:,}"` | `1,234,567.89`, `1,234.5` |
| separator + zero | `"{1234:011,}"`, `"{1234:012,}"`, `"{-1234.5:012,.2}"` | `000,001,234`, `0,000,001,234`, `-0,001,234.50` |

- **The colon rule**: the spec starts at the first `:` that is not inside
  `( )`, `[ ]`, `{ }` or a nested string or character literal, and runs to
  the closing `}`. No expression has a `:` at that level, so
  `"{m["k:v"]:>5}"`, `"{["a": 1].len():3}"` and
  `"{f(fn(x: Int) => x):4}"` all split where expected. The spec is raw text:
  no escapes, and it cannot contain `}`, `"` or a newline.
- A larger value is never cut: `"{12345:3}"` is `12345`. Widths count code
  points, as `pad_left` does (`"{"Zürich":8}"` is `Zürich  `).
- `.N` rounds exactly like `f.to_fixed(N)` (the binary value, half to even:
  `"{2.675:.2}"` is `2.67`). Without a precision a `Float` keeps its usual
  shortest text (`"{0.1:6}"` is `   0.1`); `nan` and `inf` are padded like
  any other text.
- `,` puts a comma between groups of three digits of the integer part
  (after the sign, up to the `.` or an exponent; `"{1e20:,}"` is `1e20`, and
  `nan`/`inf` are unchanged). With `0` padding the zeros are digits too and
  are grouped as well; the text never starts with a comma, so it can be one
  character longer than the width (`"{1234:012,}"` is 13 characters), as in
  Python. It comes after the width and before the precision: `"{x:12,.2}"`.
- Radix digits are lowercase for `x` (uppercase for `X`), with `-` before
  negative numbers and no `0x` prefix, as `to_str_radix`; `INT_MIN` works.
- Specs nest like any interpolation:
  `"{"{name:<6}={qty:03}":>12}"`.
- Everything else is a compile-time error: a spec on any other type
  (`List`, `Option`, a struct, a generic `T`: format the parts, or call
  `to_str()` first), `.N` on a non-`Float`, a radix on a non-`Int`, `0` or `,` on a
  `Str` or `Bool`, `,` together with a radix (`"{n:,x}"`), a `,` in another
  position (`"{n:,8}"`, `"{f:.2,}"`), `0` together with an alignment, an alignment without a
  width, an empty spec, and Python's type letters (`"{f:.2f}"` is written
  `"{f:.2}"`; `"{n:d}"` is `"{n}"`). The value's type must be known at that
  point: in `fn(x) => "{x:5}"` annotate `x: Int`.

`cents.fmt_fixed(2)` writes a fixed-point integer (`1234` as `12.34`).

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

`sys.proc.exit(status)` ([docs/library.md](library.md), `Proc`) may end a program with any status 0-255,
including these four (an interpreter passes on the status of the program it runs).

## 10. Capabilities (authority)

A program can only affect the outside world through capabilities, and the only
source of capabilities is the `Sys` value passed to `main`:

```tenon
struct Sys { console: Console, fs: Fs, clock: Clock, net: Net, proc: Proc, args: List[Str] }
```

`sys.args` holds the command-line arguments *after* the program name. Paths
given to the unattenuated `sys.fs` are relative to the current directory (or
absolute; `sys.fs.within("/srv/data")` is fine). `sys.net` is the network
capability (§15); `sys.proc` runs other programs (below); `sys.workers()`
starts workers on other cores (§18). There are no global functions for I/O, no ambient file system access, and no
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
  variants `read_bytes`, `write_bytes`, `append_bytes` ([docs/library.md](library.md), "Bytes"), which
  follow the same path, jail and read-only rules as `read`, `write`, `append`.
- `Fs.read`, `Fs.read_bytes` (and `Fs.truncate`) on a directory give
  `Err(Failed("path: Is a directory"))` (the operating system's text).
- `Fs.truncate(path, len)` cuts an existing file to its first `len` bytes and
  fsyncs it, in place (the cheap way to drop a torn tail: `fs.truncate(p,
  text.rfind("\n").unwrap() + 1)`). It never extends a file and never
  creates one: a missing file is `Err(NotFound(path))`, and `len < 0` or
  `len` larger than the file is `Err(Failed("path: truncate length 9 is
  larger than the file (5 bytes)"))` (or `"... is negative"`), with the file
  unchanged. It is a write: a read-only `Fs` gives `Denied`, and the jail,
  NUL and symlink rules above apply. Unlike `write` it is not atomic.
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

The methods of the builtin types (`Str`, `List`, `Map`, `Set`, `Heap`,
`Option`, `Result`, `Int`, `Float`), the operations of the capabilities
(`Console`, `Fs`, `Clock`, `Proc`), bytes, text encoding and line endings
are described in [docs/library.md](library.md), with the standard library
modules (`journal`, `regex`). Every signature is in the prelude
(`lib/prelude.tn` in the repository, `docs/prelude.tn` in a study kit).

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
- Inside a package (a `tenon.toml` in the file's directory or above it),
  `import name` looks first for `name.tn` next to the importing file, then
  for the entry module of a dependency `name` in the package's manifest,
  then in the standard library. Manifests, `tenon fetch`, the lock file and
  the offline cache: [docs/packages.md](packages.md).
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
  the capabilities `Console`, `Fs`, `Clock`, `Net`, `Proc`, `Listener`,
  `Conn`, `Poller`) have no declaring module, so any file may add methods to them:
  `fn Str.shout(self) -> Str { self.upper() + "!" }` in a main file makes
  `"hi".shout()` work. Such a method is private to its file unless declared
  `pub` (then importers can call it too). There is one method of a given name
  per type in the whole program: defining one the prelude already has
  (`fn Str.trim`), or one that another module of the program also defines, is
  an error (`function 'Str.shout' is already defined`).
- Standard library modules: `journal` (append-only, checksummed, crash-safe
  record log) and `regex` (regular expressions), described in
  [docs/library.md](library.md) ("Standard library"). `import journal` and
  `import regex` find them.

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

Within one thread, concurrency is a single-threaded event loop: no data
races are possible, and events arrive in a deterministic order (for more
cores, workers and channels: §18). A `Poller` (a unique handle from
`sys.net.poller()`) owns many sockets, named by `Int` ids:

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

## 16. Formatting

Every program has one canonical layout, which `tenon fmt` produces; its
rules are in [docs/tools.md](tools.md) ("Formatting").

## 17. Traits

A trait names a set of methods; an `impl` gives them for one type.

```tenon
trait Shape {
    fn area(self) -> Int
    fn name(self) -> Str { "shape" }                       // a default method
    fn describe(self) -> Str { self.name() + " of area {self.area()}" }
}

struct Square { side: Int }

struct Rect { w: Int, h: Int }

impl Shape for Square {
    fn area(self) -> Int { self.side * self.side }
    fn name(self) -> Str { "square" }                      // replaces the default
}

impl Shape for Rect {
    fn area(self) -> Int { self.w * self.h }
}

// T: Shape is a bound: any type with an impl of Shape
fn total[T: Shape](xs: List[T]) -> Int {
    var t = 0
    for x in xs { t += x.area() }
    t
}

fn main(sys: Sys) {
    let con = sys.console
    con.println(Square { side: 3 }.describe())             // square of area 9
    con.println("{total([Rect { w: 2, h: 5 }, Rect { w: 1, h: 1 }])}")   // 11
    let shapes: List[dyn Shape] = [dyn Shape(Square { side: 2 }), dyn Shape(Rect { w: 2, h: 3 })]
    for s in shapes { con.println("{s.name()}: {s.area()}") }   // square: 4, shape: 6
}
```

**Declaring.** `trait Name { ... }` lists methods; each takes `self` (or
`mut self`) first and may have a default body, which can call the trait's
other methods. Methods may be generic (`fn pair[U](self, u: U) -> (Self, U)`).
`Self` in a trait or impl is the implementing type. A trait may be `pub`;
traits have no type parameters of their own, no supertraits and no
functions without `self` (yet).

**Implementing.** `impl Trait for Type { ... }` gives every method that has
no default, with exactly the trait's signature (`Self` replaced by the
type); a missing method, an extra one or a different signature is an error.
Generic types get generic impls, with bounds on their parameters:
`impl[T: Show] Describe for List[T] { ... }` (the syntax of `fn f[T: Show]`);
a specific instantiation also works (`impl Describe for Option[Int]`). Builtin
types (`Int`, `Str`, `List[T]`, ...), tuples and function types can have impls.

**Calling.** A method of a trait implemented for a type is called like the
type's own methods: `sq.area()`, also from other modules. If the type has its
own method of that name, that one wins; two traits giving one type the same
method name make the call ambiguous (an error).

**Bounds.** `fn f[T: A + B](x: T)` accepts any type implementing A and B, and
inside f the methods of A and B can be called on `x`. A call of f with a type
that lacks an impl is rejected at the call: `type Point does not implement
Shape (needed by bound T: Shape of total)`. A type parameter has only the
bounds it declares, so a generic function passing its `T` on to `total`
needs `T: Shape` itself. Generic code is compiled once per type it is used
with (monomorphization), so a call through a bound costs what a direct call
costs; the interpreter does the same.

**`dyn` values.** `dyn Shape(x)` converts a value of any type implementing
Shape into a value of type `dyn Shape`, so different types can share a list,
a map or a field. The conversion is always written; a `dyn Shape` passed to
`dyn Shape(...)` again is unchanged. Methods called on a `dyn` value are
found at run time through a table (in C, one static vtable per trait and
type); a `dyn Shape` also satisfies the bound `T: Shape`. Formatting a `dyn`
value formats the value inside (`dyn Show(x)` makes a list of anything
printable). `dyn` values are values like any other (copying shares the
value inside), but they cannot be compared, hashed (map keys) or encoded.
Only an object-safe trait can be used with `dyn`: its methods take `self` by
value, are not generic and do not mention `Self`; otherwise `trait Twin
cannot be used with 'dyn': method 'twin' mentions Self`.

**Derived traits.** `Eq`, `Ord`, `Hash` and `Show` are traits of the prelude
(lib/v2/prelude.tn) that every type satisfies structurally, exactly as `==`,
ordering, hashing and `to_str()` always worked (§4). As bounds they say what
a type parameter is used for: `fn largest[T: Ord](xs: List[T]) -> T`,
`fn count[K: Hash + Eq](xs: List[K]) -> Int`. Eq: no functions,
capabilities or `dyn` values inside; Ord: Eq and no maps; Hash (usable as a
map key): Eq and no Float; Show: no functions or capabilities (a fifth,
Send, says what can go to another worker: §18). "Inside" counts every
field and payload, through other declared types (`struct Log { c: Console }`
is not Show), except that a type whose Show impl applies is Show whatever it
contains. A type that
contains a function does not satisfy Eq: `type fn(Int) -> Int does not
implement Eq (needed by bound T: Eq of same)`. Only Show can be implemented,
to replace the derived text:

```tenon
struct Money { cents: Int }

impl Show for Money {
    fn to_str(self) -> Str { "${self.cents / 100}.{(self.cents % 100).to_str().pad_left(2, "0")}" }
}

fn main(sys: Sys) {
    let m = Money { cents: 1205 }
    sys.console.println("{m} {[m, Money { cents: 7 }]}")   // $12.05 [$12.05, $0.07]
}
```

The impl is used wherever a Money is formatted: interpolation, `to_str()`,
inside lists, maps, tuples and other values, in generic code, `dyn` values,
`unwrap` traps and `main`'s error; `encode` (§14) stays structural so that
`decode` reads it back. Inside `to_str` format the fields, not `self` (that
would call it again). `impl Eq`, `Ord` and `Hash` are refused in this
version: equality, map keys and sorting stay structural, so the interpreter
and the C backend cannot disagree about them. An impl of Show may bound its
type parameters only by derived traits (`impl[T: Show] Show for Box[T]`).
An impl for one instantiation formats only that one: with `impl Show for
Box[Int]`, a `Box[Str]` keeps the derived text, also in generic code. A
generic impl applies where its bounds hold: with `impl[T: Hash] Show for
Box[T]`, a `Box[Float]` keeps the derived text (its body, which may use `T`
as a map key, never runs for it).

**Coherence.** A type implements a trait at most once: a second impl, or a
generic impl overlapping another (`impl[T] Shape for List[T]` and
`impl Shape for List[Int]`), is an error. An impl must be in the module that
declares the trait or the one that declares the type (the orphan rule):
`impl Show for Point` belongs with `Point`, and `impl geo.Shape for Tile`
works in Tile's module. The builtin types have no module, so only a trait's
own module can implement it for `Int` or `List[T]`, and Show (the prelude's)
cannot be implemented for them.

**Obligations (§12).** A bounded generic function takes linear and unique
values like any generic function: calling a `self` method of the trait
consumes the value. Only an impl in the type's own module finishes a linear
value through `self`; an impl elsewhere must consume it like any other
code. `dyn` values cannot hold linear or unique values (`a 'dyn' value
cannot hold the linear type Job`): a table call could not tell whether the
value was finished.

## 18. Workers and channels

A worker runs a function on another OS thread, so programs can use every
core. Workers share nothing: each has a heap of its own, and they
communicate through typed channels. What goes from one worker to another is
copied into the receiver's heap (a unique value is moved), so no two threads
ever touch the same value and there are no data races, by construction.
The API is in the prelude (`lib/v2/prelude.tn`).

```tenon
fn count_words(lines: List[Str]) -> Int {
    var n = 0
    for l in lines { n += l.words().len() }
    n
}

fn main(sys: Sys) {
    let con = sys.console
    let w = sys.workers()                         // the authority to start workers
    let h = w.spawn(count_words, ["a b", "c"])   // runs on another core
    con.println("{h.join()}")                     // 3: waits, gives the result
    con.println("{w.par_map([1, 2, 3], fn(x) => x * x)}")   // [1, 4, 9]
    // a pool: the jobs go into one channel, every worker takes the next one
    let (jobs, todo) = channel()
    let (done, results) = channel()
    var pool: List[Worker[Unit]] = []
    for _ in 0..4 {
        pool.push(w.spawn(fn(_) {
            while let Some(x) = todo.recv() { done.send((x, x * 10)) }
        }, ()))
    }
    for i in 0..8 { jobs.send(i) }
    jobs.close()                                  // recv gives None once the jobs are gone
    var out: List[(Int, Int)] = []
    for _ in 0..8 { out.push(results.recv().unwrap()) }
    out.sort()                                    // in whatever order they finished: sort
    for h2 in pool { h2.join() }
    con.println("{out}")
}
```

| Call | Meaning |
|---|---|
| `sys.workers()` | the `Workers` capability: only `main` has it, and passes it on explicitly |
| `w.spawn(f, arg)` | start `f(arg)` (`f: fn(A) -> R`) on a new worker; gives a `Worker[R]` |
| `h.join()` | wait for the worker and give its result (a copy: a handle may be joined again, by any worker) |
| `w.cores()` | the number of cores (to size a pool) |
| `w.par_map(xs, f)`, `w.par_map_n(n, xs, f)` | `xs.map(f)` computed by `cores()` (or `n`) workers: the same list, in order |
| `channel()` | a new channel: `(Sender[T], Receiver[T])`, `T` inferred from use |
| `tx.send(x)` | put a copy of `x` in the channel (never waits: channels are unbounded); traps on a closed channel |
| `tx.close()` | no more sends; receivers get what is left, then `None` |
| `rx.recv()` | the next value (`Option[T]`), waiting for one; `None` once closed and empty |
| `rx.try_recv()` | the next value if there is one now, else `None` (for polling) |

A function of several values takes a tuple (`w.spawn(f, (a, b))`), or is a
closure that captures them (`w.spawn(fn(_) => f(a, b), ())`). Channel
handles and `Worker` handles are shared: copies of a `Sender` all send to the
same channel, and any number of workers may send to and receive from one
channel (each value is received once). They cannot be compared or encoded.

**What can be sent: `Send`.** The derived trait `Send` (like `Eq` and `Show`,
§17) says which values may go to another worker, as spawn's argument or
result or through a channel. Every type is `Send` except:

- linear types (§12), and types containing them: a channel that is dropped
  with values in it, or a worker that is never joined, would lose the
  obligation (`type Job does not implement Send (needed by bound T: Send of
  channel): the linear type Job could be dropped by a channel or a worker that
  is never joined`);
- the socket handles `Poller`, `Listener` and `Conn`, and types containing
  them: their sockets belong to the worker that opened them. Send the `Net`
  capability and open them in the worker.

A type parameter is `Send` only if it declares it (`fn f[T: Send](x: T)`), so
generic code that sends its values says so. The other capabilities (`Console`,
`Fs`, `Clock`, `Net`, `Proc`, `Workers`) can be sent: a worker has no
authority except what the program passes to it (an attenuated `Fs` stays
attenuated). Unique values (§12) are moved: after `tx.send(t)` or
`w.spawn(f, t)` the sender cannot use `t`. A worker cannot return a unique
value, because every `join` of a handle gives the result; send it through a
channel instead. Closures capture by value and cannot capture unique or
linear values, so a closure (also inside a `dyn` value, which cannot hold
them either) always carries only sendable values, and can be spawned or sent.

**Traps.** A trap in a worker ends the whole program with status 70, as a
trap in `main` does (traps are bugs, and are not caught); so do a stack
overflow (72) and `sys.proc.exit` in a worker. When `main` returns, the
program ends, also the workers that are still running: join the ones whose
work matters.

**Closing and deadlock.** A channel ends only when some sender calls
`close()`; dropping the senders does not close it. A program in which every
thread waits on a `recv` or a `join` that nothing can satisfy (for example a
`recv` loop on a channel that is never closed, after its senders finished)
traps with `deadlock: every worker is waiting for a channel or a join`, at the
main thread's wait, instead of hanging. A thread blocked elsewhere (a socket,
`Poller.wait`, the console) does not count as waiting.

**Deterministic output.** Workers run in parallel, so the order of their
`println` lines and of values arriving on a shared channel depends on
scheduling. Programs (and tests) whose output must not vary collect results
through channels and sort them, or by index (`par_map` does), and print from
`main` after `join`. A line printed by `println` is never mixed with
another worker's.

**Event loops.** A `Poller` lives in one worker, which opens it from the
`Net` it was given; several workers may each run an event loop. An event loop
polls a channel with `try_recv` between waits with a timeout:

```tenon
fn serve(caps: (Net, Receiver[Str])) -> Int {
    let (net, stop) = caps
    let p = net.poller()
    let _ = p.listen(0)
    var turns = 0
    while true {
        for ev in p.wait(10) {                     // 10 ms, then look at the channel
            match ev {
                Data(id, text) => { let _ = p.send(id, text) }
                _ => {}
            }
        }
        turns += 1
        if stop.try_recv().is_some() { break }
    }
    turns
}

fn main(sys: Sys) {
    let (stop, stop_rx) = channel()
    let h = sys.workers().spawn(serve, (sys.net, stop_rx))
    stop.send("stop")
    sys.console.println("{h.join() > 0}")
}
```

(tests/v2/run/workers_event_loop.tn is a server worker with a client event
loop in `main`.)

**In the interpreter** (`tenon run`) workers take turns on one thread, with
the same results as `tenon build` for every program whose output does not
depend on scheduling, but slower (docs/tools.md, `tenon run`). Use
`tenon build` for speed.

**Costs** (C backend, Apple M4 Max; compiler/iwork.tn and runtime/tenon.h for
the implementation):

- Copying a value to another worker costs about its size: 0.6 ns per `Int`
  of a list, 12 ns per string (one allocation each), 18 ns per map entry
  (measured with lists of 1,000,000 `Int`s and 100,000 strings, and a map of
  100,000 entries). A value shared twice inside the sent value is copied
  twice. Send a few large messages (chunks) rather than many small ones.
- A message round trip to another worker and back takes about 4.5 µs (the
  receiver sleeps when the channel is empty); starting and joining a worker
  about 18 µs.
- A program that starts workers is compiled for threads: its allocator state
  is thread-local and its output locked. Single-threaded code in such a
  program runs at most a few percent slower (bench/trees 5%, bench/v2/pwords
  3%, bench/v2/mandel 0%); programs without workers are unchanged.
- Speedups over the same function on one thread (`python3 ops/evidence/bench.py
  --parallel`; 16 cores): bench/v2/mandel (floating point) 1.96x on 2
  workers, 3.62x on 4, 6.9x on 8; bench/v2/pwords (strings and maps,
  allocating; maps copied back) 1.92x, 3.51x, 6.2x.
- Each worker has its own stack of 256 MB (reserved, committed as used) and
  keeps at most 64 MB of freed blocks for reuse; `main` has 1 GB.

## 19. Not yet implemented

Bounded channels, waiting on several channels at once, and a channel that a
`Poller` reports like a socket; see `docs/log.md`.
