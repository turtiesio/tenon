# Language gaps found while writing calc

Each entry: what I wanted, what I did instead, a minimal snippet. No interpreter/native
disagreements and no compiler crashes were found (`tools/programs.sh` transcripts match on
both backends).

## 1. No top-level constants

Wanted: named module-level constants (`max_depth`, `int_max`, ...).
Did instead: zero-argument functions (`fn max_depth() -> Int { 1000 }`, called as `max_depth()`).
The error is also unhelpful for someone who expects `let` at top level: it only says the
parser expected a declaration keyword.

```tenon
let max_depth = 1000
fn main(sys: Sys) { }
```
```
error: expected 'fn', 'struct' or 'enum', found 'let'
```
(The error does not mention `import` either, and the reference never says top-level `let` is not allowed.)

## 2. `_` is not accepted as a closure parameter

Wanted: ignore the (unused) error value in `map_err(fn(_) => "message")`.
Did instead: `fn(e) => "message"` with an unused name `e`. `_` works in `let _ =`, `for _ in`
and patterns, so this is an inconsistency, and the reference does not say so.

```tenon
fn main(sys: Sys) {
    let xs = [1, 2].map(fn(_) => 0)
    sys.console.println("{xs}")
}
```
```
error: expected a name, found '_'
```

## 3. No integer limit constants and no checked/wrapping arithmetic

Overflow traps and traps cannot be caught, so a calculator that must *report* overflow has
to pre-check every operation by hand. There is no `Int.max_value()` / `Int.min_value()`,
no `checked_add`/`checked_mul` returning `Option`, and the minimum Int cannot be written as a
literal.
Did instead: `int_max()`/`int_min()` helper functions, written as
`-9223372036854775807 - 1` for the minimum, and hand-written overflow tests for `+ - * / %`
and unary `-` (about 40 lines; the `*` case is the fiddly one: it needs the sign cases plus
special handling of `-1` because `MIN / -1` itself traps).

```tenon
fn main(sys: Sys) {
    let m = -9223372036854775808
    sys.console.println("{m}")
}
```
```
error: integer literal does not fit in Int (64-bit; the smallest Int is INT_MIN)
```

## 4. Discarding a value needs `let _ =` on every call (friction, not a bug)

A recursive-descent parser has many "advance and ignore the token" calls (`p.next()`), and a
statement cannot silently drop a value, so each one is written `let _ = self.next()` (about 25
occurrences). Documented and deliberate, but it is noise. I kept `let _ =` everywhere.

```tenon
let _ = self.next()
```

## 5. Documentation notes (not blockers)

- The reference says `main` may return `Unit`, `Int` or `Result`; this works for an `Int` exit
  status (used here: 0 / 1). Good.
- It is not stated whether a non-exhaustive `match` on a `Str` needs `_` (it does) or whether
  `break`/`continue` are allowed as a match-arm value (they are, §7 says "anywhere inside the
  loop body"; `let op = match k { A => Add, _ => break }` type-checks). Worth an example in §7.
- Deeply nested input (`((((...1...))))`) is bounded here by a nesting limit I added to the
  parser (200). Both backends handle that and a call depth of 1000 fine; I did not probe how
  deep the stack allows before the reserved stack-overflow exit (code 72).
