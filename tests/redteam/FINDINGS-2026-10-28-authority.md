# Authority findings — 2026-10-28

Part "authority" of the weekly correctness review: do Tenon programs get only the authority they
are given, and do the safety promises hold (capabilities, `Send` and worker isolation, linear and
unique obligations, module privacy, packages, memory safety, backend agreement)?

Tested the self-hosted compiler built by `./check` in a fresh clone of
`https://github.com/turtiesio/tenon.git` at `6a4e169` (macOS arm64, Apple clang 21). The initial
gate passed. No compiler, runtime, library or existing test was changed. Read README, tenon.md §1,
reference, library, tools, packages, both preludes and every `FINDINGS*.md` (including today's
`FINDINGS-2026-10-28-conformance.md`); nothing already listed there is counted below (the old
comparison, deep-stack, path, wrapper and temporary findings; the weak package hashes, which
`docs/packages.md` states are not cryptographic; the acknowledged check/use race of `Fs`).

## Ranked findings

| Rank | Severity | Property violated | Finding | Repro (`repros-2026-10-28-authority/`) |
|---|---|---|---|---|
| 1 | **High** | linear: "every path must consume it" (§12) | A linear value moved into an earlier argument is silently lost when a later argument contains `?`, `return`, `break` or `continue` | `01a`–`01d` |
| 2 | **High** | linear: ref only inspects (§12) | A `ref Claim` function used as a `fn(Claim)` value consumes nothing: the argument vanishes | `02` |
| 3 | Medium | "dropping one closes it" (§15); interpreter = compiler (§1) | `tenon run` never closes a dropped `Listener`/`Conn`: it keeps accepting, peers never see end of stream (hang), and a loop runs out of file descriptors | `07a`, `07b`, `07c` |
| 4 | Medium | linear/unique: "copies" are rejected (§12) | A `const` of a linear or unique type is copied at every use | `03a`, `03b` |
| 5 | Medium | privacy is unforgeability (§13) | A module-private enum can be forged with `decode` (type inferred) and its private variants can be matched | `04` + `private_level.tn` |
| 6 | Medium | a moved unique value "cannot be used" (§18); never copied (§12) | A consumed linear/unique value can still be inspected: fields, `ref` calls, handle methods, `==`, formatting | `05a`, `v2/05b` |
| 7 | Low | "killed" on timeout (library, `Proc`); tenon.md §2.4 process groups | `run_with` kills only the direct child on timeout; its descendants live on | `06` |

Everything else in scope held (list at the end). All seven are fixed (each section names the commit
and the regression test); the repros of findings whose fix the frozen seed does not share moved to
`repros-2026-10-28-authority/v2/`. Findings 1, 2, 4 and 6 are checker holes (accepted
programs break a documented promise) and behave identically in `run` and `build`; 3 is a backend
difference; 5 is a privacy hole; 7 is a resource-control gap.

Replay everything: `python3 tests/redteam/repros-2026-10-28-authority/reproduce.py` (one finding:
`... reproduce.py 01`; with the flags of `tools/asan.sh`: `--sanitize`). Single program:

```sh
R=tests/redteam/repros-2026-10-28-authority
target/tenon check $R/FILE.tn && target/tenon run $R/FILE.tn
target/tenon build $R/FILE.tn -o /tmp/x && /tmp/x
```

## 1. A linear value is lost when a later argument leaves the function or loop (High)

**Property:** reference §12: "every path must consume it: ... and before `return`, `break`,
`continue` or `?`"; "The compiler rejects any program that copies one or loses one".

**Cause (inferred from behaviour):** an argument that is a bare linear variable counts as consumed
the moment it is evaluated, but the call has not happened yet. If a later argument (or a later
tuple/struct element, or the rest of an interpolation) returns, breaks, continues or `?`-fails, the
already-moved value is dropped with nobody finishing it. The same checker does catch the value
when it is still a live variable at the `?` (`let _n = fails()?` gives "the early return of '?' would
drop it"), so only the in-flight case is missing.

```tenon
linear struct Claim { id: Int }
fn Claim.complete(self, con: Console, n: Int) { con.println("completed {self.id} with {n}") }
fn fails() -> Result[Int, Str] { Err("boom") }
fn work(con: Console) -> Result[Unit, Str] {
    let c = Claim { id: 7 }
    c.complete(con, fails()?)
    Ok(())
}
fn main(sys: Sys) { sys.console.println("{work(sys.console)}") }
```

**Command:** `check`, `run`, and `build` + run of `01a-linear-lost-method-arg.tn`.

**Expected:** a check error that `c` is dropped by the early return of `?` (as in the live-variable
case). **Actual:** accepted by `check`; `run` and native print `Err("boom")`, exit 0, and
`completed 7 ...` never appears: the obligation is gone. ASan/UBSan clean.

More shapes, all accepted and all losing the claim (`01b`–`01d`):

| Shape | Program |
|---|---|
| plain call, `?` in a later argument | `take(c, con, fails()?)` |
| `return` in a later argument | `take(c, con, if early { return } else { 0 })` |
| `break` / `continue` in a later argument | `take(c, con, if i == 1 { break } else { 0 })` |
| tuple | `let (a, b) = (c, fails()?)` |
| match scrutinee | `match (c, fails()?) { (a, b) => ... }` |
| interpolation | `"{c.id_of()} {fails()?}"` |
| struct literal of a `linear struct` | `Hold { c: c2, n: fails()? }` |

`unique` values are unaffected (they may be dropped). `?` is the idiomatic way to write error
handling in Tenon, so this is easy to hit by accident, e.g. `store.commit(claim, parse(line)?)`.

Fixed in 06027af, tests tests/v2/reject/linear_inflight_*.tn (receiver, argument, `return`, `break`,
`continue`, tuple, match scrutinee, struct literal, a new value, a variant) and
tests/v2/run/linear_inflight_ok.tn. Rule (reference §12): a part of a call, method call, tuple or struct
literal that moves a linear value cannot sit next to a part that may leave early (`?`, `return`, or a
`break`/`continue` of a loop around it), whatever their order; compute that part with `let` first. The
interpolation shape is not a loss: `c.id_of()` is the type's own method and finishes the claim before
the `?` runs (it stays accepted, in tests/v2/run/linear_inflight_ok.tn).

## 2. A `ref` parameter is erased when the function is used as a value (High)

**Property:** reference §12: "A parameter declared `x: ref T` only *inspects* its argument: the
caller keeps the value (it is not consumed by the call)".

```tenon
linear struct Claim { id: Int }
fn peek(c: ref Claim) -> Int { c.id }
fn apply(f: fn(Claim) -> Int, c: Claim) -> Int { f(c) }
fn main(sys: Sys) {
    let n = apply(peek, Claim { id: 7 })     // apply "consumes" c by calling f(c); peek consumes nothing
    let k = Claim { id: 8 }
    let g: fn(Claim) -> Int = peek
    sys.console.println("peeked {n} {g(k)}")
}
```

**Command:** `02-ref-param-erased-by-fn-value.tn` (check, run, build).

**Expected:** a check error: `peek` has a `ref` parameter, so it does not fit `fn(Claim) -> Int`
(the checker already refuses `mut` functions as values: "'bump' has 'mut' parameters, so it can
only be called, not used as a value"). **Actual:** accepted; `run` and native print
`peeked 7` / `peeked 8`, exit 0. Both claims (7, 8) are never completed, and there is no syntax
to write a `ref` in a function type, so the loss cannot be spelled out in a signature. This
turns any inspector into a silent drop of an obligation.

Fixed in ed34e7d, tests tests/v2/reject/ref_fn_value.tn, tests/v2/reject/ref_method_value.tn,
tests/v2/reject/trait_impl_ref_dropped.tn, tests/v2/reject/trait_impl_ref_added.tn,
tests/v2/run/trait_ref_param.tn. Rule (reference §12): `ref` is not part of a function type, so a
function with a `ref` parameter can only be called, like one with `mut` parameters. The same erasure
existed through traits (an impl taking `ref` where the trait method takes the value, called through a
bound); trait methods now carry their `ref` parameters and impls must match them.

## 3. `tenon run` never closes dropped sockets (Medium)

**Property:** reference §15: "`Listener` and `Conn` are unique handles: ... dropping one closes
it"; reference §1: both backends "must behave identically".

**07a** — a listener dropped when its function returns:

```tenon
fn open_and_drop(sys: Sys) -> Int { let l = sys.net.listen(0).unwrap()
    l.port() }
fn main(sys: Sys) {
    let p = open_and_drop(sys)
    match sys.net.connect("127.0.0.1", p) {
        Ok(_) => sys.console.println("still accepting"),
        Err(_) => sys.console.println("refused"),
    }
}
```

`run`: `still accepting`; native: `refused`; both exit 0.

**07b** — `for i in 0..5000 { once(sys) }` where `once` opens a listener and drops it. With
`ulimit -n 256`: `run` fails at iteration 253 ("opened and dropped 253 listeners; first failure
at 253"); native reaches 5000. (Without the limit the interpreter presumably holds every socket until
exit.)

**07c** — a client `Conn` dropped after `write("x")`: the server's `read_line` returns
`Ok(Some("x"))` natively (end of stream) but **never returns** in `tenon run` (exit 124 under a
timeout): the program deadlocks. Exit by timeout is the symptom; no sanitizer report is involved.

**Expected:** the interpreter closes handles at the same points as the compiled program.

Fixed in ba6303c, test tests/run/net_drop_closes.tn (function return, block end, a temporary, an
overwritten variable, a match arm in a loop, a struct, a value moved into a call, a temporary argument,
the peer of a dropped `Conn` reading the end of the stream; `run` = native = `tenon-seed run`). The
interpreter closes a socket where the C backend's reference counts reach zero (docs/dev/compiler.md,
"Dropped sockets"; reference §15). `07a` and `07c` were the two files `ops/evidence/interp_diff.py` found
differing from the seed's interpreter; it finds none now.

## 4. A constant of a linear or unique type is copied at every use (Medium)

**Property:** reference §12: "The compiler rejects any program that copies one or loses one";
`unique`: "never copied".

```tenon
linear struct Claim { id: Int }
fn Claim.complete(self, con: Console) { con.println("completed {self.id}") }
const CLAIM: Claim = Claim { id: 1 }
fn main(sys: Sys) {
    let a = CLAIM
    let b = CLAIM
    let c = CLAIM
    a.complete(sys.console)
    b.complete(sys.console)
    c.complete(sys.console)
}
```

**Command:** `03a-const-linear-copied.tn`; `03b-const-unique-copied.tn` is the unique version
(prints `6` for two uses of one constant `Handle { fd: 3 }`).

**Expected:** a check error at the declaration (a `const` cannot have a linear or unique type) or
at each use. **Actual:** accepted; `completed 1` three times, exit 0, both backends. One
obligation becomes any number of independent ones. Across modules a `pub const` of a linear type
mints values outside the type's module, which is how "privacy is unforgeability" (§13) is meant
to be prevented (the module's own `mk` function is not needed). A `let a = CLAIM` that is never
used is still rejected ("never used"), so only duplication is open.

Fixed in d2de63f, tests tests/v2/reject/const_linear.tn, tests/v2/reject/const_unique.tn (a constant
cannot have a linear or unique type; reference §12).

## 5. Private enum: forgeable with `decode`, variants visible to patterns (Medium)

**Property:** reference §13: "Items are private unless declared `pub`"; "a module is the only
place that can create a value of its type ...: privacy is unforgeability"; §14: "types with fields
you cannot see cannot be encoded" (decode of `Account` with private fields is correctly rejected).

Module `private_level.tn`:

```tenon
// module
enum Level { Guest, Admin }
pub fn guest() -> Level { Guest }
pub fn is_admin(l: Level) -> Bool { match l { Admin => true, Guest => false } }
```

Importer (`04-private-enum-forged.tn`):

```tenon
import private_level
fn main(sys: Sys) {
    let g = private_level.guest()
    let forged = decode("Admin").unwrap()            // type inferred from is_admin's parameter
    sys.console.println("{private_level.is_admin(forged)}")   // true
    match g { Admin => ..., Guest => ... }                    // private variants are matchable
}
```

**Expected:** both lines rejected: `Admin(..)`/`Pa(5)` as an expression is "unknown name" and
`private_level.Level` as a type is "private to module", and a value of a type nobody outside can
name should not be constructible or deconstructible. **Actual:** `check` accepts; `run` and native
print `is_admin(guest) = false`, `is_admin(decode) = true`, `matched private variant Guest`.
Structs with private fields are protected (`decode`, `encode`, literal, update and field access are
all rejected, 33 variants tried), so this is specific to enums, whose payloads count as visible.

Fixed in a35a3f5, tests tests/v2/reject/enum_private_decode.tn, tests/v2/reject/enum_private_match.tn,
tests/v2/reject/struct_private_decode.tn (module tests/v2/reject/privlevel.tn). Rule (reference §13,
§14): a pattern cannot name a variant of another module's private enum, and a private type (struct or
enum without `pub`) of another module cannot be encoded or decoded; the same forging was open for a
private struct whose fields are all `pub`.

## 6. A consumed linear/unique value can still be inspected (Medium)

**Property:** reference §18: "a unique value is moved: after `tx.send(t)` or `w.spawn(f, t)` the
sender cannot use `t`"; §12 unique: "never copied"; §15: dropping a handle closes it.

Moves are tracked for another move (`let b = a; let c = a` is rejected: "'a' was already used"),
but not for the operations §12 calls non-consuming: field reads, `ref` arguments, `==`,
formatting, and the methods of builtin handles. After the value is gone, these still work:

* `05a`: `close_it(l)` (a `Listener` passed by value and dropped inside) then `l.port()` is
  accepted and works; because the caller's name still references the socket, the "dropped"
  listener is **not closed** (a new connection to its port still succeeds, both backends).
* `v2/05b`: a user `unique struct Buf { items: List[Int], name: Str }` is passed to
  `w.spawn(consume, b)` and sent through a channel, then `b.items.len()` and `b.name` are read in
  the sender. Accepted; prints `sender still sees 1000 items`. (No memory error: ASan/UBSan and
  TSan are clean because values are copied between workers, which is also why this stays an
  observable-semantics gap rather than a use-after-free.)
* Also accepted after consumption: `h.fd` of a unique struct, `peek(h)` with `ref h`, `h == h`,
  `"{h}"`, `l.accept()`, and `c.id` of a linear value after `c.fin()`.

A user-defined method taking `self` (`h.get()`) *is* rejected after a move, so the check is inconsistent between method calls and the other inspecting forms.

**Expected:** "'x' was already used" for each of these uses. **Actual:** accepted, `run` = native.

Fixed in bdbca07, tests tests/v2/reject/moved_*.tn (field read, `ref` argument, `==`, formatting, a
`Listener` method, a linear field after `fin`, moved on one path, after `spawn`, after `send`) and
tests/v2/run/unique_moved_then_reassigned.tn. Rule (reference §12): once consumed, a name cannot be
used at all, also by the uses that do not consume, until a unique `var` is assigned a new value.

## 7. `Proc.run_with` timeout leaves the command's descendants running (Low)

**Property:** library, `Proc`: a command still running after `timeout_ms` "is killed (SIGKILL)";
tenon.md §2.4: "Processes a job starts are always killed as a whole group when it ends or times
out" (the project's own rule for the tooling it builds on `run_with`, e.g. `selfhost/pkg.tn`'s `sh`).

`06-run-with-timeout-leaves-descendants.tn` runs `sh -c "sleep 7.31 & sleep 7.31"` with a 300 ms
timeout: `timed_out=true status=-1 signal=9`, and `pgrep -f "sleep 7.31"` still finds both
`sleep` processes afterwards (`descendant still running after the timeout: true`, both backends).
A hung build step that forks therefore outlives its timeout. The repro kills the leftovers itself.

**Expected:** kill the process group (or document that only the direct child is killed).

Fixed in cf14aaf, test tests/v2/run/proc_timeout_kills_group.tn (the command runs in a process group
of its own and the whole group is killed on timeout; docs/library.md, `Proc`).

## Held up (no bug found)

* **Fs jail:** 35 read-side paths × `exists/is_dir/read/list/read_bytes` and 20 write-side paths ×
  `write/append/write_bytes/append_bytes/truncate/mkdir/mkdir_one/rename/remove`, against a
  fixture with 11 kinds of symlink (to a directory, to a file, absolute, dangling, in the middle
  of the path, inside the jail, planted `.tmp` links): every escape is `Denied`, the area outside
  the jail is byte-identical afterwards, and `run` = native. `..`, absolute, empty, `sub/..`,
  `link/`, `./link` denied; `...`, `..a`, `a..` are ordinary names. `within` chains (`within("..")`,
  absolute, symlink and NUL arguments) give a dead, read-only `Fs`, never a wider one; `read_only`
  survives `within` and every write form; 9 NUL placements × 12 operations (including both
  `rename` arguments and the unattenuated `Fs`) denied. Paths of 5,000 × 3 bytes, 2,000
  nested `within`s, a 30,000-component path and a 70,000-byte name fail cleanly under ASan/UBSan.
  Concurrent writers of one file (6 MB × 3 writers + a reader) produced no torn read.
* **Forging capabilities (about 40 cases):** user `extern`, methods on `Sys`/`Fs`, `Sys { .. }` literals,
  `decode`/`encode` of `Fs`, `Sys`, `Option[Fs]`, tuples, `dyn`, fns, closures, `Workers`,
  channels, `List[Fs]` indexing, empty-map lookups, `panic[Fs]` constants, redefining `Fs.within`
  / `Fs.read_only`, closures/struct update/`Sys` update around an attenuated `Fs`. None obtains or
  widens authority.
* **Net/Proc/Clock/Console:** `listen` and `poller().listen` bind 127.0.0.1 only; `Poller` ids
  (`0`, `1`, `2`, negatives, `INT_MAX`, `2^32`, closed ids) never touch memory or fds 0–2 (ASan/UBSan
  clean); `run`, `run_with` (NUL, 200,000 arguments, 3 MB arguments, 1 MB stdin through `cat`,
  3 MB each on stdout and stderr, signals, timeout 1 ms / negative / `INT_MAX`), `env`, `exit`
  (0, 3, 255 pass; 256, -1, 300 trap; 70/72/74 pass; from a worker) agree; `sleep_ms` with
  negative values returns at once; huge/negative `read_bytes`; about 20 error paths of `Net` and 40 of
  `Fs` give identical text in both backends. `tenon run`'s replay of a worker (append, console
  read, `Proc.run`, clock) performs each effect once, like native.
* **Send and isolation (35 check cases, several TSan and ASan programs):** linear, `Listener`,
  `Conn`, `Poller`, structs/tuples/`Option`/generic wrappers containing them, inference through
  unbounded generics, generic wrappers, user methods on `Sender`, results of workers, `par_map`
  with unique results, `dyn` over them: all rejected with the `Send`/unique diagnostics; user
  `unique` values are moved and unusable by the sender in the way they are tested by finding 6.
  TSan found no report with: shared `const` lists/maps/strings in 8 workers, one `Worker` handle
  joined by 6 workers, a `dyn` value and a closure over big data sent to 6 workers, `Sender`s
  sent through channels shared by 4 workers, 4 workers reading one stdin, 4 workers printing, 4
  workers writing/listing files. ASan/UBSan clean on tree/enum/map/closure messages; 3,000 concurrent
  workers on one channel run correctly in both backends.
* **Linear/unique across traits, dyn, generics (about 190 check cases):** default methods that
  use `self` twice, orphan impls that drop or duplicate, bounded generics (`twice`, `drop_it`,
  `dup`, `cl`, `go`), `Option`/`Result` helpers with closures (`map`, `map_or`, `filter`,
  `and_then`, `is_some_and`, `map_err`, `ok`, `unwrap_or`), `dyn` over linear/unique including
  through generic impls, closures capturing `self`/fields/`ref`/`mut` parameters, `let ... else`,
  `if let`, `while let`, `_` patterns, struct update with a temporary base, overwrite of an
  `Option[Claim]`, field moves out of unique/linear values, `List`/`Map`/`Set`/`Heap` holding
  them, enum payloads, user generic methods: all rejected as documented.
* **Packages:** import order (local, dependency, std) as documented, a dependency cannot reach the
  root's modules, a local `journal.tn` in a dependency hides std only for that package, and
  duplicates of one module name are an error; editing, replacing (`extra.TN`), symlinking or
  looping files in the cache is caught by the content hash; a symlink loop in a fetched
  repository ends in an error instead of a hang; 300 byte-level mutations of `tenon.toml` and
  `tenon.lock` gave no crash, trap or hang.
* **Generated C:** C keywords, libc and runtime names used as variables, fields, constants, types,
  functions and variants (`exit`, `printf`, `errno`, `FILE`, `NULL`, `tn_alloc`, `fnv7`, ...) are
  mangled; strings with trigraphs, `*/`, `%n`, `\0`, a 200,000-byte literal compile and print
  correctly, also with `cc -std=c11 -trigraphs`.

## Limits of this review

* **TSan on macOS** deadlocks inside its own `dispatch_once` interceptor when several threads call
  `getaddrinfo` (`Net.connect`) in a program that also forks (`Proc`); that mixed program, which
  runs correctly 25/25 native, is not evidence of a Tenon bug and is not reported. Each part alone
  is TSan clean.
* The check/use race of `Fs.within` is acknowledged in the source and not re-tested; no attempt
  was made on out-of-memory behaviour (exit 71) or on hash collisions in the package cache.
* The seven findings are isolated repros, not golden tests that bless the faulty output.
