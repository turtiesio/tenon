# Tenon quick start for Python and TypeScript programmers

One page, to read before docs/reference.md. Every snippet comes from
tests/run/quickstart.tn (the trait rows from tests/v2/run/quickstart_traits.tn,
the worker rows from tests/v2/run/quickstart_workers.tn),
which the test suite runs on both backends.

## A whole program

```tenon
struct Item { name: Str, qty: Int }

enum Cmd { Add(Str, Int), Remove(Str), List }

fn parse(line: Str) -> Result[Cmd, Str] {
    let w = line.words()
    if w.is_empty() { return Err("empty command") }
    match w[0] {
        "add" => {
            if w.len() != 3 { return Err("usage: add NAME QTY") }
            let Some(q) = w[2].to_int() else { return Err("bad quantity '{w[2]}'") }
            Ok(Add(w[1], q))
        }
        "remove" => if w.len() == 2 { Ok(Remove(w[1])) } else { Err("usage: remove NAME") },
        "list" => Ok(List),
        other => Err("unknown command '{other}'"),
    }
}

fn main(sys: Sys) -> Int {
    let con = sys.console
    var stock: Map[Str, Int] = [:]
    var errors = 0
    while let Some(line) = con.read_line() {
        match parse(line) {
            Ok(Add(name, q)) => stock[name] = stock.get_or(name, 0) + q,
            Ok(Remove(name)) => {
                if let Some(q) = stock.remove(name) { con.println("removed {q} {name}") } else { con.println("no {name}") }
            }
            Ok(List) => {
                var items = stock.entries().map(fn(e) => Item { name: e.0, qty: e.1 })
                items.sort_by_desc(fn(it) => it.qty)
                for (i, it) in items.enumerate() {
                    con.println("{i + 1}. {it.name.pad_right(6, " ")}{it.qty}")
                }
            }
            Err(msg) => {
                con.eprintln("error: {msg}")
                errors += 1
            }
        }
    }
    if errors > 0 { 1 } else { 0 }
}
```

## Running it

Save the program as `stock.tn`, then:

```sh
printf 'add apple 3\nlist\n' | tenon run stock.tn    # interpret it: prints "1. apple 3"
tenon build stock.tn -o stock                        # compile it to a native executable
printf 'add apple 3\nlist\n' | ./stock               # the same output, faster
tenon check stock.tn                                 # type-check only
tenon fmt stock.tn                                   # rewrite it in the canonical layout
```

A test is a program in a `run/` directory with the expected output next to
it: `t/run/stock.tn` starting with `// stdin: add a 1\nlist`, then
`tenon test t --bless` writes `t/run/stock.out` and `tenon test t` compares
both backends with it. `tenon` comes from `ops/repo/install.sh` (or
`target/tenon` in the repository, built by `./check`); every command is in
[docs/tools.md](tools.md).

## Translation table

| Python / TypeScript | Tenon |
|---|---|
| `x = 1` / `const x = 1` | `let x = 1` (immutable) |
| `not`, `and`, `or` / `!`, `&&`, `\|\|` | `not`, `and`, `or` |
| `x = 1` then `x += 1` / `let x` | `var x = 1` then `x += 1` |
| `def f(a: int) -> str:` | `fn f(a: Int) -> Str { ... }`; the last expression is the result |
| `print(x)` / `console.log(x)` | `sys.console.println("{x}")`; `main` receives `sys: Sys` |
| `sys.argv[1:]` / `process.argv.slice(2)` | `sys.args` (program name excluded) |
| `sys.exit(2)` | `fn main(sys: Sys) -> Int` and return the code |
| `print(..., file=sys.stderr)` | `con.eprintln(...)` |
| `for line in sys.stdin:` | `while let Some(line) = con.read_line() { ... }` (no `"\n"`, and one `"\r"` removed) |
| `f"{a} and {b!r}"` / `` `${a}` `` | `"{a} and {b}"`; a literal brace is `\{` |
| `f"{x:>5}"`, `f"{n:08x}"`, `f"{f:.2f}"` | `"{x:>5}"`, `"{n:08x}"`, `"{f:.2}"` (no `f`); `<` `^` fill `{x:*^9}`, `{n:05}`, `{n:X}` `{n:b}` `{n:o}`, widths in code points |
| `f"{n:,}"`, `f"{f:12,.2f}"` | `"{n:,}"`, `"{f:12,.2}"` (Int and Float; not with `x` `b` `o`) |
| `int(s)` | `s.to_int()` gives `Option[Int]`: `let Some(n) = s.to_int() else { ... }` |
| `int(s, 16)`, `hex(n)` | `s.to_int_radix(16)`, `n.to_str_radix(16)`; literals `0xFF 0b1010 1_000` |
| `s.split()` / `s.split(",")` | `s.words()` / `s.split(",")` |
| `s.strip()`, `s.startswith(p)` | `s.trim()`, `s.starts_with(p)`; also `strip_prefix` gives `Option` |
| `s.strip("0")`, `s.rstrip("0")`, `s.lstrip("0")` | `s.trim_chars("0")`, `s.trim_end_chars("0")`, `s.trim_start_chars("0")` |
| `text.splitlines()` | `text.lines()` (no `"\n"`, and one `"\r"` removed, like `read_line`) |
| `a, _, b = s.partition("=")` | `let Some((a, b)) = s.split_once("=") else { ... }` |
| `ord(c)`, `s[i]` as a byte | `'a'` is an `Int` code point; `s.byte(i)`; `s.chars()` |
| `chr(c)`, `c.isdigit()` | `c.char()` (a one-character `Str`); `c.is_digit()` `is_alpha` `is_alnum` `is_upper` `is_lower` `is_space` (ASCII, on code points) |
| `all(c in ok for c in s)` | `s.all_bytes(fn(b) => b.is_lower() or b.is_digit() or b == '_')` |
| `len(s)`, `s.rjust(8, ".")` | `s.len()` is **bytes**; `s.char_count()` code points; `s.pad_left(8, ".")` / `pad_right` pad to code points |
| `bisect.bisect_left(xs, x)` | `xs.binary_search(x)` gives `Ok(i)` (found) or `Err(i)` (insertion point) |
| `[f(x) for x in xs if p(x)]` | `xs.filter(fn(x) => p(x)).map(fn(x) => f(x))` |
| `xs[:] = [x for x in xs if p(x)]` | `xs.retain(fn(x) => p(x))` (in place, on a `var`) |
| `for i, x in enumerate(xs)` | `for (i, x) in xs.enumerate()` |
| `for i in range(n)` | `for i in 0..n` |
| `for i in reversed(range(n))` | `for i in rev_range(0, n)` (`n - 1` down to `0`) |
| `sorted(xs, key=k, reverse=True)` | `xs.sort_by_desc(fn(x) => k(x))` on a `var` list (stable) |
| `max(xs, key=k)` / `min(xs, key=k)` | `xs.max_by(fn(x) => k(x))` / `xs.min_by(...)` give `Option[T]` (`None` if empty; first of equal keys) |
| `defaultdict(list)` grouping, `itertools.groupby` | `xs.group_by(fn(x) => k(x))` gives `Map[K, List[T]]`: all equal keys (not only adjacent), keys in first-occurrence order |
| `d = {}`; `d[k] = d.get(k, 0) + 1` | `var d: Map[Str, Int] = [:]`; `d[k] = d.get_or(k, 0) + 1` |
| `d.setdefault(k, []).append(x)` | `d.or_insert(k, [])` then `d[k].push(x)` (in place) |
| `if k in d` / `d.get(k)` | `d.contains(k)` / `d.get(k)` gives `Option` |
| `for k, v in d.items()` | `for (k, v) in d.entries()` (insertion order) |
| `set()`, `heapq` | `var s: Set[Int] = Set.new()`, `Heap` |
| `None` / `null` | `Option[T]`: `Some(x)` / `None` |
| exceptions | `Result[T, E]`: `Ok(x)` / `Err(e)`; `expr?` returns the `Err` early |
| `class P: ...` | `struct P { x: Int }`; methods `fn P.norm(self) -> Int` |
| `class Shape(ABC)` with `@abstractmethod def area(self)`, `typing.Protocol` / `interface Shape { area(): number }` | `trait Shape { fn area(self) -> Int }`, then `impl Shape for Circle { fn area(self) -> Int { ... } }` (§17 of the reference) |
| `def total(xs: list[T])` with `T` bound to Shape / `function total<T extends Shape>(xs: T[])` | `fn total[T: Shape](xs: List[T]) -> Int`; several bounds `T: Shape + Show` |
| `list[Shape]` of different classes / `Shape[]` | `let shapes: List[dyn Shape] = [dyn Shape(c), dyn Shape(Circle { r: 2 })]` (the conversion is written) |
| `__str__` / `toString()` | `impl Show for Pt { fn to_str(self) -> Str { "Pt({self.x})" } }`; used by `"{p}"` everywhere |
| `ProcessPoolExecutor().map(f, xs)`, `Pool().map(f, xs)` / a `worker_threads` pool | `let w = sys.workers()` then `w.par_map(xs, f)`: the same list as `xs.map(f)`, computed on all cores (§18 of the reference) |
| `executor.submit(total, xs).result()` / `new Worker(...)` + `once('message')` | `let h = w.spawn(total, xs)` then `h.join()` gives the result; the argument and result are copied, nothing is shared |
| `multiprocessing.Queue()`, `queue.Queue()` / `MessageChannel`, `postMessage` | `let (tx, rx) = channel()`; `tx.send(x)`; `while let Some(x) = rx.recv() { ... }` ends after `tx.close()` |
| `P(x=x, y=0)` / `{ x, y: 0 }` | `P { x, y: 0 }` (`x` alone means `x: x`) |
| method that mutates | `fn P.bump(mut self)`; call it on a `var` |
| tagged union / `match` | `enum Cmd { Add(Str, Int), List }` and exhaustive `match` |
| `lambda x: x + 1` / `x => x + 1` | `fn(x) => x + 1` |
| `r"\d{4}"` / `` String.raw`\d{4}` `` | `r"\d{4}"`: raw string, no escapes, `{...}` is literal; cannot contain `"` |
| `re.fullmatch(r"(\d{4})-(\d{2})", s)` | `import regex` then `regex.compile(r"(\d{4})-(\d{2})").unwrap().full(s)` gives `Option[List[Str]]` (groups) |
| `open(p).read()` | `sys.fs.read(p)` gives `Result[Str, IoError]` (`Err` if not UTF-8) |
| `open(p, "rb").read()`, `sys.stdin.buffer.read()` | `sys.fs.read_bytes(p)` gives `Result[List[Int], IoError]` (each 0..255); `con.read_all_bytes()`; `Str.from_utf8(bs)` |

## Rules that surprise newcomers

- **No shadowing.** A name can be bound once per function, and that includes
  pattern bindings: `let v = ...; match v { Some(v) => ... }` is an error. Pick
  a new name (`Some(x)`).
- **Values are not silently dropped.** A call whose result you ignore needs
  `let _ = f()`.
- **Changing a caller's variable** takes an explicit `mut` on both sides:
  `fn fill(out: mut List[Int])` and `fill(mut xs)`.
- **`if` is an expression.** Both branches must have the same type, and an `if`
  without `else` is `()`. `match` must cover every case; use `_ => ...` for the rest.
- **Integers are 64-bit and overflow traps.** Use `checked_add`, `checked_mul`
  and the like to get `Option` instead. `INT_MIN` and `INT_MAX` are in the prelude.
- **Files and the network need a capability** from `sys` (`sys.fs`, `sys.net`).
  A function that does not receive one cannot touch them.
- **Workers share nothing.** What you send or pass to `spawn` is copied (a
  unique value moves), and a channel ends only when someone calls `close()`:
  dropping the senders does not end `recv()` loops.
- **Building a big string:** `out += piece` on a `var` appends in place. To
  build across functions, pass the buffer down: `fn emit(out: mut Str, ...)`.
