# Self-hosted C backend: notes

`selfhost/tenonc.tn` is the self-hosted compiler driver:

    tenonc check FILE [ROOT]                 = selfhost/check.tn (`ok` or the first diagnostic)
    tenonc emit FILE [--root DIR]            = `tenon emit FILE`, byte for byte
    tenonc build FILE [-o OUT] [-O0] [--root DIR]

Its C backend is a second, independent implementation of
bootstrap/src/emit_c.rs, emit_body.rs, emit_ctl.rs and emit_builtins.rs,
working from the self-hosted checker's results (`checker.Checked`: the
program, the declarations and the type, resolution and capture side tables).

## Modules

| Module | Ports | Contents |
|---|---|---|
| `tenonc.tn` | main.rs, emit_c.rs `build`/`compile` | subcommands, reading the runtime, running the C compiler |
| `front.tn` | main.rs `front` | loading the prelude and modules, checking (shared with check.tn) |
| `emit.tn` | emit_c.rs, helpers of emit_body.rs | emitter state, C type names, boxing, scopes and temporaries, the driver |
| `emitlayout.tn` | emit_c.rs | type definitions in dependency order, per-type helpers, decoders, `main`, assembly |
| `emitbody.tn` | emit_body.rs | function instances, statements, loops, places, assignment, expressions, calls |
| `emitctl.tn` | emit_ctl.rs | patterns, `match`, `?`, closures, function values |
| `emitbi.tn` | emit_builtins.rs | the prelude's `extern fn`s |

Methods can only be defined in the module of their type, so `Em` (the state)
has its core helpers as methods in emit.tn and the other modules are free
functions taking `m: mut emit.Em`. The modules import each other in a cycle
(emit -> emitbody -> emitctl -> emitbody), which the language allows.

## Inputs read at compile time

The bootstrap embeds lib/prelude.tn, lib/std/*.tn and runtime/tenon.h
(`include_str!`). tenonc reads them from the repository ROOT when it compiles
a program: `--root DIR`, else `$TENON_ROOT`, else the current directory
(`check` takes ROOT as its second argument, as check.tn does). The runtime is
pasted into the C exactly as the bootstrap pastes it, so the output does not
depend on where it was read from.

`build` uses the `Proc` capability (lib/prelude.tn, docs/reference.md §11) to
read `$CC` and `$TENON_KEEP_C` and to run `$CC OPT -w -std=gnu11 -pthread -o OUT
OUT.c -lm`, as the bootstrap does. Differences from `tenon build`: no build
cache, and messages start with `tenonc:`.

## Fidelity rules that matter for identical C

- Every fresh name (`t12`, `r3`, `f_main_4`, `t7_Point`) comes from one
  counter, so every call that allocates a name or a type name happens in the
  bootstrap's order, including the ones whose result is discarded (`tn =
  cty(t)` at the top of every extern call). Rust evaluates `format!`
  arguments left to right; the port binds them to locals in that order.
- Function instances are emitted from a stack (last queued first), as
  `fn_queue.pop()`; lambdas and wrappers write their bodies before the
  function that creates them.
- Float literals print as Rust's `{:e}` (`1.5e0`, `1e-3`): `emit.float_lit`
  rewrites the shortest round-trip text of `Float.to_str`.
- `may_mutate` gives the same answer as the bootstrap's walk (an `Assign`
  among the direct statements of a block or `if`, a `mut self` method call,
  anywhere except inside a lambda) without its repeated visits of nested
  blocks, which are exponential in the nesting depth.
- Polymorphic recursion: the bootstrap exits at the first type deeper than 48
  or function instance deeper than 24; the port records the message, stops
  growing types (also in `is_boxed` and `trivial`, which the bootstrap never
  reaches for such types) and exits with status 1 and no output, as the
  bootstrap does.

## What the checker had to add

- Literal values in its tree (`XInt(Int)`, `XFloat(Float)`, the literal
  segments of strings: `XStr(exprs, segments)`); the checker ignored them.
- `check` returns `Checked` instead of `Unit`; no diagnostic changed.
- Calling a constant (`const F: fn(Int) -> Int`, `F(3)`) is a call through a
  function value (`RCallValue`), as in the bootstrap (tests/run/const_shadows_variant.tn).

## Testing

- `tools/selfhost.sh` (in `./check`): for every corpus file the bootstrap
  accepts, `tenon emit` and `tenonc emit` print the same bytes and exit with
  the same status (306 files).
- `tools/fixpoint.sh` (in `./check`): stage1 (the bootstrap building
  tenonc.tn) and stage2 (stage1 building tenonc.tn) emit identical C for
  tenonc.tn, equal to `tenon emit selfhost/tenonc.tn`, and stage2 emits the
  same C as stage1 for the whole accepted corpus.
- `selfhost/checkfuzz.py`: mutants that both compilers accept are also
  compared by their emitted C.

## Remaining for a fully self-hosted compiler (tenon.md §5)

Stage A (this port) is complete. Not done yet: the interpreter and `run`
(`tenon run`), `test` (the test runner), `tokens`/`ast` as tenonc subcommands
(they exist as selfhost/tokens.tn and astdump.tn), a build cache, running the
test suite and programs with tenonc as the compiler, and freezing the
bootstrap.
