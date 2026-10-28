# Self-hosted C backend: notes

`selfhost/tenonc.tn` is the self-hosted compiler driver; every `tenon`
subcommand has a tenonc equivalent (selfhost/SELFHOST.md). The C backend's:

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
OUT.c -lm`, as the bootstrap does, with the same kind of build cache
(selfhost/SELFHOST.md); its own messages start with `tenonc:`.

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

## Stage B

Stage A (this port) is complete. Stage B (the interpreter, the test runner,
`tokens`/`ast`, the build cache, the gates switched to tenonc, the frozen
bootstrap) is described in selfhost/SELFHOST.md.

## Traits (v2: tenonc only; selfhost/emittrait.tn)

None of this code runs for a program without traits, so the C of the whole
v1 corpus stays byte-identical to the bootstrap's (tools/selfhost.sh).

- **Bounds** are monomorphized: an `RTrait` call is resolved in each
  function instance by substituting the receiver's type
  (`ckenv.Env.method_for`: the impl's method, or the default with
  `Self` = the type) and emitted as the direct call of that instance.
- **`dyn T`** is `struct { tn_env *o; const void *vt; }`. `o` is a box
  `struct dboxN { tn_env h; V v; }` (the closure environment header, so
  `rc` and `drop` work as for closures), one box type per value type; `vt`
  points to `static const struct tN_vt vtK`, one per (trait, type): the
  box's formatter, then a wrapper per trait method (derived traits' methods
  are not in tables) that calls the impl's instance on the boxed value. The
  per-type helpers of a dyn type retain/release the box, format through the
  table, and stub eq/cmp/hash/dec (the checker forbids them).
- **Show impls**: when a declared type gets its C name (`Em.cty`), its Show
  impl's `to_str` instance is queued (`note_type`); the type's formatter
  starts with `if (!(mode & TN_FULL))` calling it, so every place that
  formats (interpolation, lists, maps, traps, `main`'s error) uses it and
  `encode` (TN_FULL) does not. Its prototype goes with the helper
  prototypes, which come before the functions'.

## Workers and channels (v2: tenonc only; emitbi.tn `worker_call`)

A program whose checker results resolve a call to `Sys.workers` (emit.tn
`uses_workers`, `Em.mt`) is compiled for threads; nothing changes for any
other program, so the v1 corpus stays byte-identical to the bootstrap's.

- The C starts with `#define TN_MT 1`, which switches runtime/tenon.h to its
  thread-safe form (one thread-local struct for the allocator lists, the
  release queue and `tn_cur_loc`; locked output and input; see the section
  "workers and channels" there).
- Every type gets `N_copy`, a deep copy that reads its argument without
  touching its counts (struct and tuple fields, enum payloads, `TN_LIST_COPY`
  and `TN_MAP_COPY` for lists and maps; builtin ones in tenon.h); closures'
  environments and `dyn` boxes get a `copy` function in their header. Boxed
  enums allocate from the free lists (no per-type pools, which would be
  thread-locals) and leave the shared nullary nodes' counts alone
  (`TN_RC_STATIC`). `println` is one locked write (`tn_writeln`).
- `Workers.spawn` copies the argument and the function, and starts a
  `tn_Worker` whose generated runner (`tn_runN`, per argument and result
  type) calls it on the new thread; `Worker.join` copies the result out;
  `channel` makes a `tn_Chan` with the element size and a release function
  (`tn_relpN`); `send` copies (`send_copy`; a retain in a program without
  workers, where channels are used by one thread).
