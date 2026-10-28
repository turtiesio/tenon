# Tenon red-team findings

**Status update (re-verified after commit `1b2420c`, "Fix 9 QA findings").** Findings 1, 3, 4, 5, 6, 7, 8, 9 and 10 below were
fixed while this report was being written; I re-ran every repro against the fixed binary (marked **FIXED**) and then
tried to bypass each fix. The fixes for 5, 7 and 10 are incomplete and the NUL fix has a sibling hole in `Net`; those residues are
findings **20-24** (all open). Still open overall: **2** (high); **11, 20, 21, 22, 23** (medium); **12-18, 24** (low). Findings 1, 3, 4, 6, 8 and 9
held up against every bypass I tried.

Scope: correctness/soundness of the bootstrap compiler (`tenon run` interpreter and `tenon build` via C) at
commit `4b66990` plus working-tree state on 2026-10-28. Everything below was found by writing small Tenon
programs; nothing outside `redteam/` was modified. Each finding has a minimal reproduction in `repros/`.
`repros/setup-fs.sh` builds the fixture for the two file-system repros. "run" = `tenon run F.tn`, "native" =
`tenon build F.tn -o x && ./x`.

## Summary, ranked

| # | Sev | Property violated | Finding | Repro | Status |
|---|---|---|---|---|---|
| 1 | **high** | explicit authority; interpreter = compiler | A NUL byte in a path defeats `Fs.within`: the native build lists/stats the *parent* of the jail (`"..\0"`), and silently truncates paths. Interpreter says something else. | 01 | FIXED |
| 2 | **high** | linear/unique types; module privacy as unforgeability | A client-defined generic wrapper (`struct Wrap[A]`) drops or duplicates another module's `linear` value and duplicates `unique` handles (`Listener`/`Conn`). | 19 (+`vaultlib.tn`) | **open** |
| 3 | **high** | linear: used exactly once | A `match` guard can consume a linear value and the following arm consumes it again. | 03 | FIXED |
| 4 | **high** | linear: no loss | A linear value that exists only as a temporary is silently dropped by `mk().field`, `mk() == mk()`, `"{mk()}"`, and `f(mk())` with a `ref` parameter. | 04 | FIXED |
| 5 | medium | explicit authority | `Fs.within` / `read_only` follow symlinks out of the root (read, write, rename, remove, mkdir, list). Both backends. | 02 | FIXED (bypass: 21) |
| 6 | medium | linear: no loss | `Two { a: x, ..base }` silently drops the replaced linear field of `base`. | 05 | FIXED |
| 7 | medium | "functions cannot be compared"; interpreter = compiler | A struct containing a `fn` can be `==`-compared and used where a `fn` key is hashed; `run` and native give different answers/exit codes. | 06 | FIXED (bypass: 20) |
| 8 | medium | interpreter = compiler; no silent failure | NaN as a `Map[Float,_]` key: `run` traps, native inserts unreachable duplicate entries. | 07 | FIXED |
| 9 | medium | no silent failure | `Net.listen`/`connect` reduce ports mod 65536: `listen(73616)` binds 8080, `listen(-1)` binds 65535. | 08 | FIXED |
| 10 | medium | interpreter = compiler | Dropping (or `==` on) a 1,000,000-long recursive enum overflows the C stack in native (exit 72); the interpreter succeeds. | 09 | FIXED for enums only (rest: 22, 23) |
| 11 | medium | compiler robustness | Polymorphic recursion makes `tenon build` run forever; a polymorphic recursive type crashes it with a Rust stack overflow (exit 134). | 10, 11 | **open** |
| 12 | low | allow-only (reject at check time) | `Map < Map` type-checks and traps at run time. | 12 | open |
| 13 | low | check early | A cycle between `const`s is accepted; using one traps `stack overflow` at run time. | 13 | open |
| 14 | low | no hidden surprises | `x += e` reads `x` after `e` runs, `x = x + e` before. | 14 | open |
| 15 | low | allow-only | `let xs = []` / `let o = None` (type never determined) is accepted. | 15 | open |
| 16 | low | interpreter = compiler | `tenon run F.tn $'\xff'` panics the interpreter (Rust, exit 101); native runs. | 16 | open |
| 17 | low | located traps | Traps inside prelude-defined methods (`Int.abs`, `List.sum`, ...) report `<prelude>:L:C`, not the user's call site. | 17 | open |
| 18 | low | usability | Nested tuple access `t.0.1` does not parse. | 18 | open |
| 20 | medium | "functions cannot be compared"; interpreter = compiler | Fix for 7 covers only `==`/`<` and map keys: `List.contains`/`index_of`, a user generic `a == b`, `sort`, `sort_by` with a fn key, and capabilities are still comparable; `run` and native disagree. | 20 | **open** |
| 21 | medium | explicit authority | `Fs.write` opens `<path>.tmp`; a symlink planted there writes outside the root (fix for 5 checks only `path`). Both backends. | 21 | **open** |
| 22 | medium | interpreter = compiler | 1M-deep chain through a struct's `List` (or a `Map`) still overflows the C stack on release (fix for 10 covers enums only). | 22 | **open** |
| 23 | medium | interpreter = compiler | Derived `==`, `<`, hashing, `to_str`, `encode`/`decode` of a deep enum chain overflow the C stack in native; the interpreter succeeds. | 23 | **open** |
| 24 | low | interpreter = compiler | Native `Net.connect` truncates the host at a NUL byte and resolves `""` locally; the interpreter rejects/fails. | 24 | **open** |

Areas that held up are listed at the end.

---

## 1. NUL byte in a path escapes `Fs.within` in the native build (high)

**Status: FIXED in 1b2420c (re-verified: every NUL path is now `Denied("path escapes the Fs root: ...")` in both backends, for read/list/is_dir/exists/write/append/mkdir/rename (both arguments)/within/remove).**

**Property:** "An attenuated Fs rejects absolute paths and `..`" (reference §10); interpreter and compiled program behave identically.

**Cause:** `tn_fs_path` (runtime/tenon.h) checks components on the full length-counted string, but the result is handed to
`open`/`opendir`/`stat` as a C string. `"..\0"` is a 3-byte component, not `..`, so it passes; the OS sees `<root>/..`.
Any bytes after the NUL are ignored (`"in.txt\0anything"` reads `in.txt`). The interpreter (Rust) refuses all NULs with an
`Err(Failed(..))`, so the two backends also disagree on every NUL path.

**Repro:** `repros/01-fs-nul-escape.tn` (fixture: `setup-fs.sh`, run from `/tmp/tq`, jail = `/tmp/tq/jail`).

| | `tenon run` (exit 0) | native (exit 0) |
|---|---|---|
| `jail.list("..\0")` | `Err(Failed("..\u{0}: file name contained an unexpected NUL byte"))` | `Ok(["jail", "outside"])` (**parent of the jail**) |
| `jail.is_dir("..\0")` | `false` | `true` |
| `jail.exists("..\0")` | `false` | `true` |
| `jail.read("in.txt\0anything")` | `Err(Failed("in.txt\u{0}anything: file name contained an unexpected NUL byte"))` | `Ok("hi\n")` |

**Expected:** every path containing NUL is rejected with the same `Denied`/`Failed` error in both backends.
**Impact:** an attenuated `Fs` leaks the existence and names of everything next to its root (one level up). Reading outside
needs more than a single component, so only listing/stat of the parent escapes. The other operations go through the same
`tn_fs_path` + C-string path; I verified `mkdir("..\0/zz")` (`Ok(())` native, `Err(Failed(..))` in `run`) and `rename` (native attempts the
rename, `run` refuses), not the rest.

## 2. Generic wrapper bypasses linear/unique rules (high)

**Property:** §12/§13 "a module is the only place that can create a value of its type or finish a linear one: privacy is
unforgeability"; "generic functions other than unwrap/expect cannot take it (they might copy or drop)".

**Cause:** the rule "inside a method of the type itself, `self` is exempt" is applied to `struct Wrap[A]` even when `A` is a
linear type from another module. Any program can declare a one-line generic struct with a method `fn Wrap[A].drop_it(self)`
or `fn Wrap[A].dup(self) -> (Wrap[A], Wrap[A]) { (self, self) }`; `Wrap[vaultlib.Tok]` is then auto-linear, but its own
methods may do anything with `self`. (Prelude generics such as `Option.is_some` are rejected correctly because they go through
the generic-parameter analysis; the user-method path skips it.)

**Repro:** `repros/19-linear-generic-wrapper-bypass.tn` with `repros/vaultlib.tn` (`pub linear struct Tok`, private construction, only disposal `Tok.finish`).

* `tenon check`: accepted. `tenon run`: `1 2`, exit 0. native: `1 2`, exit 0.
* `Tok` created by `vaultlib.mk_tok()` is dropped by `drop_it()` without `finish`; a second `Tok` is duplicated into two owners.
* The same works for `unique` handles: `let (a, b) = Wrap { v: sys.net.listen(0).unwrap() }.dup()` is accepted (both backends, exit 0), so a `Listener`/`Conn` ("cannot be copied") is copied.

**Expected:** compile-time error ("may copy or drop values of its type parameter A") whenever a wrapper method's `self` would be copied or dropped with a linear/unique argument, i.e. the exemption must apply only to types declared `linear`/`unique`.

## 3. Match guard consumes a linear value that a later arm consumes again (high)

**Status: FIXED in 1b2420c (`a match guard cannot consume 't'`; bound variables, nested blocks and `if` in guards also rejected).**

**Property:** §12 "must be consumed exactly once"; the task list names "match guards".

**Repro:** `repros/03-linear-guard-double-consume.tn`. `tenon check`: accepted.
`tenon run`: stdout `closed 7` / `closed 7`, exit 0. Native: the same, exit 0. The one `Tok` was consumed (`close`) twice.
**Expected:** error: `t` is consumed in a guard that may fall through. (Variants where the guard merely *inspects* are correctly accepted.)

## 4. Linear temporaries are dropped by "inspecting" operations (high)

**Status: FIXED in 1b2420c (`this linear value is created here and never consumed`; paren, block, `if`, tuple, `unwrap()`, `match`, index, `while` condition, range and interpolation variants of the temporary all rejected).**

**Property:** §12 "reading fields, comparing and formatting do not consume it ... every path must consume it"; no silent loss.

The rules treat field read, `==`, formatting and `ref` arguments as non-consuming, which is right for a *variable* but
loses a value that has no variable.

**Repro:** `repros/04-linear-temporary-dropped.tn` — four lines, all accepted by `check`:
`mk().id`, `mk() == mk()`, `"{mk()}"`, `peek(mk())` (`peek(t: ref Tok)`).
`tenon run`: `1 true Tok { id: 1 } 1`, exit 0. Native: identical, exit 0. A plain `mk()` statement and `let _ = Some(mk())` are correctly rejected.
**Expected:** error "linear value would be dropped" for each.

## 5. `within` / `read_only` follow symlinks (medium)

**Status: FIXED in 1b2420c for paths (symlink anywhere along `path`, incl. file links, absolute links, `link/`, `./link`, `within(link)` -> denied, both backends). Residual: `.tmp` of `Fs.write` -> finding 21; the check/use race is acknowledged in the code comment.**

**Property:** "An attenuated `Fs` can only reach paths under its root".

**Repro:** `repros/02-fs-symlink-escape.tn` (fixture has `jail/link -> ../outside`). Identical in both backends, exit 0:
```
read:   Ok("SECRET\n")        write:  Ok(())     rename: Ok(())
mkdir:  Ok(())                remove: Ok(())     list:   Ok(["newdir"])
```
(file `outside/secret.txt` is read, then moved into the jail by `rename`; `outside/pwned.txt` and `outside/newdir` are created/removed).
`read_only()` denies by operation (not tested through the link), but reads cross.
**Expected:** resolve and re-check, or open with `O_NOFOLLOW`/`openat` per component; or document that symlinks are out of scope. By reading
the code (not tested), the temp file of `Fs.write` (`<path>.tmp`, `O_CREAT|O_TRUNC`) would also follow a pre-planted symlink.

## 6. `..base` drops the replaced linear field (medium)

**Status: FIXED in 1b2420c (`'..' would drop the base's linear field`).**

**Repro:** `repros/05-linear-struct-update-drops-field.tn`: `Two { a: Tok { id: 3 }, ..t }` discards `t.a`.
`check` accepts; `run` and native exit 0 with no output. `let _ = t.a` is rejected, `t.a = ...` is rejected ("cannot overwrite a linear value in place").
**Expected:** reject struct update that replaces a linear field of `base` (or require the old field to be consumed first).

## 7. A struct holding a `fn` is comparable / hashable (medium)

**Status: FIXED in 1b2420c for `==`/`<` through struct/enum fields and for map/set keys (`Hf cannot be compared: they contain the function type`); still reachable through generics: finding 20.**

**Property:** §4 "Functions and capabilities cannot be compared"; `Option[fn]`, `List[fn]`, `(Console, Int)` are rejected correctly.

**Repro:** `repros/06-fn-field-compare.tn` (`struct Hf { f: fn() -> Int }`, `a == a`; `Map[fn() -> Int, Int]`).
* `tenon run`: prints `true`, then `trap: key not found: <fn>` / `at 06-fn-field-compare.tn:9:6`, **exit 70**.
* native: prints `false` then `2` (two entries for the same function key), **exit 0**.

**Expected:** compile-time rejection, as for the other containers. (Same class: `xs.sort()` on `List[fn]` is accepted.)

## 8. NaN as a map key (medium)

**Status: FIXED in 1b2420c (`Float cannot be a map or set key`; also found through inference, generic helpers and tuples/lists/structs of Float). NaN in `List[Float].sort()` is unchanged (unsorted result, silently).**

**Repro:** `repros/07-nan-map-key.tn` (`m[nan] = 1; m[nan] = 2`).
`tenon run`: `trap: key not found: nan` at `07-nan-map-key.tn:6:6`, **exit 70**. Native: `[nan: 1, nan: 2] 2 None`, **exit 0** (entries that can never be found or removed; the map grows on every insert).
**Expected:** one behaviour in both backends; best a check-time rejection of `Float` keys, or a defined NaN-key rule.
Related, same on both backends: `List[Float].sort()` with NaN returns an unsorted list silently (`[3.0, nan, -0.0, 0.0, 1.0, nan, -1.0]`).

## 9. Network ports are truncated (medium)

**Status: FIXED in 1b2420c (both `listen` and `connect` return `Failed("...: port must be 0-65535")`, both backends).**

**Repro:** `repros/08-net-port-truncation.tn`. Identical in both backends, exit 0:
`listen(73616)` -> bound port **8080**; `listen(-1)` -> **65535**; `listen(65536)` and `listen(4294967296)` -> a random port (they became port 0).
`connect(host, p)` truncates the same way, and its error texts differ between backends (`connect("", 80)`: run `failed to lookup address information...`, native `Connection refused`).
**Expected:** `Err(Failed("port out of range"))` (or a trap) for ports outside 0..65535.

## 10. Native stack overflow on a deep recursive value (medium)

**Status: FIXED in 1b2420c for boxed enums (`Cons` chain drop and the copy/COW paths now work). Not fixed: struct `List`/`Map` chains (22) and derived ==/</hash/fmt/codec (23).**

**Property:** native = interpreter; resource limits are the traps in §9, not behavioural differences.
**Repro:** `repros/09-deep-enum-native-stack-overflow.tn` (1,000,000 `Cons` cells, no user recursion).
`tenon run`: `built`, `dropped`, exit 0. Native: `built`, `trap: stack overflow`, **exit 72** (recursive release at `c = Nil`).
`mk() == mk()` on two such values behaves the same way (run: `true`, native: exit 72). A long list/stack/queue implemented as an enum can't be freed.
**Expected:** iterative release/compare, or interpreter and native sharing one documented depth limit.

## 11. `tenon build` does not terminate / crashes on polymorphic recursion (medium)

* `repros/10-polymorphic-recursion-hangs-build.tn` — `check` and `run` fine (`0`, exit 0). `build`: no output, runs until killed (still running after 15 s; infinite monomorphization).
* `repros/11-polymorphic-recursive-type-crashes-build.tn` — `check` and `run` fine (`Wrap(Leaf([1]))`). `build`: after ~26 s `thread 'main' has overflowed its stack / fatal runtime error: stack overflow, aborting`, **exit 134**.
**Expected:** an instantiation-depth limit with a diagnostic.

## 20. Function/capability comparison still reachable through generics (medium; fix for 7 incomplete)

**Repro:** `repros/20-fn-compare-via-generics.tn` (`check` accepts). Output, exit 0 in both:
```
run:    true Some(0)      native: false None      <- xs.contains(a) / xs.index_of(a), a = Hf { f: one }
        false false               false false      <- same(one, one) via `fn same[A](a: A, b: A) -> Bool { a == b }`, and [console].contains(console)
```
`xs.sort()` on `List[Hf]`, `zs.sort_by(fn(x) => one)` (function-valued key) and `[console, console].sort()` are accepted too.
The comparability check runs on the binary operator at its use site; generic bodies (`List.contains` in the prelude, user generics) are
checked with an abstract `T`, and the instantiation is never re-checked. **Expected:** reject at the instantiation (`contains` on `List[Hf]` etc.),
or check `T`'s comparability in the generic call.

## 21. `Fs.write` temp file follows a planted symlink (medium; fix for 5 incomplete)

**Repro:** `repros/21-fs-tmp-symlink-write.tn` + `setup-fs.sh` (plants `jail/f.txt.tmp -> ../outside/target.txt`; run from `/tmp/tq`).
`jail.write("f.txt", "PWNED")` -> `Ok(())` in both backends; afterwards `/tmp/tq/outside/target.txt` contains `PWNED` and `jail/f.txt` is itself a
symlink to it (`rename` moved the planted link over `f.txt`). The symlink check runs on the components of `path` only, not on `path + ".tmp"`.
**Expected:** `O_NOFOLLOW|O_EXCL` for the temp file with a unique name (or `mkstemp` in the target directory), and refuse if it already exists.

## 22. Deep chain through a struct's `List` or a `Map` still overflows on release (medium; remainder of 10)

**Repro:** `repros/22-deep-struct-list-release.tn` (1,000,000 nested `Tree { kids: [t] }`). run: `built` / `dropped`, exit 0. Native: `built` / `trap: stack overflow`, **exit 72**.
Same for `enum Chain { End, Next(Map[Int, Chain]) }` (500,000 deep). The deferral added in `1b2420c` is only in the boxed-enum release.
(`Next(Option[Chain])`, `Cons(Int, Chain)` and the copy-on-write paths now work.)

## 23. Derived ==, <, hash, to_str, encode, decode recurse on the native stack (medium; remainder of 10)

**Repro:** `repros/23-deep-enum-eq-hash-fmt-codec.tn`. run: `true`, exit 0. Native: `trap: stack overflow`, **exit 72**, no output.
With the same 1,000,000-deep `Cons` chain: `<`, using it as a `Map` key, `c.to_str()` and (300,000 deep) `encode` + `decode` give the identical
split (run succeeds: `false`, `1`, `13888893`, `4088893 true`; native exit 72). Either make the generated code iterative, or give the interpreter the same
depth limit so the two backends at least agree (and document the limit next to exit code 72).

## 24. Native `Net.connect` truncates the host at NUL (low)

**Repro:** `repros/24-net-connect-nul-host.tn`. run: `Err(Failed("127.0.0.1\u{0}evil.example:9: file name contained an unexpected NUL byte"))` and
`Err(Failed(":80: failed to lookup address information: ..."))`. Native: `Err(Failed("127.0.0.1:9: Connection refused"))` (host truncated; it really connected)
and `Err(Failed(":80: Connection refused"))`. `Net` has no host attenuation, so this is a divergence, not an escape. Messages for unresolvable names also differ
(`no.such.host.invalid:80`: run `failed to lookup address information...`, native `No route to host`).

## 12-18. Low severity

* **12** `repros/12-map-ordering-accepted.tn`: `a < a` on `Map[Int, Int]` passes `check`; both backends then `trap: maps are not ordered` at 4:29, exit 70. §4 says maps are not ordered; this should be a check error like `fn` comparison.
* **13** `repros/13-const-cycle.tn`: `const A1 = B1 + 1; const B1 = A1 + 1` is accepted; using `A1` gives `trap: stack overflow`, exit 72 in both backends. Unused constants are never evaluated (the program without the use prints and exits 0). A division by zero or overflow in a constant is likewise a run-time trap at first use rather than a compile error.
* **14** `repros/14-compound-assign-order.tn`: prints `15 6` in both backends. Binary operators capture the left operand first (`b + {b = 10; 5}` = 6), but `a += {a = 10; 5}` reads `a` after the right side (= 15). Same for `xs[0] += {...}`.
* **15** `repros/15-uninferred-type-accepted.tn`: `let xs = []` and `let o = None` pass check and run (`ok`, exit 0), leaving an unresolved type variable (docs say to annotate).
* **16** `repros/16-run-nonutf8-arg-panics.tn`: `tenon run F.tn $'\xff'` -> `called Result::unwrap() on an Err value: "\xFF"` (Rust panic, **exit 101**); the compiled program prints `["�"]`, exit 0.
* **17** `repros/17-trap-location-in-prelude.tn`: `INT_MIN.abs()` -> `trap: integer overflow` / `at <prelude>:32:41` (both backends, exit 70). Same for `List.sum` overflow. The user's call site is not reported.
* **18** `repros/18-nested-tuple-index.tn`: `t.0.1` -> `error: expected a name, found '0.1'` (exit 1).

## Minor observations (no repro file)

* `Str.pad_left(5, "xy")` of `"ab"` is `"xyxyxyab"` (fill is repeated `width - len` times, so the result is longer than `width` with a multi-byte or multi-char fill). Same in both backends.
* `encode` prints control characters as `\u{1}` but the language has no `\u` escape (`unknown escape '\u'`), so encoded text is not valid Tenon literal syntax, although `decode` accepts it.
* A `main` that returns `Err(..)` (and the `tour` / `errors` corpus programs) exits with one more live allocation than a clean exit (the error value is never freed; allocation-counting build, live=2 vs 1). Harmless at exit, but it contradicts "leak-free" if checked mechanically.
* `"abc".repeat(INT_MAX)` / `pad_left(INT_MAX, ..)` loop pushing into a list for as long as memory lasts (both backends) instead of trapping out of memory; I killed these runs. I did **not** safely test the OOM exit code 71 (the doubling-string/list programs consumed >20 GB before I killed them on the interpreter and on native), so the interpreter's missing OOM handling is untested.

## What held up (no bug found)

Method: ASan+UBSan builds of the generated C (`-fsanitize=address,undefined`), an allocation-counting `malloc` wrapper (macOS ASan has no leak detector), and interpreter-vs-native diffing of stdout, stderr and exit code.

* **Memory safety / COW:** aliasing through `mut self` methods (`b.add_all(b.items)`, `a.add(a)`), `mut` parameters with by-value aliases of the same place, list mutation while iterating, `Str +=` in place with shared/sliced/captured/self-appended strings, `m[k].push`, `m[k] += v` on snapshots, closures capturing lists/maps, nested containers, map insert/remove stress (30k random ops, snapshots, removal during iteration), recursive enums, match bindings that outlive reassignment of the scrutinee. All ASan/UBSan clean, no leaks, interpreter and native identical. The whole `tests/run` corpus is ASan clean.
* **Differential fuzz:** 277 valid mutants of `tests/run` programs (operators, integer literals, strings) gave identical stdout/stderr/exit code in both backends; 400 syntax-level mutations gave no compiler panic or hang in `tenon check`.
* **Evaluation order:** call arguments, struct literal fields, operands, assignments, short-circuit, guards, `if`/`match` conditions: identical and left-to-right in both backends.
* **Type checker:** `let` mutation (fields, elements, nested, parameters, `self`, rvalue receivers), implicit Int/Float/Bool/Str conversions, non-exhaustive/unreachable/guarded/or-pattern/nested matches, ignored `Result` (statements, branches, closure bodies, loop bodies, `fn()` coercions), `?` mismatches, shadowing (closures, match binds, loops), closure capture mutation, `let ... else` non-diverging blocks, `const` mutation, `mut` argument misuse and aliasing.
* **Authority:** no way to construct `Console`/`Fs`/`Net`/`Clock`/`Sys`, `decode` them, `extern` them, redefine prelude types, or reach I/O without `main`'s `Sys`; `..`, absolute, empty, `sub//..` paths are denied; `read_only` denies write, append, remove, mkdir and rename (including after `within`).
* **Linear types:** loops, `?`, `return`/`break`/`continue`, closures, `or`-patterns, short-circuit `and`/`or`, `while` conditions, tuples, `Option`/`Result` helpers (`is_some`, `unwrap_or`, `ok`, `map`), `ref` parameters (consume/return/store/forward), `mut` parameters of linear type, `encode`/`decode`, generic analysis (`first[A, B]`, `bad[A](x: ref A)`).
* **Module privacy:** construction, field read/write, struct update, private functions/methods, `encode`/`decode` of private-field types, foreign method definitions. (Derived `==`/`<` on a foreign type compares private fields, which §4 specifies.)
* **Traps:** location, message, exit code 70/72, and flushed stdout/stderr ordering are identical in both backends for overflow (all operators incl. `INT_MIN / -1`), division, slices (byte boundaries), indices, map keys, `unwrap`/`expect`/`panic`/`assert`, float-to-int, `char`, and for `main` returning `Int`/`Err`.
* **Codec:** `decode` is canonical-only and identical in both backends across ~100 malformed/non-canonical inputs.

## Fix verification notes

After `1b2420c` I re-ran repros 01-09 (all FIXED in both backends) and the earlier probe batteries: ~20 guard/temporary/struct-update variants
(all rejected as intended), 12 Fs NUL variants and 17 symlink variants (all denied identically in both backends except 21), the port range for
`listen` and `connect`, and Float/fn/capability map keys (rejected, including through inference and generic helpers). The temporary deferral
used for the enum-release fix also shows one extra live allocation at exit under the counting `malloc` (live=2 vs 1 for `Next(Some(t))` and
`Cons` chains; the counter is not a leak detector for allocations that stay reachable, so treat as unconfirmed).

## Caveats

* The checkout changed under me (`mut` parameters, `let ... else`, constants, `Fs.rename`, etc. landed during the session); all repros were re-verified against the binary built from the final working tree.
* While fuzzing I briefly wrote a temporary file (`_fz11.tn`) next to a corpus program inside the repo's `tests/run/` for a few seconds; I removed it immediately and `git status` shows no change from me. Everything else was written under `redteam/` and `/tmp/tenon-qa/`.

## Status after fixes (verified 2026-10-28 by re-running every repro on main)

| # | Finding | Status | Fixed by |
|---|---|---|---|
| 1 | NUL byte escapes `Fs.within` | fixed: NUL paths are refused in both backends | 1b2420c |
| 2 | generic wrapper drops/duplicates a linear value | fixed: only types declared linear/unique exempt `self`; `Wrap.drop_it` rejected for linear `A` | 6d7d6ce |
| 3 | match guard consumes a linear value | fixed: rejected | 1b2420c |
| 4 | linear temporaries dropped | fixed: rejected | 1b2420c |
| 5 | `within` follows symlinks | fixed: existing symlinks on the path are refused (TOCTOU race documented) | 1b2420c |
| 6 | `..base` drops a linear field | fixed: rejected | 1b2420c |
| 7, 20 | comparing functions | fixed: rejected when written directly or through struct fields; through generics, functions (like NaN) are never equal, consistently in both backends (interpreter no longer short-circuits on Rc identity) | 1b2420c, 6331822 |
| 8 | NaN map keys | fixed: Float (and fn/capability) keys rejected | 1b2420c |
| 9 | ports truncated | fixed: out-of-range ports are errors | 1b2420c |
| 10, 22, 23 | native stack overflow on deep values | fixed: bounded-depth release, and native main runs on a 1 GB stack like the interpreter | 1b2420c, 6331822 |
| 11 | polymorphic recursion hangs/crashes `build` | fixed: clear compile error | 6d7d6ce |
| 12 | `<` on maps accepted | fixed: compile-time error | 6d7d6ce |
| 13 | constant cycles | fixed: compile-time error | 6d7d6ce |
| 14 | `x += e` vs `x = x + e` order | documented (reference §6) | 6d7d6ce |
| 15 | uninferred `let` | fixed: compile-time error | 6d7d6ce |
| 16 | non-UTF-8 argument panics the interpreter | fixed: lossy in both backends | 6d7d6ce |
| 17 | trap location inside the prelude | fixed: reported at the user call | 6d7d6ce |
| 18 | `t.0.1` | fixed in both lexers | 6d7d6ce |
| 21 | `Fs.write` temp-file symlink | fixed: stale temp removed, created O_EXCL\|O_NOFOLLOW | 6d7d6ce |
| 24 | NUL in `connect` host | fixed: refused, messages normalized | 6d7d6ce |

Not yet tested: out-of-memory behaviour (exit 71).

## Capability-escape probes (a later pass; moved into the corpus 2026-10-28)

24 one-line probes (`a01_*.tn` ... `a24_*.tn`) were committed at the repository root by accident. None escapes:
the 18 the checker rejects are `tests/reject/cap_probe_*.tn` (each with its expected diagnostic); the 5 it accepts
with a meaningful, deterministic result are `tests/run/cap_probe_*.tn` (formatting a capability prints `<Fs>`;
`panic()` as a `Console` and indexing an empty `List[Clock]` trap; copying capabilities into a list grants nothing new;
a user variant named `Some` is allowed). The remaining one is kept here:

* **25** `repros/25-import-std-override.tn`: `import journal` with no `journal.tn` beside the importer resolves to the
  standard module (exit 0, no output). A local `journal.tn` would take precedence (module lookup is local file first,
  then the standard library), which is by design and not an escape: a module gets authority only through parameters.
  It pins nothing the corpus does not already cover (`tests/run/std_journal_cr.tn`), so it is not a test.
