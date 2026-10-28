# The self-hosted compiler

Contributor notes on `tenon` (`selfhost/*.tn`), the one self-hosted
executable (tenon.md §5, "Fully self-hosted compiler"). Its user reference
is [docs/tools.md](../tools.md); how it is tested, built in stages and
cross-checked is in [testing.md](testing.md). This page records how each
part is built and which rules keep it identical to the frozen seed
(`bootstrap/`, `target/release/tenon-seed`, governance/README.md), which only
builds stage 0.

## Commands and modules

`selfhost/tenon.tn` is the driver. It has every subcommand of the seed, and
more:

| tenon | = tenon-seed | Implementation |
|---|---|---|
| `run FILE [ARGS...]` | `run` | interp.tn and the i*.tn modules ("The interpreter") |
| `build FILE [-o OUT] [-O0]` | `build` | emit*.tn ("The C backend"), the build cache in tenon.tn |
| `emit FILE` | `emit` (byte for byte) | emit*.tn |
| `check FILE` | `check` | front.tn, checker.tn, ck*.tn ("The checker") |
| `test DIR... [--bless]` | `test` | testrun.tn |
| `tokens FILE`, `ast FILE` | `tokens`, `ast` | lexer.tn `dump`, astdump.tn |
| `fmt [--check] FILE...`, `fmt -` | (none) | fmtcmd.tn, fmt.tn, fmtlayout.tn, fmtlex.tn |
| `lsp` | (none) | lsp.tn, lspquery.tn, lspindex.tn, lsppos.tn, json.tn |
| `fetch [DIR]` | (none) | pkg.tn, pkgtoml.tn ([docs/packages.md](../packages.md)) |

Each prints and exits with what the seed's subcommand does; the driver's own
messages (unreadable files, a failing C compiler, usage errors) start with
`tenon:`, as the seed's do. Flags may come in any position. Inside a package
(a `tenon.toml` at or above the file's directory), `run`, `build`, `emit`,
`check` and `test` resolve `import` also to the dependencies pinned in
`tenon.lock`, offline, from the cache (pkg.tn `context`, front.tn
`load_in`); the language server does the same.

The prelude, the standard library and the C runtime are read from the
toolchain root when a program is compiled (`--root DIR`, else `$TENON_ROOT`,
else found from the executable's own path, else the current directory:
docs/tools.md). The seed embeds the same files (`include_str!`), so the
runtime is pasted into the C exactly as the seed pastes it and the output
does not depend on where it was read from.

New language features (traits, workers) exist only here: the seed cannot
parse them, so code that uses them lives under `v2/` directories (lib/v2,
tests/v2, programs/v2, bench/v2), which the cross-checks skip.

## The checker

`tenon check FILE` (selfhost/tenon.tn) runs a second, independent
implementation of the bootstrap's front end after parsing: module loading
(bootstrap/src/main.rs `front`), bootstrap/src/check.rs,
bootstrap/src/check_expr.rs, bootstrap/src/exhaust.rs,
bootstrap/src/linear.rs and the Subst/unify code of bootstrap/src/types.rs.
It is silent on success and prints the first diagnostic as
`PATH:LINE:COL: error: MESSAGE`. `tools/selfhost.sh` compares it with
`tenon-seed check` on every `.tn` file of the corpus outside `v2/`. `checker.check` returns the
side tables the C backend uses (`Checked`; see "The C backend" below).
`checker.check_lenient` (used by the language server, selfhost/lsp.tn,
through `front.analyze_in`) reports the same first diagnostic but goes on
checking the other functions after one fails, so the side tables cover the
whole program while it is being edited.

### Modules

| Module | Ports | Contents |
|---|---|---|
| `front.tn` | main.rs `front` | reads the prelude and modules through `Fs`, parses, checks |
| `checker.tn` | check.rs `check` | the phases in the bootstrap's order; returns `Checked` |
| `ckast.tn` | ast.rs, check.rs `fix_paths`, `breaks` | checker syntax tree with file numbers and node ids |
| `cktypes.tn` | types.rs | `Ty`, substitution, unification (no rollback, as in the bootstrap) |
| `ckenv.tn` | check.rs `declare`, `resolve_type`, `lower_type`, ... | declarations, modules, privacy, `check_main` |
| `ckinfer.tn` | check.rs, check_expr.rs | function bodies |
| `ckexh.tn` | exhaust.rs | exhaustiveness and reachability |
| `cklin.tn` | linear.rs | linear/unique analysis, codec restrictions |

The parser (`parser.tn`) records the positions the checker reports: type
expressions, declarations, variants, parameters and imports.

### Fidelity rules that matter for exact messages

- Unification binds variables as it goes and never rolls back; a failed
  `unify` leaves partial bindings, and the message prints the resolved types
  afterwards. The argument order of every `unify` call follows the bootstrap.
- Diagnostics come from the first failing step in the bootstrap's order:
  type declarations (all structs, then all enums), recursion, kinds,
  function signatures, every function body in declaration order (prelude,
  main file, modules in load order), `main`, then the linear pass over all
  functions.
- Side tables are keyed by node id; the receiver invented by `fix_paths` for
  `Value.field` gets id `-1 - id` (the bootstrap uses `u32::MAX - id`).
- The linear pass's cache of "generic function accepts a linear argument"
  answers is shared across the whole pass, as the bootstrap's thread-local is.

- Hiding prelude items: a main-file item whose name the prelude also
  declares at top level gets the internal name `<main>.NAME`
  (`Env.internal`), and diagnostics print it that way. Unqualified variants
  of non-prelude enums hide prelude variants (`variant_by_name`). `panic`
  ends a `let ... else` block only when it resolves to the prelude's.

### Seed quirks reproduced on purpose

- `check_recursion` reports at the default span, rendered `<prelude>:0:0`.
- `breaks` (does a `while true` body contain a `break`?) also finds a
  `break` belonging to a loop nested inside an `if` or a block, because
  `visit_stmt` descends into nested loop bodies.
- An `if` without `else` appends "('if' without 'else' must produce Unit)" to
  any "type mismatch" raised anywhere inside its block.

- `module.Type.Variant` used as a value (not called) is not rewritten by
  `fix_paths`, so it reports `unknown name 'module'`
  (tests/selfhost/mod_variant_member.tn); `module.Variant(..)` becomes a path
  call and reports `'module' has no member 'Variant'`
  (tests/selfhost/mod_module_variant_call.tn).
- `muts` (which parameters are `mut`) excludes `self`, but a method used as a
  function value (`Type.method(recv, ..)`) indexes it against the full
  parameter list including `self`; the self-hosted checker indexes the same way.
- A `ref`/`mut` parameter flag is looked up by parameter name in the linear
  pass, so `mut` parameters count as borrowed: consuming one reports the
  `'ref' parameter` message (tests/selfhost/lin_mut_param.tn).

- Rules added to the bootstrap from QA findings are implemented: round 1
  (commit 7609370: comparability through fields and payloads, Float/function
  map keys, linear temporaries, guards that consume, `..` dropping a replaced
  linear field) and round 2 (commit 7abe2a9: ordering maps, un-inferable
  `let` types, constant cycles, `self` exemption only for linear/unique
  owners).

### Known disagreements

None on the corpus. Files skipped by `tools/selfhost.sh` would be listed here
with a minimal reproduction.

### Traits (v2)

The language: docs/reference.md §17. Tested by `tenon test tests/v2`, never
cross-checked (the seed cannot parse them).

- **Front end.** parser.tn: `trait`, `impl[..] T for Type`, bounds in
  `[T: A + B]` (`FnDecl.bounds`), `dyn Name` types (a `Named("dyn Name")`)
  and `dyn Name(x)` (`EDyn`). ckast.convert turns every impl method into a
  function (`Origin` `OImpl(i)`: owner the impl's type, type parameters the
  impl's then its own, bounds the impl's then its own) and every default
  body into a function generic in `Self` bounded by its trait
  (`ODefault(t, m)`), appended after the file's functions. lib/v2/prelude.tn
  (Eq, Ord, Hash, Show) is appended to the prelude's text by front.gather.
- **Declarations** (ckenv): traits are a namespace of their own
  (`trait_ix`, internal names like types'), registered before the types (a
  field may be `dyn T`), their methods' signatures lowered after them;
  `declare_impls` checks each impl (the trait's methods and signatures,
  missing and extra methods, the orphan rule, overlap with every earlier
  impl by unifying the targets with their parameters renamed apart) and
  records `ImplInfo.fns`: per trait method the function, the impl's or the
  default. Impl and default functions are not in `fn_ix`, so they never
  clash with a type's own methods (which win at a call).
- **Bodies** (ckinfer): a method call on a type parameter looks in its
  bounds, on a `dyn` value in its trait (`RTrait(trait, method, receiver
  type, method type args)`: resolved per instance by the backends); on any
  other type, when the type has no method of the name, in the impls whose
  target unifies with the receiver (on a copy of the substitution: exactly
  one may), giving an ordinary `RMethod` of the impl's function. Bounds are
  checked after the body (`pbounds`), when the types are known:
  `ckenv.implements` (a type parameter has the bounds it declares; derived
  traits structurally; otherwise an impl whose target matches, and its
  bounds recursively). `cklin`: a trait call with `self` consumes its
  receiver; `dyn` cannot hold linear or unique values; an impl method's
  `self` is exempt only in the type's own module.

### Workers and channels (v2)

docs/reference.md §18; the API is in lib/v2/prelude.tn (`extern fn`s with
bounds, `Workers.par_map` in Tenon).

- **Types:** `Workers` (a capability), `Sender[T]`, `Receiver[T]` and
  `Worker[R]` are builtin types (cktypes `builtin_arity`, `is_capability`:
  not comparable, not encodable, not in `dyn`). The three handles are
  `is_shared_handle`: `kind_walk` does not look into their type argument, so
  `Sender[Token]` of a unique `Token` is a plain, copyable value.
- **Send** is a derived trait (`builtin_trait_name`): `Env.implements` asks
  `unsendable_part`, which walks tuples, struct fields, enum payloads and
  type arguments (not into the shared handles) and names the first linear
  type or socket handle (Poller, Listener, Conn). The bound failure appends
  that reason. Every other type is Send, functions and `dyn` values
  included: closures and `dyn` values cannot hold linear or unique values.
- **cklin:** the worker externs consume a generic argument exactly once
  (`worker_extern` in `extern_ok`), so unique values may be sent or spawned
  and are then moved; `Workers.spawn` with a non-plain result type is
  refused (`a worker cannot return the unique type ...`).

## The C backend

`tenon emit` and `tenon build` use a second, independent implementation of
bootstrap/src/emit_c.rs, emit_body.rs, emit_ctl.rs and emit_builtins.rs,
working from the self-hosted checker's results (`checker.Checked`: the
program, the declarations and the type, resolution and capture side tables).

### Modules

| Module | Ports | Contents |
|---|---|---|
| `tenon.tn` | main.rs, emit_c.rs `build`/`compile` | subcommands and flags, reading the runtime, running the C compiler |
| `front.tn` | main.rs `front` | loading the prelude and modules, checking |
| `emit.tn` | emit_c.rs, helpers of emit_body.rs | emitter state, C type names, boxing, scopes and temporaries, the driver |
| `emitlayout.tn` | emit_c.rs | type definitions in dependency order, per-type helpers, decoders, `main`, assembly |
| `emitbody.tn` | emit_body.rs | function instances, statements, loops, places, assignment, expressions, calls |
| `emitctl.tn` | emit_ctl.rs | patterns, `match`, `?`, closures, function values |
| `emitbi.tn` | emit_builtins.rs | the prelude's `extern fn`s |

Methods can only be defined in the module of their type, so `Em` (the state)
has its core helpers as methods in emit.tn and the other modules are free
functions taking `m: mut emit.Em`. The modules import each other in a cycle
(emit -> emitbody -> emitctl -> emitbody), which the language allows.

### Building

`build` uses the `Proc` capability (lib/prelude.tn, docs/library.md) to
read `$CC` and `$TENON_KEEP_C` and to run `$CC OPT -w -std=gnu11 -pthread -o OUT
OUT.c -lm`, as the bootstrap does, with the same kind of build cache
("The build cache"); its own messages start with `tenon:`. Unlike the
bootstrap, a program with more than 400 kB of function definitions (`tenon`
itself: 6 MB of C) is compiled as up to 8 translation units by parallel
`$CC` runs and then linked (`emit.CParts`, tenon.tn `compile`; the
runtime's state is shared through `TN_STATE` in runtime/tenon.h): cc -O2 on
tenon.tn takes about 3 s instead of 13 s. `emit` and the cache still see one
C text.

### Fidelity rules that matter for identical C

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

### What the checker had to add

- Literal values in its tree (`XInt(Int)`, `XFloat(Float)`, the literal
  segments of strings: `XStr(exprs, segments)`); the checker ignored them.
- `check` returns `Checked` instead of `Unit`; no diagnostic changed.
- Calling a constant (`const F: fn(Int) -> Int`, `F(3)`) is a call through a
  function value (`RCallValue`), as in the bootstrap (tests/run/const_shadows_variant.tn).

### Traits (v2, selfhost/emittrait.tn)

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

### Workers and channels (v2, emitbi.tn `worker_call`)

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

## The interpreter

A port of bootstrap/src/interp.rs, builtins.rs, value.rs and codec.rs:

| Module | Ports | Contents |
|---|---|---|
| `interp.tn` | interp.rs `run` | names for formatting, the `Sys` value, `main`'s result and exit status |
| `ival.tn` | value.rs | values, map keys, equality, ordering, formatting, format specs |
| `icode.tn` | (resolution done once) | the checked tree lowered to frame slots, resolved calls, builtins numbered by `ibuiltin.table` |
| `ieval.tn` | interp.rs | statements, expressions, calls, places, patterns, traps |
| `ibuiltin.tn` | builtins.rs | numbers, strings, lists, maps, Option/Result, console |
| `icap.tn` | builtins.rs | Fs, Net (blocking and the event loop), Clock, Proc |
| `icodec.tn` | codec.rs | the strict decoder |

Design:

- A value (`ival.Val`) is one struct whose fields are used according to its
  kind, so a part deep inside a value is changed in place through `mut`
  places (`nav(mut v.xs[i], ...)`). Lists and maps are Tenon's own
  copy-on-write values; the language's value semantics (a `var` copy, a
  closure's capture, an argument) follow from Tenon's.
- Map keys are `ival.Key`, an exact hashable form of a key value (the checker
  allows no floats, functions or capabilities in keys); maps keep insertion
  order as the bootstrap's do.
- Names are resolved once to frame slots (no shadowing, so a name has one
  slot per function); calls know their target, and each builtin is resolved by name to its
  variant (`ibuiltin.Bi`; the one table is `ibuiltin.table`, with
  `icap.table` and `iwork.table`), so adding one shifts no other.
- Evaluation order, `mut` arguments (taken out of their places, written back
  after the call), the prelude call site used for trap locations, the depth
  limit (20000 calls: `trap: stack overflow`, status 72), the exit status of
  `main` and the trap messages are the bootstrap's. A builtin's trapping
  precondition is checked before the host builtin runs, so the trap is the
  program's.
- Capabilities are the interpreter's own: an `Fs` value is a host `Fs`
  (`within` and `read_only` make new ones), so jail, symlink and read-only
  rules are the C runtime's, which agree with the bootstrap's. The program's
  exit status (also 70 and 72) is passed on with `Proc.exit`.

Traits (v2, docs/reference.md §17): functions whose type parameters have a
bound other than the derived traits, and traits' default methods, need their
type arguments, so icode lowers them once per instantiation, as the C
backend does (`Cx.target`, instances after the program's functions); every
other function is lowered once. A `dyn` value is `K_DYN` (the value and a
vtable of `Code.vts`: per trait method the function to call). Show impls:
ieval.prerender replaces each part of a value whose type has one by its
text (`K_RAW`) before formatting; a program without Show impls skips it.

A missing map key reached through a place (`m[k] += 1`) is shown with
the key type's Show impl, as `m[k]` read as a value and C everywhere
(ieval.nk; tests/v2/run/trait_show_key_place.tn).

### Known differences

From `tenon-seed run` (none is exercised by the corpus):

- A dropped `Listener` or `Conn` is closed when the program ends, not when the
  value is dropped (an interpreted value has no destructor). Blocking sockets
  are emulated on a host `Poller`; text read from a `Conn` is converted to
  UTF-8 per received chunk, so a character split across TCP segments becomes
  U+FFFD.
- At most 4 `Poller`s per program.
- A map used as a key of another map loses its insertion order.

### Workers and channels (v2)

selfhost/iwork.tn, docs/reference.md §18. The interpreter's own code must
be accepted by the seed (which builds stage 0), so it cannot use workers: workers run under a deterministic
cooperative scheduler. A spawned worker runs when `main` waits (recv, join,
try_recv), round robin, until it finishes or would wait; a waiting worker is
unwound (`ieval.CBlock`) and later run again from the start, with the result
of every builtin with an effect it already called (`Bi.effect`:
console, capabilities, channels, workers) replayed from its log. The
observable results are the C backend's for every program whose output does
not depend on scheduling (tests/v2/run/workers_*.tn, programs/v2/scan on
both backends). Differences: resuming a worker repeats its computation (a
worker that waits k times costs about k times its work); a worker blocked in
the host (a socket, `Poller.wait(-1)`, `sleep_ms`) holds up every worker;
workers still running when `main` returns never ran to the end (in C they
are stopped at an arbitrary point); `Workers.cores()` asks `getconf`.

### Speed

Tenon built -O2 by ./check against the seed's interpreter (`tenon-seed run`): fib(38) 18.8 s
vs 17.0 s, bench/trees 33.7 s vs 43.3 s, tests/run/std_regex.tn 2.4 s vs
2.3 s.

## The test runner

`tenon test` (testrun.tn) ports bootstrap/src/testrun.rs: the same jobs,
directives (`// stdin:` with `\n` and `\xHH`, `// args:`, `// error:`),
rendering, golden files and `--bless`, and the same 20 s timeout per command
(`Proc.run_with`, which captures output and kills on timeout). Tests run in
8 workers: the runner starts itself 8 times (`test --worker I/N`) from one
`sh` and sums their results. It invokes itself: tenon.tn finds its own path
(`self_exe`: /proc on Linux, else `ps` and PATH) and passes it on as `--exe`.

## The build cache

As the bootstrap's: an entry is the executable plus its C source, named by a
hash of the C text, the C compiler and the flags (`pkg.hash`, two
polynomial hashes, the one hash of the tool, also behind tenon.lock content
hashes: the prelude has no hash function); a hit requires the
cached source to equal the new one exactly. `$TENON_CACHE` (default
`$TMPDIR/tenon-cache`), `off`, and `$TENON_KEEP_C` behave as in the
bootstrap; tenon's entries are named `t...` and never collide with the
bootstrap's. tools/cache_test.sh (in ./check).

## Prelude API added for the tools

- `Proc.run_with(cmd, args, dir, input, timeout_ms) -> Result[ProcOut, IoError]`
  (`ProcOut { status, signal, timed_out, out, err }`; the extern behind it is
  `Proc.run_capture`), for the test runner.
- `Proc.exit(status)`: any status 0-255, including the reserved 70, 71, 72
  and 74, so the interpreter can pass on a trap's status.

Both are in the bootstrap (interpreter and C backend), the C runtime and the
self-hosted C backend; tests/run/proc_run_with.tn and proc_exit_range.tn.
