# Notes (Tenon usability study)

## General documentation issues
- reference.md links to `src/prelude.tn` and `std/journal.tn`, and mentions `docs/log.md` and `./check`/`tests/`; in the kit these are `docs/prelude.tn`, `docs/std-journal.tn`, and the others don't exist.
- §10 shows `struct Sys { console, fs, clock, args }` without `net`, but prelude's Sys has `net: Net` and §15 uses `sys.net`.
- No documented way to write a `trim` that only removes spaces/tabs (trim removes all ASCII whitespace) – I wrote a helper. A `trim_matches`/predicate-based trim would help.
- Not documented: whether `main` returning `Int` lets me exit with code 2/3 cleanly (it did – good), or how to print to stderr AND exit with a code (combination works fine).
- Unclear whether `{}` is a valid Unit expression in a match arm (`None => {}`); it is.

## Task 01 (cfgcheck)
- Compiled first try. Matching on a `Str` with string-literal patterns, guards on tuple patterns inside `Some(...)`, and `Str.is_empty` as a function value all worked as hoped.
- Wished for: a `Str.strip_suffix`/`trim_end_matches("\r")`, and an `Int.is_ident`-style char class for `_`.

## Task 02 (ldiff)
- Compiled first try. Wished for a `List.filled(n, x)` / `[0; n]` constructor; had to push in a loop to build the LCS table. No 2-D array type either (used flat list).
- Doc doesn't say whether `if` used as the right-hand side of an indexed assignment spanning lines is OK (it is).
- Unclear from docs whether `Str.lines()` drops only one trailing empty line (e.g. "a\n\n" → ["a", ""]); assumed so.

## Task 03 (datecalc)
- Compiled first try. `const` of type `List[Str]` worked (doc says "any expression", good).
- No floor division / Euclidean modulo (`div_euclid`/`rem_euclid`); had to fix up negative `%` by hand for month arithmetic.
- No string builder; `out = out + c.char()` in a loop – unclear from docs whether that is quadratic. Byte-to-string for ASCII needs `Int.char()`, which works on code points, so copying a UTF-8 string byte-wise this way would corrupt it – a `Str.slice` based approach is needed; doc could warn.
- Would like `Str.is_digits()` / a strict `to_int` (to_int accepts `+`, which most specs here reject), so I reimplemented digit checks.

## Task 04 (lfagg)
- **Doc vs compiler mismatch**: reference §7 says "`while true { ... }` with no `break` never finishes, so a function may end with it". My function ended with `while true { ... }` whose body had no `break` of its own — the only `break` was in a *nested inner* `while` loop — and the compiler rejected it with:
  `error: this block must end with a value of type Option[Map[Str, Str]]` pointing at the `while true`. So a `break` belonging to a nested loop seems to count. The error message doesn't mention the `break` or the rule, which made it confusing. Worked around it by extracting the inner loop into a helper.
- `groups[k].count += 1` and `groups[k].min = groups[k].min.min(v)` on map entries worked as documented. Nice.
- Wished for `Option.and_then`/`flatten`: I wrote `pairs.get(f).map(numeric).unwrap_or(None)`.
- No `trim` variant for spaces only (again).

## Task 05 (gradebook)
- **Confusing error**: matching `Ok(()) => 0` on a `Result[Unit, Str]` gave
  `error: type mismatch: expected Unit, found ()` — `()` is documented (§2) as "the only value of type Unit", so this message reads as a contradiction. Apparently `()` isn't allowed as a *pattern* (patterns list in §7 doesn't include it, but the error should say so). Used `Ok(_)`.
- **Missing feature**: no sort with a comparator (`sort_by` takes only a key function). Sorting by an exact rational `P/M` descending can't be expressed as a key without big ints, so I hand-wrote a merge sort. A `sort_with(fn(a, b) -> Ordering)` / `cmp` would help.
- Nested map entry assignment `graded[id][assignment] = v` worked. `Int.is_alnum` as a function value worked.

## Task 06 (alertwin)
- Compiled first try. Mutating a struct inside a map entry (`services[name].errors_at.push(t)`, `services[name].head += 1`) works, but it forces repeating `services[name]` on every line. Wished for a way to borrow a mutable reference to a map entry (e.g. `with services[name] as s { ... }` or a `mut` local alias), or to pass `mut services[name]` to a helper (didn't try; the docs only show `mut` args on variables).
- Unclear whether `let s = services[name]` copies the whole List (docs say COW, so presumably cheap until mutated) — I avoided it in the hot path to be safe.
- No deque type; used List + head index.

## Task 07 (ratelimit)
- Compiled first try. Matching on a tuple `(t[0], t.len())` with string/int literal patterns, and `?` inside variant constructors, made the parser very compact.
- **Perf model unclear**: the docs say values are copy-on-write but don't say when a copy is made if I hold `let p = self.policies.get(name)` and then mutate `self.policies[name].buckets[...]` — does the outstanding `p` force a full copy of the buckets map? I restructured defensively to never hold such a copy. A short "performance model of COW" paragraph in the reference would help.
- `let _ = m.remove(k)` needed to discard the Option — fine, documented.

## Task 08 (inventory)
- Compiled first try. Methods with `mut self` on a struct containing another struct with `mut self` methods (`self.expiry.push(...)`) composed nicely. Or-patterns binding the same name (`Commit(id) | Release(id)`) worked.
- **Missing**: no priority queue / heap in the prelude; wrote a binary heap (~40 lines). Also no `List.swap(i, j)`.
- Struct update `Stock { held: st.held + n, ..st }` was handy.

## Task 09 (tally)
- Compiled first try; the `Fs` API (write is atomic+durable, append is durable, `within`, `rename`) fit the task exactly. `Err(NotFound(_))` patterns on `IoError` are nice.
- **Missing**: no truncate; to cut a log back to its valid prefix I write a temp file and rename it. Fine but a `Fs.truncate` would be more direct. No way to get the parent of a path (`path.parent()`), and `Fs.mkdir` always creates parents — I had to hand-parse the path to enforce "only the last component is created".
- **Missing**: no `if let` / `is` pattern test in expressions; to handle a `Result[Unit, Str]` I needed a full `match` with an empty `Ok(_) => {}` arm.
- Spec-level note (not Tenon): commands carry ≤15-digit ints but values may reach 1e17, so COMPACT can write 18-digit S records; I accept up to 18 digits when replaying.
- Docs don't say whether `fs.exists`/`is_dir` on an unattenuated Fs accept paths with trailing `/` (assumed yes).

## Task 10 (servsim)
- Compiled first try. A generic `struct Heap[T]` using `<`/`>` on `T` worked with no trait bound, because every type is ordered (§4). `break` as the value of a `match` arm in a `let` worked.
- Needed a min-heap again (second time, after task 08) — strong case for a prelude `Heap`/priority queue.
- Wished for `Option.is_some_and(pred)`; wrote `opt.map(pred).unwrap_or(false)` several times.

## Top 10 points
1. **`while true` doc/compiler mismatch** (task 04): §7 says a function may end with `while true { ... }` with no `break`, but a `break` in a *nested* loop makes the compiler reject it with the unhelpful `error: this block must end with a value of type Option[...]`.
2. **`Ok(())` pattern error** (task 05): `error: type mismatch: expected Unit, found ()` — contradicts §2 ("`()` is the only value of type Unit"). Either allow `()` as a pattern or give a message that says unit patterns aren't supported.
3. **No comparator sort**: `sort_by` only takes a key; sorting by an exact ratio needed a hand-written merge sort. Want `sort_with(fn(a, b) -> Int)` or similar.
4. **No heap / priority queue** in the prelude; I wrote one twice (tasks 08, 10). Also no `List.swap`, no `List.filled(n, x)`, no deque.
5. **Doc paths are wrong for the kit**: reference links `src/prelude.tn`, `std/journal.tn`, `docs/log.md`, `tests/`, `./check`; the kit has `docs/prelude.tn` and `docs/std-journal.tn` and nothing else. §10's `Sys` struct omits the `net` field that the prelude and §15 have.
6. **COW performance model undocumented**: unclear whether holding `let p = m.get(k)` while mutating `m[k]...` forces a full copy, and whether `s = s + x` in a loop is quadratic. I wrote defensive code. One paragraph would fix it.
7. **Mutating map entries is verbose**: `services[name].x += ...` repeated on every line; wish for a mutable alias / passing `mut m[k]` to a helper (docs only show `mut` args on variables).
8. **Missing small string helpers**: trim that removes only spaces/tabs, strip one suffix (`"\r"`), strict digit-only `to_int` (`to_int` accepts `+`), `is_digits`. Every task re-implemented these.
9. **Missing Option/Result combinators**: `and_then`/`flatten`, `is_some_and`, `if let`/`is` pattern tests; also no Euclidean `div`/`rem` for negative numbers (task 03).
10. **Fs gaps**: no `truncate`, no path helpers (`parent`), and `mkdir` always creates parents (task 09 needed "only the last component"). On the plus side, the Fs semantics (atomic write, durable append, `rename`) are well documented and fit perfectly.

Positive overall: 8 of 10 tasks compiled on the first attempt (the 14 compile-error log entries come from tasks 04 and 05, where I ran a batch of examples against one broken build); string/tuple literal patterns, `?` inside constructors, struct update, or-patterns and `let ... else` made the code compact and readable.
