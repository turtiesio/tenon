# Tenon language reference

This is the single source document for the language. It is also the only
documentation given to authors in the usability study, so it must be enough to
write real programs. Builtin APIs are listed in [`src/prelude.tn`](../src/prelude.tn),
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
- Statements end at a newline (or `;`). A line that begins with `.` or `else`
  continues the previous line, and so does anything inside `( )` or `[ ]`.
- Names: types and enum variants start with an uppercase letter; functions,
  variables and fields start with a lowercase letter. The compiler enforces this.
- Literals: `42`, `1_000`, `3.14`, `1e-9`, `true`, `false`, `"text"`.
  Escapes: `\n \t \r \0 \\ \" \{ \}`. `"{expr}"` interpolates any value (see §8); write `\{` for a literal `{` (a lone `}` is literal).
- `()` is the only value of type `Unit`.

## 3. Types

| Type | Meaning |
|---|---|
| `Int` | 64-bit signed integer. Overflow **traps**. |
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

## 4. Declarations

```tenon
struct Point { x: Int, y: Int }
struct Pair[A, B] { first: A, second: B }

enum Shape { Circle(Int), Rect(Int, Int), Empty }
enum Tree[T] { Leaf, Node(Tree[T], T, Tree[T]) }   // recursion through enums is fine

fn area(s: Shape) -> Int { ... }                    // return type Unit if omitted
fn largest[T](xs: List[T]) -> Option[T] { ... }      // generic function

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

## 5. Functions and closures

The last expression of a block is its value. `return` exits early.

```tenon
fn fib(n: Int) -> Int { if n < 2 { n } else { fib(n - 1) + fib(n - 2) } }

let add = fn(a: Int, b: Int) -> Int { a + b }   // closure, full form
let inc = fn(x) => x + 1                         // short form; types inferred from use
let names = people.map(fn(p) => p.name)
```

Closures capture variables **by value** at creation; they cannot assign to
captured variables. Named functions and variants can be used as values:
`xs.map(Some)`, `words.map(Str.len)`.

## 6. Variables and mutation

- `let x = ...` is immutable; `var x = ...` is mutable. Types are inferred;
  annotate with `let x: List[Int] = []` when needed.
- Names may not be redeclared inside a function (no shadowing).
- Assignment targets: `x = v`, `p.field = v`, `xs[i] = v`, `m[k] = v`
  (inserts or replaces), and compound forms `+= -= *= /= %=`.
- Mutating methods (`push`, `insert`, `sort`, user methods with `mut self`)
  need a mutable place: a `var`, or a field/element of one.

## 7. Control flow

```tenon
if a > b { ... } else if a == b { ... } else { ... }   // also an expression
while cond { ... }
for i in 0..n { ... }            // half-open range
for x in xs { ... }              // over a snapshot of the list
for (k, v) in m { ... }          // over map entries in insertion order
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

Patterns: `_`, a name, literals (`3`, `-1`, `"text"`, `true`), tuples
`(a, b)`, variants `Some(x)` / `Shape.Rect(w, h)`, and alternatives `p | q`
(each alternative binds the same names). `let (a, b) = pair` and
`for (k, v) in m` take patterns that always match.

`if` without `else`, and statements in general, must produce `Unit`: a value
cannot be silently dropped. Discard explicitly with `let _ = expr`.

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

Bugs are **traps**: integer overflow, division by zero, index out of bounds,
missing map key in `m[k]`, `unwrap()` on `None`/`Err`, `panic(msg)`, failed
`assert(cond)`. A trap prints `trap: <message>` and `at file:line:col` to
stderr and exits. Traps cannot be caught.

`main` returns `Unit` or `Result[Unit, E]`; returning `Err(e)` prints
`error: <e>` to stderr and exits with code 1.

Reserved exit codes:

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | `main` returned `Err` |
| 70 | trap |
| 71 | out of memory |
| 72 | stack overflow |
| 74 | standard output could not be written |

## 10. Capabilities (authority)

A program can only affect the outside world through capabilities, and the only
source of capabilities is the `Sys` value passed to `main`:

```tenon
struct Sys { console: Console, fs: Fs, clock: Clock, args: List[Str] }
```

There are no global functions for I/O, no ambient file system access, and no
way to construct a capability. Functions that need authority take it as a
parameter, so a signature shows what a function can touch. Attenuate before
passing on:

```tenon
let data = sys.fs.within("data")      // can only reach paths under data/
let ro = data.read_only()             // and only read them
```

An attenuated `Fs` rejects absolute paths and `..` (`Err(Denied(..))`).
`Fs.write` replaces a file atomically and durably (temp file, fsync, rename);
`Fs.append` is durable (fsync). I/O failures are `Err(IoError)`:
`NotFound(path)`, `Denied(path)`, or `Failed("path: reason")`.

## 11. Builtin API

See [`src/prelude.tn`](../src/prelude.tn) for the full list with signatures.
Highlights:

- `Str`: `len byte slice find split lines words trim trim_start trim_end
  starts_with ends_with contains to_int to_float upper lower replace chars
  repeat pad_left pad_right is_empty`; `Int.char()` makes a one-character string.
- `List[T]`: `len push pop insert remove clear slice sort sort_by reverse get
  first last index_of contains extend sorted reversed map filter any all count
  is_empty`, `+` concatenates; `List[Str].join`, `List[Int].sum`.
- `Map[K, V]`: `m[k]` (traps if missing), `get` (Option), `get_or`, `insert`,
  `remove`, `contains`, `keys`, `values`, `entries`, `len`, `is_empty`.
- `Option[T]`: `unwrap expect unwrap_or is_some is_none map ok_or`.
- `Result[T, E]`: `unwrap expect unwrap_or is_ok is_err ok map_err`.
- `Int`: `abs min max to_float to_str char`; `Float`: `to_int floor ceil round
  sqrt abs min max`.
- `Console`: `print println eprintln read_line read_all`.
- `Fs`: `read write append exists remove list mkdir within read_only`.
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

- A module is a file; `import name` makes its public items available as
  `name.item` (functions, types, `name.Type.function`) and the variants of its
  public enums by their plain names.
- Items are private unless declared `pub`; struct fields are private unless
  marked `pub`. Outside its module, a struct with private fields cannot be
  built, and its private fields cannot be read. Derived formatting shows a
  foreign type's private fields as `..`.
- Methods of a type can only be defined in the module that defines the type.
  Together with privacy this makes a module the only place that can create a
  value of its type or finish a linear one: privacy is unforgeability.
- Standard library modules: `journal` (append-only, checksummed, crash-safe
  record log; see `std/journal.tn`).

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

## 16. Not yet implemented

Concurrency (one connection at a time today); see `docs/log.md`.
