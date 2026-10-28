# Benchmarks

`python3 ops/evidence/bench.py [NAME...]` builds and runs each benchmark
(median wall time of `BENCH_RUNS` runs, default 3), checks that every
implementation prints the same output, and writes `.evidence/bench.json`;
with no names it also runs the parallel ones (`bench/v2`,
`.evidence/bench_parallel.json`). The nightly evidence run measures Linux and
reports the results in STATUS.md.

## What each measures

| Benchmark | Input | What it exercises |
|---|---|---|
| `fib` | none | `fib(38)`, naive recursion: calls and integer arithmetic |
| `trees` | none | binary trees built, walked and freed (benchmarks-game style): allocation and reference counting of enum nodes |
| `wordfreq` | `gen.py`: ~16 MB of Zipf-like words | lowercasing, splitting into words, a `Map[Str, Int]` of counts, sorting the entries |
| `calc` | `gen.py`: definitions, recursive calls, arithmetic lines | a REPL for a small expression language: tokenizer, recursive-descent parser, tree-walking evaluator with enums and `Result` |
| `mdhtml` | `gen.py`: ~12 MB of Markdown | a Markdown subset to HTML: string scanning byte by byte, slicing, appending |
| `v2/mandel` | none | the Mandelbrot set row by row on 0-8 workers: float arithmetic, `par_map_n` |
| `v2/pwords` | none | word counts in 64 chunks on 0-8 workers, maps copied back and merged |

Each `bench/NAME` has `NAME.tn` and references in C (`NAME.c`), Python
(`NAME.py`), and for most also Rust (`NAME.rs`) and TypeScript (`NAME.ts`,
run with node); `bench/v2/NAME` has `NAME.tn` and optionally a serial
`NAME.c`.

## Fairness

- **Same algorithm.** A reference implements the same algorithm with the
  same data structures where the languages allow it (an open-addressing
  table where Tenon has a `Map`), written as idiomatic code in its language,
  not tuned beyond what the Tenon version is.
- **Same C compiler and flags.** The C references are compiled with the
  compiler `tenon build` uses (`$CC`, default `cc`) and its flags (`-O2 -w
  -std=gnu11 -pthread -fno-tree-slp-vectorize`, compiler/tenon.tn
  `cc_flags`); `v2/mandel` adds `-ffp-contract=off`, since Tenon's floats do
  not fuse multiply-adds. Rust is built with `rustc -O`.
- **Same integer semantics.** Tenon's `Int` arithmetic traps on overflow
  (runtime/tenon.h `tn_add`), so the compiled references compute the same
  defined result (owner decision 2026-10-28, docs/log.md):
  - C: the integer arithmetic that computes the program's values (results,
    sums, counts, checksums, recursion arguments such as `n - 1`) uses
    `ck_add`, `ck_sub` and `ck_mul` from `bench/checked.h`
    (`__builtin_*_overflow`; on overflow `trap: integer overflow` and exit
    status 70, as Tenon), never signed overflow, whose undefined behaviour
    lets the C compiler transform code that Tenon must not (gcc rewrote the
    recursive `fib` into loops). Positions and sizes in buffers (`size_t`
    indices, loop counters over a range) stay plain: they are bounded by the
    size of an object and cannot overflow, so checking them would change no
    result. `calc` checks its language's arithmetic itself (an overflow is a
    calc error, the same explicit tests in every version) and `mdhtml`
    computes only positions, so their C needs no `checked.h`.
  - Rust: built with `-C overflow-checks=on` (a panic on overflow, as in a
    debug build), set in ops/evidence/bench.py.
  - Python: integers have arbitrary precision; no benchmark's values come
    near 2^63, so the outputs agree.
  - TypeScript: numbers are doubles; the benchmarks' integers stay below
    2^53, where doubles are exact.
