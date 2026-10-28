# Self-hosting: `tenon` replaces the bootstrap CLI

`selfhost/tenon.tn` is the driver of `tenon`, the one self-hosted
executable (tenon.md §5, "Fully self-hosted compiler"; its reference:
docs/tools.md). It has every subcommand of the frozen seed
(`target/release/tenon-seed`, which only builds stage 0), and more:

| tenon | = tenon-seed | Implementation |
|---|---|---|
| `run FILE [ARGS...]` | `run` | interp.tn and the i*.tn modules below |
| `build FILE [-o OUT] [-O0]` | `build` | emit*.tn (EMITTER_NOTES.md), the build cache in tenon.tn |
| `emit FILE` | `emit` | emit*.tn |
| `check FILE` | `check` | checker.tn (CHECKER_NOTES.md) |
| `test DIR... [--bless]` | `test` | testrun.tn |
| `tokens FILE`, `ast FILE` | `tokens`, `ast` | lexer.tn `dump`, astdump.tn |
| `fmt [--check] FILE...`, `fmt -` | (none) | fmtcmd.tn, fmt.tn, fmtlayout.tn, fmtlex.tn (test: tools/fmt_check.sh) |
| `lsp` | (none) | lsp.tn, lspquery.tn, lspindex.tn, lsppos.tn, json.tn (test: tools/lsp_test.py) |
| `fetch [DIR]` | (none) | pkg.tn, pkgtoml.tn (docs/packages.md; test: tools/pkg_test.sh) |

Inside a package (a `tenon.toml` at or above the file's directory), `run`,
`build`, `emit`, `check` and `test` resolve `import` also to the dependencies
pinned in `tenon.lock`, offline, from the cache (pkg.tn `context`, front.tn
`load_in`); the language server does the same.

Each prints and exits with what the seed's subcommand does; the driver's own
messages (unreadable files, a failing C compiler, usage errors) start with
`tenon:`, as the seed's do. The prelude, the standard library and the C
runtime come from the toolchain root (`--root DIR`, else `$TENON_ROOT`, else
found from the executable's own path, else the current directory:
docs/tools.md). Flags may come in any position (tools/cli_test.sh).

## The interpreter

A port of bootstrap/src/interp.rs, builtins.rs, value.rs and codec.rs:

| Module | Ports | Contents |
|---|---|---|
| `interp.tn` | interp.rs `run` | names for formatting, the `Sys` value, `main`'s result and exit status |
| `ival.tn` | value.rs | values, map keys, equality, ordering, formatting, format specs |
| `icode.tn` | (resolution done once) | the checked tree lowered to frame slots, resolved calls, numbered builtins |
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
  slot per function); calls know their target and builtins are numbered.
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

Known differences from `tenon-seed run` (none is exercised by the corpus):

- A dropped `Listener` or `Conn` is closed when the program ends, not when the
  value is dropped (an interpreted value has no destructor). Blocking sockets
  are emulated on a host `Poller`; text read from a `Conn` is converted to
  UTF-8 per received chunk, so a character split across TCP segments becomes
  U+FFFD.
- At most 4 `Poller`s per program.
- A map used as a key of another map loses its insertion order.

(v2) A missing map key reached through a place (`m[k] += 1`) is shown with
the key type's Show impl, as `m[k]` read as a value and C everywhere
(ieval.nk; tests/v2/run/trait_show_key_place.tn).

Verification:

- `./check` runs the whole suite with `tenon` (`tenon test tests tests/v2`:
  every run test on the interpreter and the C backend, compared with the
  .out files). The seed's own `tenon-seed test tests` runs in
  tools/evidence.sh, as the differential reference for its interpreter.
- `tools/programs.sh` (in ./check) runs the 9 program scenarios
  (chat uses the event loop, kvhttp blocking sockets) on `tenon run` and
  `tenon build`.
- `tools/interp_diff.py` (evidence): every corpus file under `tenon-seed run` and
  `tenon run`, byte-identical stdout, stderr and exit status: 755 of 758 the
  same, 0 different, 3 skipped (over 20 s in the bootstrap). The 5
  benchmarks run separately give the same output too.
- tools/selfhost.sh fails when the prelude has an `extern fn` the interpreter
  does not know (a builtin added to the bootstrap must be added here too).

Speed (tenon built -O2 by ./check; bootstrap = `tenon-seed run`): fib(38) 18.8 s
vs 17.0 s, bench/trees 33.7 s vs 43.3 s, tests/run/std_regex.tn 2.4 s vs
2.3 s. ./check's own timing table gives its current cost per step.

## The test runner

`tenon test` (testrun.tn) ports bootstrap/src/testrun.rs: the same jobs,
directives (`// stdin:` with `\n` and `\xHH`, `// args:`, `// error:`),
rendering, golden files and `--bless`, and the same 20 s timeout per command
(`Proc.run_with`, which captures output and kills on timeout). Tests run in
8 workers: the runner starts itself 8 times (`test --worker I/N`) from one
`sh` and sums their results. It invokes itself: tenon.tn finds its own path
(`self_exe`: /proc on Linux, else `ps` and PATH) and passes it on as `--exe`.

## New prelude API

- `Proc.run_with(cmd, args, dir, input, timeout_ms) -> Result[ProcOut, IoError]`
  (`ProcOut { status, signal, timed_out, out, err }`; the extern behind it is
  `Proc.run_capture`), for the test runner.
- `Proc.exit(status)`: any status 0-255, including the reserved 70, 71, 72
  and 74, so the interpreter can pass on a trap's status.

Both are in the bootstrap (interpreter and C backend), the C runtime and the
self-hosted C backend; tests/run/proc_run_with.tn and proc_exit_range.tn.

## The build cache

As the bootstrap's: an entry is the executable plus its C source, named by a
hash of the C text, the C compiler and the flags (tenon.tn `hash_hex`, two
polynomial hashes: the prelude has no hash function); a hit requires the
cached source to equal the new one exactly. `$TENON_CACHE` (default
`$TMPDIR/tenon-cache`), `off`, and `$TENON_KEEP_C` behave as in the
bootstrap; tenon's entries are named `t...` and never collide with the
bootstrap's. tools/cache_test.sh (in ./check).

## Gates

`./check` has the seed build tenon with -O0 (stage0, target/tenon0),
stage0 build tenon at -O2 in parallel translation units (stage1,
target/tenon), and runs the whole test suite, the program scenarios, the
doc programs and the grammar check with stage1. tools/selfhost.sh compares
stage1 with the bootstrap (`tokens`, `ast`, `check`, `emit`) and stage0 with
stage1 (the fixpoint) in one pass over the corpus. The bootstrap's own
`tenon-seed test tests` runs in tools/evidence.sh as the differential reference.
./check prints the time of each step at the end.

## Workers and channels in the interpreter (v2)

selfhost/iwork.tn, docs/reference.md §18. The interpreter is built by the
frozen bootstrap, so it has no threads: workers run under a deterministic
cooperative scheduler. A spawned worker runs when `main` waits (recv, join,
try_recv), round robin, until it finishes or would wait; a waiting worker is
unwound (`ieval.CBlock`) and later run again from the start, with the result
of every builtin with an effect it already called (`ibuiltin.FIRST_EFFECT`
on: console, capabilities, channels, workers) replayed from its log. The
observable results are the C backend's for every program whose output does
not depend on scheduling (tests/v2/run/workers_*.tn, programs/v2/scan on
both backends). Differences: resuming a worker repeats its computation (a
worker that waits k times costs about k times its work); a worker blocked in
the host (a socket, `Poller.wait(-1)`, `sleep_ms`) holds up every worker;
workers still running when `main` returns never ran to the end (in C they
are stopped at an arbitrary point); `Workers.cores()` asks `getconf`.
