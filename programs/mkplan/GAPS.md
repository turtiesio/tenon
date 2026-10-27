# mkplan: language gaps and friction

No compiler bugs found: the interpreter and the native build produced identical
transcripts on the first run.

## 1. Two exit statuses with `error:` reporting

**Wanted:** `fn main(sys: Sys) -> Result[Unit, Str]` for `?`-style error handling
(exit 1, `error: ...` on stderr) *and* exit status 2 for usage errors.
`Result[Unit, E]` can only give 1, and `Int` gives no `?`/`error:` printing.

**Did instead:** `main` returns `Int`; the real work is in `fn plan(sys: Sys) -> Result[Unit, Str]`
and `main` prints `mkplan: {e}` itself and returns 1 on `Err`.

```tenon
fn main(sys: Sys) -> Int {
    match plan(sys) {
        Ok(_) => 0,
        Err(e) => { sys.console.eprintln("mkplan: {e}"); 1 }
    }
}
```

(The `mkplan:` prefix therefore differs from the `error:` prefix `main -> Err` would print.)

## 2. Cycle path needs manual path threading

**Wanted:** a way to hold a "current DFS path" without passing it through every
recursive call. **Did instead:** pass `path: List[Str]` and build `path + [name]`
per call (a copy each time, fine at this scale). Not a real obstacle; noted only
because function parameters are immutable and closures cannot assign captured
variables, so a shared mutable stack is not expressible.

## 3. Undocumented-but-worked (docs gap, minor)

Things I had to try rather than read: `if self.visit(dep, here)? { ... }` (using
`?` inside an `if` condition in a `mut self` method), and closures capturing
`self` (`self.reached.filter(fn(i) => self.rebuild[...])`). Both work; the
reference does not say that `?` is allowed in any expression position or that
closures may capture `self`.
