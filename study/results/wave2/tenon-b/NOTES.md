# NOTES (Tenon study, kit tenon-b)

## Task 01 cfgcheck
- try.sh does `cd` to the kit dir, so relative paths in test args must be relative to the kit root, not my cwd. (Not in docs; hit it immediately.)
- Docs gap: `main` returning Int is stated in §9 but there is no example of a CLI using exit codes; worked first time.
- Docs: `match` arm `x => stmt` with assignment (`"-q" => quiet = true`) worked; not documented whether assignment is allowed as an arm expression.
- Docs gap: no string-slicing-by-char / byte-to-char helper other than `Int.char()`; `s.byte(i)` + `Int.is_lower()` etc. was enough.
- `trim`/`words` treat `\r` as whitespace, which differs from the spec's "spaces and tabs", so I wrote my own trim/tokens helpers (a `trim_chars(set)` or `split_ws` variant would help).
- Wish: `Str.split_whitespace` that only splits on space/tab; `List.enumerate`; `Str.all(pred)`.

## Task 02 ldiff
- No issues; compiled and passed first time. Flat `List[Int]` as 2D table worked (4M pushes fast enough). No 2D array / `List.repeat(n, v)` / `List.filled` builtin; wished for one (had to push in a loop).
- Wish: `List.enumerate()` / `zip`; `for (i, x) in xs`.
- Docs unclear: whether `"\n".lines()` is `[""]` (assumed yes).

## Task 03 datecalc
- No compiler errors. Observed: `match` with alternatives of int literals (`4 | 6 | 9 | 11 =>`) and a match used as an `if`-expression value inside arms worked.
- Docs gap: `Int.to_str` is listed, but `Int.pad`/formatting width isn't; used `to_str().pad_left(w, "0")`. Fine, but negative numbers would pad as `00-5`; had to be careful.
- Docs gap: no floor division/modulo for negatives (`div_floor`, `rem_euclid`); I avoided it by range-checking first. A `Int.div_floor` would have been handy for month arithmetic.
- Docs: the `const` with `//` trailing comment fine. Not documented: whether `const` can be used in patterns.
- Docs: `let x = match ... { _ => { ...; return 2 } }` (arm diverging with return inside block) works; this isn't spelled out in §7 (only `let ... else`).

## Task 04 lfagg
- Compile error from my own typo was clear: `error: type Option[Str] has no method 'and_then_numeric'` (with caret). Good message. Missing from the Option API: `and_then` / `flat_map`, `filter`, `or_else`, `map_or`; I wrote a helper with `?` instead.
- `while true { ... break }` plus `continue` worked as documented.
- Overflow trap on Int made me compute the average with integer division/remainder (sum*100 could overflow); no `Int.div_rem`, and no decimal formatting of Floats (no `Float.format(2)`), so exact-rounding by integer math was needed. A fixed-precision float formatter would be a common need.
- `sort_by(fn(e) => (-e.1.count, e.0))` works as documented (tuple keys). Tuple field `.1.count` chained OK.
- Docs: `Map.entries()` documented only in §11 list; `for (k, v) in rows` over a List of tuples worked (pattern in for) though docs only show it for maps.
- Docs: `string += string` in a loop worked and is fast enough for 200k lines.

## Task 05 gradebook
- Passed first time. Nested-map assignment `grades[id][assignment] = (p, m)` worked, though §6 only documents `m[k].push(x)` / `m[k] += 1` (worth one more line stating that nested index assignment works).
- Big missing piece: no way to sort with a custom comparator (`sort_by` takes only a key). Ordering by exact ratio P/M needed cross-multiplication, so I wrote a generic merge sort `merge_sort[T](xs, less: fn(T,T)->Bool)`. A `sort_with(cmp)` builtin would be very useful. Passing the named function `before` as a `fn(T,T)->Bool` value worked.
- Overflow trap on multiplication made me write an overflow-free ratio comparison (Euclid-like); a 128-bit or `Int.mul_div` helper would help.
- `let slot = match g { "A" => 0, ... }` string-literal patterns work.
- `if ... { "A" } else if ... { "B" }` chain with `else` on a new line: worked (docs say lines starting with `else` continue).
- Docs unclear: can a struct be declared after use in file (order independence)? Yes, `Score` declared mid-file worked.

## Task 06 alertwin
- Passed first time; 200k lines in 0.3s. In-place nested update `svcs[name].times.push(t)` and `svcs[name].head += 1` work and are not quadratic (good), but this is only implied by §6 ("a field/element of one, including map entries"). I was unsure whether `m[k].field.push(x)` copies the list (copy-on-write sharing with a local); docs have no performance note on it. Avoided `var s = svcs[name]` copy-modify-writeback for that reason.
- Verbose: `svcs[ev.service].x` repeated many times; no way to take a mutable alias/reference to a map entry (`let ref s = ...` / `with_entry(k, fn)`); wished for one.
- `let Some(v) = parse_option(...) else { return 2 }` on one line works.
- Docs: `match` arm as a statement `"-w" => { ... }` followed by a trailing `,` after `}` accepted.

## Task 07 ratelimit
- PERFORMANCE TRAP (biggest finding): `let Some(p) = policies.get(name)` binds a *copy* of a struct that contains a Map; while `p` is alive, `policies[name].buckets[client] = b` triggers a full copy-on-write of the 50k-entry map each time. 100k commands took 31 s; after reading scalar fields via `policies[name].capacity` and never holding the struct in a local, 0.4 s. The docs mention COW (§3) but nothing about the gotcha that a live local alias makes mutation O(n), and nothing about how to update a nested value cheaply. Need a doc paragraph "performance model for mutation" + ideally an entry-style API.
- `mut` parameters (`policies: mut Map[...]`, `mut policies` at call) worked first try in a function that is a `match` returning Str with early `return`s.
- `con.read_line()` + `let Some(line) = con.read_line() else { break }` fine. `con.flush()` fine.
- Wish: `Map.entry(k)`/`update(k, fn)`, `Option.map_or`, `Map.remove` returning Option forced `let _ =`.

## Task 08 inventory
- Passed first try; 100k commands in 0.4 s (applied the task-07 lesson: scalar-only values in maps, one struct of state passed as `mut`).
- No priority queue / heap in the prelude; wrote a binary min-heap over `List[(Int, Int)]` with `mut` params. Tuple `<=`/`<` comparison worked. A `Heap[T]` or a sorted-map type would be a natural builtin.
- `mut inv: Inv` passing a big state struct and `heap_pop(mut inv.expiry)` (a `mut` argument that is a field path) worked; docs say "caller passes a place marked mut" without saying field paths are allowed.
- Docs: `inv.held[h.sku] -= h.qty` compound assignment through struct->map->key works.
- `Some((time, cmd)) =>` nested tuple pattern in match works.
- Unclear to me whether a `match` arm may be `return "..."` as an expression in a statement position (`Expired => return "ERR expired",`): it compiled.

## Task 09 tally
- Passed first time. Used `Fs.within(dir)`, `read`, `append`, `write`, `rename`, `exists`, `is_dir`, `mkdir`; all behaved as documented. `text.find_from("\n", pos)` was exactly what a scanner needed.
- Docs gap: `Fs.mkdir` "creates missing parents" but the task says only the last component; I had to check the parent with `is_dir` myself. Docs don't say what `exists`/`is_dir` do for non-existent/odd paths (assumed false).
- Docs gap: no way to truncate a file or write a partial file; used `Fs.write` (atomic replace) for the repair. Docs do not say whether `Fs.append` creates the file when missing (it did).
- Docs gap: no way to test crash behaviour (kill) from inside; relies on `Fs.append` being durable per call, which the docs say.
- Enum variant named `List`/`Set` (my own `Cmd.List`, `Cmd.Set`) collides conceptually with builtin type names `List`/`Set`: it compiled, but I was nervous; docs say types and variants share the uppercase namespace and don't say whether a variant may shadow a builtin type name.
- `match` arms of the form `"LIST" => if cond { Some(List) } else { None },` work.
- `panic("...")` as a `match` arm value of type Str works (generic return type).

## Task 10 servsim
- Passed first time; 100k requests / 1000 servers in well under a second.
- Again had to hand-write a binary min-heap (second time: tasks 08 and 10). A builtin priority queue, or an ordered map (`SortedMap`/`BTreeMap`), is the obvious missing collection. With a generic `heap_push[T]` I could not use `<=` on T without an ordering bound; docs say every type supports ordering, so a generic version would likely work, but I did not test it.
- Tuple destructuring `let (_, k) = heap_pop(mut busy_heap)` with a `mut` argument inside a `let` pattern works.
- `fn main(...) -> Int` with early `return 2` inside `let ... else { ...; return 2 }` blocks is idiomatic and worked everywhere.
- `INT_MAX` constant is usable unqualified; ranges `1..(servers + 1)` fine.
- Output batching: `con.print(out.join("\n") + "\n")` fast for 200k lines.

## Top 10 (summary)
1. Copy-on-write performance trap: a live local copy of a struct containing a Map/List (`let Some(p) = m.get(k)`) makes each write to `m[k].inner[...]` copy the whole inner map (31 s vs 0.4 s at 100k commands). Needs a doc section on the mutation cost model plus an entry/update API.
2. `sort_by` takes only a key; no comparator sort (`sort_with(fn(a, b) -> Int)`), so exact-ratio ordering needed a hand-written merge sort.
3. No priority queue / ordered map in the prelude; hand-wrote a binary heap twice.
4. try.sh runs from the kit directory, so relative test paths must be kit-relative (undocumented).
5. `trim`, `words` treat `\r` as whitespace; no way to trim only spaces/tabs or split on only those. Needed own helpers in 01, 02, 04.
6. Option/Result API is thin: no `and_then`, `map_or`, `or_else`, `filter`; Map has no `entry`/`update`/`get_mut`; `Map.remove` result requires `let _ =`.
7. No floor div/mod, no `Int.mul_div`, no fixed-decimal Float formatting: exact rounding and overflow-safe comparisons were by hand with integers (04, 05).
8. Docs do not say whether `m[k][k2] = v`, `inv.f[k] -= x`, or `f(mut inv.field)` (field paths as `mut` args) are allowed; they all work.
9. `Fs.mkdir` creates missing parents although tasks may need "last component only"; `Fs` has no truncate and no explicit statement on `append` creating missing files / `exists` semantics.
10. Wished-for conveniences: `for (i, x) in xs` / `enumerate`, `List.filled(n, v)` (2D tables), `Str.all(pred)`, and a statement that variants may reuse builtin type names (`List`, `Set`).
