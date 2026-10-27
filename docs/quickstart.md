# Tenon quick start for Python and TypeScript programmers

One page, to read before docs/reference.md. Every snippet comes from
tests/run/quickstart.tn, which the test suite runs on both backends.

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
| `for line in sys.stdin:` | `while let Some(line) = con.read_line() { ... }` (no newline) |
| `f"{a} and {b!r}"` / `` `${a}` `` | `"{a} and {b}"`; a literal brace is `\{` |
| `int(s)` | `s.to_int()` gives `Option[Int]`: `let Some(n) = s.to_int() else { ... }` |
| `int(s, 16)`, `hex(n)` | `s.to_int_radix(16)`, `n.to_str_radix(16)`; literals `0xFF 0b1010 1_000` |
| `s.split()` / `s.split(",")` | `s.words()` / `s.split(",")` |
| `s.strip()`, `s.startswith(p)` | `s.trim()`, `s.starts_with(p)`; also `strip_prefix` gives `Option` |
| `a, _, b = s.partition("=")` | `let Some((a, b)) = s.split_once("=") else { ... }` |
| `ord(c)`, `s[i]` as a byte | `'a'` is an `Int` code point; `s.byte(i)`; `s.chars()` |
| `[f(x) for x in xs if p(x)]` | `xs.filter(fn(x) => p(x)).map(fn(x) => f(x))` |
| `for i, x in enumerate(xs)` | `for (i, x) in xs.enumerate()` |
| `for i in range(n)` | `for i in 0..n` |
| `sorted(xs, key=k, reverse=True)` | `xs.sort_by_desc(fn(x) => k(x))` on a `var` list (stable) |
| `d = {}`; `d[k] = d.get(k, 0) + 1` | `var d: Map[Str, Int] = [:]`; `d[k] = d.get_or(k, 0) + 1` |
| `d.setdefault(k, []).append(x)` | `d.or_insert(k, [])` then `d[k].push(x)` (in place) |
| `if k in d` / `d.get(k)` | `d.contains(k)` / `d.get(k)` gives `Option` |
| `for k, v in d.items()` | `for (k, v) in d.entries()` (insertion order) |
| `set()`, `heapq` | `var s: Set[Int] = Set.new()`, `Heap` |
| `None` / `null` | `Option[T]`: `Some(x)` / `None` |
| exceptions | `Result[T, E]`: `Ok(x)` / `Err(e)`; `expr?` returns the `Err` early |
| `class P: ...` / `interface` | `struct P { x: Int }`; methods `fn P.norm(self) -> Int` |
| method that mutates | `fn P.bump(mut self)`; call it on a `var` |
| tagged union / `match` | `enum Cmd { Add(Str, Int), List }` and exhaustive `match` |
| `lambda x: x + 1` / `x => x + 1` | `fn(x) => x + 1` |
| `re.fullmatch(...)` | `import regex` then `regex.compile(p).unwrap().full(s)` |
| `open(p).read()` | `sys.fs.read(p)` gives `Result[Str, IoError]` |

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
- **Building a big string:** `out += piece` on a `var` appends in place. To
  build across functions, pass the buffer down: `fn emit(out: mut Str, ...)`.
