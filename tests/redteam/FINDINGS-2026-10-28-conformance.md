# Conformance findings — 2026-10-28

Tested the self-hosted compiler built by `./check` in a fresh clone of
`https://github.com/turtiesio/tenon.git`, at
`262858c65d7dd97ad64285c463a35e0ee3496954` (macOS arm64, Apple clang).
The initial full gate passed. No compiler, runtime, library, or existing test
was changed. Reviewed README, quickstart, reference, library, tools, both
preludes, packages, and the existing `FINDINGS*.md`, including the latest
fix-status table. The six findings below are new; the old comparison,
constant-cycle, deep-stack, path, and linear-wrapper findings are not counted.

## Ranked findings

| Rank | Impact | Finding | Repro under `repros-2026-10-28/` |
|---|---|---|---|
| 1 | Medium | Interpreter applies `Show for Box[Int]` to `Box[Str]`; native does not | `v2/01-specialized-show.tn` |
| 2 | Medium | Implicit formatting ignores a generic `Show` impl's bounds, on both backends | `v2/02-show-impl-bound.tn` |
| 3 | Medium | Euclidean division/remainder trap although their results fit in `Int` | `03a-div-euclid.tn`, `03b-rem-euclid.tn` |
| 4 | Low | Fixed-point formatting cannot print `INT_MIN` | `04-fmt-fixed-min.tn` |
| 5 | Low | A struct containing a capability incorrectly satisfies derived `Show` | `v2/05-derived-show-bound.tn` |
| 6 | Low | LSP field definition points into a comment | `06-lsp-field.tn` |

Medium means silent wrong execution or failure of an otherwise valid operation;
low means a narrower formatting, declared-bound, or editor-contract violation.
No capability escape or native memory-safety failure was established.

## Reproduction commands

From the repository root, set:

```sh
R=tests/redteam/repros-2026-10-28
python3 "$R/reproduce.py"              # all seven programs and the LSP exchange
python3 "$R/reproduce.py" 01           # one finding
python3 "$R/reproduce.py" --sanitize   # generated C, same flags as tools/asan.sh
```

The script prints raw statuses/stdout/stderr; its successful exit means the
replay completed, not that the compiler conforms. It uses temporary outputs
and does not rewrite sources. Trait files are under `v2/` so the frozen seed's
cross-check does not mistake unsupported syntax for a regression.

For findings 1–5, the individual commands are:

```sh
target/tenon check "$R/FILE.tn"
target/tenon run "$R/FILE.tn"
target/tenon build "$R/FILE.tn" -o /tmp/tenon-conformance-native
/tmp/tenon-conformance-native
```

Substitute the exact relative repro path from the table for `FILE.tn`.
All seven files pass `check` and `build` with status 0. Native results below
were verified at default `-O2`, at `-O0`, and under ASan/UBSan.

## 1. Interpreter dispatches a specialized Show impl for the wrong type

```tenon
struct Box[T] { x: T }
impl Show for Box[Int] { fn to_str(self) -> Str { "integer" } }
fn main(sys: Sys) { sys.console.println("{Box { x: "a" }}") }
```

**Command:** the commands above with `FILE.tn=v2/01-specialized-show.tn`.

**Expected:** `Box { x: "a" }\n`, exit 0 in both backends.
[Reference §17, Implementing](../../docs/reference.md#17-traits) permits an
impl for a *specific instantiation*; the impl above is for `Box[Int]` only.
`Box[Str]` retains the structural formatting specified by §8. Reference §1
requires interpreter/native equivalence.

**Actual:** `run` prints `integer\n`, exit 0; native prints
`Box { x: "a" }\n`, exit 0. Stderr is empty in both.

The difference also occurs for specialized generic enums and when formatting
inside a worker. Inspection suggests the interpreter's formatting override
map keys on the struct/enum declaration ID, losing its type arguments
(`ival.Names.ovs`, `ieval.render`), whereas native dispatch retains them.
That explanation is an inference; the program above is the evidence.

Fixed in 01e9677, tests tests/v2/run/trait_show_specialized.tn, trait_show_specialized_main.tn, trait_show_specialized_place.tn, trait_show_specialized_expect.tn (under tests/v2/run).

## 2. Implicit Show dispatch does not enforce the impl's bounds

```tenon
struct Box[T] { x: T }
impl[T: Hash] Show for Box[T] { fn to_str(self) -> Str { "hashable" } }
fn main(sys: Sys) { sys.console.println("{Box { x: 1.5 }}") }
```

**Command:** the commands above with `FILE.tn=v2/02-show-impl-bound.tn`.

**Expected:** structural `Box { x: 1.5 }\n`, exit 0: `Float` does not satisfy
`Hash`, so the conditional override does not apply. If the compiler chooses
the override instead, it must diagnose the unsatisfied bound rather than
execute that body. [Reference §17, Bounds and Derived traits](../../docs/reference.md#17-traits)
requires bounds at instantiation and explicitly excludes `Float` from `Hash`.
Generic `Show` impls are documented as supporting derived-trait bounds.

**Actual:** accepted; both `run` and native print `hashable\n`, exit 0,
empty stderr. An inapplicable impl is executed.

The bound is operational, not just descriptive: replacing the marker body
with `let m: Map[T, Int] = [self.x: 1]; "{m.len()}"` also passes and prints
`1`, on both backends, despite creating a map with a `Float` key. This is a
new implicit-Show-instantiation path, rather than the old direct/generic
function-comparison findings. The checked-in marker is the smaller repro.

## 3. Euclidean arithmetic has avoidable intermediate overflow

`03a-div-euclid.tn`:

```tenon
fn main(sys: Sys) { sys.console.println("{INT_MIN.div_euclid(3)}") }
```

`03b-rem-euclid.tn`:

```tenon
fn main(sys: Sys) { sys.console.println("{-1.rem_euclid(INT_MIN)}") }
```

**Command:** the commands above with each of the two filenames.

**Expected:** respectively `-3074457345618258603\n` and
`9223372036854775807\n`, each exit 0.
[Library, Builtin types and capabilities, Int](../../docs/library.md#builtin-types-and-capabilities)
documents Euclidean division and a never-negative remainder. In the first
case `INT_MIN = 3 * (-3074457345618258603) + 1`; in the second
`-1 = INT_MIN + INT_MAX`. Both results are representable 64-bit integers
(reference §3); neither operation divides by zero.

**Actual:** each checks/builds, then traps in both backends, empty stdout,
exit 70:

```text
trap: integer overflow
```

The reported user locations are `03a-div-euclid.tn:1:61` and
`03b-rem-euclid.tn:1:45` (preceded by the source path).
`lib/prelude.tn` computes division as `(self - remainder) / d`, whose
subtraction underflows here, and computes negative remainders using
`d.abs()`, which cannot represent `abs(INT_MIN)`. These are two cases of the
same documented arithmetic contract failing on valid inputs, grouped as
one finding.

Fixed in 480f480, test tests/run/trap_euclid_extremes.tn.

## 4. fmt_fixed traps on INT_MIN instead of formatting it

```tenon
fn main(sys: Sys) { sys.console.println(INT_MIN.fmt_fixed(2)) }
```

**Command:** the commands above with `FILE.tn=04-fmt-fixed-min.tn`.

**Expected:** `-92233720368547758.08\n`, exit 0.
[Reference §8](../../docs/reference.md#8-strings-and-formatting) and
[Library, Int](../../docs/library.md#builtin-types-and-capabilities)
specify formatting a fixed-point integer, with `1234.fmt_fixed(2)` giving
`12.34`; no exclusion for `INT_MIN` is specified. No numeric result outside
`Int` is needed to produce this string.

**Actual:** accepted, but both backends have empty stdout and exit 70:

```text
trap: integer overflow
  at tests/redteam/repros-2026-10-28/04-fmt-fixed-min.tn:1:58
```

The source path prefix depends on the invocation. The prelude formats
`self.abs()` first, which overflows for this one valid input.

Fixed in c954e51, test tests/run/fmt_fixed_extremes.tn.

## 5. Derived Show checks type arguments but misses declared fields

```tenon
struct Box { c: Console }
fn show[T: Show](x: T) -> Str { x.to_str() }
fn main(sys: Sys) { sys.console.println(show(Box { c: sys.console })) }
```

**Command:** the commands above with `FILE.tn=v2/05-derived-show-bound.tn`.

**Expected:** a check-time diagnostic that `Box` does not implement `Show`,
because it contains `Console`. [Reference §17, Derived traits](../../docs/reference.md#17-traits)
and the header of `lib/v2/prelude.tn` define `Show` structurally as excluding
functions and capabilities. There is no custom impl in this program.

**Actual:** accepted; both backends print `Box { c: <Console> }\n`, exit 0,
empty stderr. Replacing the field with `f: fn(Int) -> Int` likewise passes
and prints `<fn>` for it. This finding concerns eligibility for an explicit
`T: Show` bound; it does not claim that directly interpolating capabilities
must be prohibited or that formatting grants authority.

Fixed in f2291e4, tests tests/v2/reject/bound_show_capability_field.tn, tests/v2/reject/dyn_show_function_payload.tn, tests/v2/run/show_bound_fields.tn.

## 6. LSP go-to-definition locates a comment, not the field declaration

```tenon
struct Point {
    // x is the coordinate.
    x: Int,
}
fn main(sys: Sys) {
    let p = Point { x: 1 }
    sys.console.println("{p.x}")
}
```

**Command:** `python3 "$R/reproduce.py" 06`. The helper runs
`target/tenon lsp`, sends `initialize`, `didOpen` with this file's complete
text, the following request, then `shutdown` and `exit`, with correct
Content-Length framing. URI is the repro file's absolute `file:` URI.

```json
{"jsonrpc":"2.0","id":2,"method":"textDocument/definition","params":{"textDocument":{"uri":"URI"},"position":{"line":6,"character":28}}}
```

**Expected:** the `x` declaration, zero-based range
`{"start":{"line":2,"character":4},"end":{"line":2,"character":5}}`.
[Tools, tenon lsp](../../docs/tools.md#tenon-lsp) promises go-to-definition.

**Actual:** response `id: 2` has the correct URI but range
`{"start":{"line":1,"character":7},"end":{"line":1,"character":8}}`,
the `x` in the comment. Diagnostics are empty, the server exits 0, and the
program itself prints `1\n` with exit 0 in both backends. Removing the
comment makes navigation locate the field correctly.

Fixed in c8dd8c3, test tests/lsp/fields.tn (run by tools/lsp_test.py).

## Negative results and validation limits

- Ran 45 accepted, newly authored exploratory programs through generated-C
  ASan/UBSan builds. No sanitizer reports. Also reran every checked-in repro
  with the replay script's `--sanitize` option. Flags match `tools/asan.sh`:
  `cc -g -O0 -DTN_POOL_MAX=0 -fsanitize=address,undefined
  -fno-sanitize-recover=undefined -w -pthread OUT.c -o OUT.asan -lm`, then
  `ASAN_OPTIONS=detect_leaks=0 OUT.asan`. This is not a leak-check result.
- Formatter output for those 45 accepted probes preserved the AST after
  removing source positions. No program whose meaning was changed by `fmt`
  was established. Checked-in repros are in canonical layout.
- Targeted probes of object safety, dyn dispatch and worker transfer,
  closure transfer through channels, unique worker results, generic impl
  bounds on ordinary calls, UTF-8/empty strings and byte lists, codec
  duplicate keys, Unicode format fills, separators, and large/special
  floats did not establish additional findings.
- These are isolated reports/repros, not golden run tests that bless the
  faulty outputs. They neither alter existing expectations nor claim
  exhaustive coverage of the language. Native sanitizer success does not
  establish the correctness of interpreter dispatch or trait checking.
