# Notes

## 01-wrap
- No compile errors. Writing `main(sys) -> Int` for custom exit codes was easy to infer from §9.
- Unclear: Does `eprintln` flush before returning an Int exit code? (it did.)
- Wished: a `String.char_at`/bytes iterator; used `byte(i)` loops. Also `Str.is_digits` then `to_int` on 4-digit strings is the idiom; fine.
- Wished: `List.join` on non-Str lists, `match` on `args` list patterns (no list patterns documented).

## 02-radix
- No compile errors. Wished: `Int.to_str_radix(base)` / `Str.to_int_radix`; had to hand-roll.
- Unclear: whether `digit_value` style `if/else if` chain as the tail expression of a fn with `else` on a new line works — it did (docs §2 says `else` continues a line), fine.
- Docs don't say how `zsh`-style arg lists reach `sys.args` for args like `-5` — they are passed verbatim, fine.

## 03-globgrep
- No compile errors. Did not need the regex module (hand-written glob NFA).
- Unclear: `while true { ... return ... }` followed by a trailing expression — I added `Err("unreachable")` after the loop; the doc says a function may end with `while true` but it's unclear if it's allowed when the fn returns a value and the loop only exits by `return`. (Didn't test without it.)
- Unclear: comparing enums with payloads containing Lists via `==` (`elems[j] == Star`) works per §4 but no mention of cost.
- Wished: pattern-matching without binding (`matches Star`), `List.last()` returns Option so `elems[elems.len()-1]` is clumsy.
- `continue` inside `for` inside a function: works.

## 04-csvjoin
- No compile errors. `let (f, next) = if cond { a()? } else { b()? }` (tuple destructuring of an if-expression containing `?`) worked.
- Docs: not stated whether `fs.read` error `Display` looks like `NotFound("path")` (it does; debug-style). OK for stderr.
- Docs: `Set.insert` on a `var` declared `Set[Str] = Set.new()` needs the annotation; fine.
- Wished: `Map.entry(k).or_insert(...)`, or a `m[k].push(x)` that inserts when missing (docs say key must exist; I had to `if not contains { m[k] = [] }`). `Map.update(k, [], fn(l) => ...)` would copy the list.
- Wished: `Str.replace` takes both args as Str — fine. A `List.join` for non-Str would be handy.

## 05-standings
- No compile errors; everything passed first run. `m[k].record(...)` (mutating method on a map entry) worked as §6 says.
- Docs gap: no way to build a "descending" sort key for a Str (name asc vs others desc worked only because name is the only ascending key and others are Int). `sort_by_desc` exists in prelude but isn't in the §11 highlights list in reference.md (it is, actually, in List list). Mixed ordering with a string key descending would need `sort_with`.
- Docs gap: format specifiers — there is no `{x:>3}` padding; I used `"{x}".pad_left(3, " ")`. A `Int.pad_left` shortcut or format spec would be nice.
- Wished: a struct named `Result` can't be defined (clashes with builtin), I used `Result_`; the docs don't say whether user types may shadow builtins.
- Wished: `Str.split_once(sep) -> Option[(Str, Str)]`.

## 06-buildorder
- No compile errors. `Heap[Str]` + `Set[Str]` from the prelude were exactly what was needed.
- Docs: `Heap.pop()` returns the smallest by derived ordering — good. `let Some(x) = h.pop() else { break }` works.
- Docs: `let _ = deps[target].insert(d)` is required since insert returns Bool; `m[k].method()` on a Set inside a Map entry compiled fine.
- Unclear: for `Map[Str, Set[Str]]`, `deps[cur].items()` on a `let` binding — fine.
- Wished: `Set` iteration directly (`for x in set`) — I used `.items()`; unsure whether `for x in set` is legal (docs don't say).

## 07-linebuf
- Compile error that cost a rewrite: `variant 'Delete' is ambiguous (Cmd, Change); qualify it, e.g. Cmd.Delete` — the error was clear, but it only points at one use site; I had to rename variants (Inserted/Deleted/Replaced) since qualifying every use is noisy. The doc (§4) does cover this rule, but I did not expect it in a "natural" two-enum design (command vs. recorded change). It would be nicer if a constructor's expected type (known from the `fn apply(c: Change)` parameter) disambiguated.
- Docs gap: not stated that `Console.println` followed by `flush()` is how to do interactive protocols — found in the prelude comment only. The flush requirement worked.
- Wished: `Str.strip_prefix` is there, I used `starts_with` + `slice(7, len)` magic numbers; a `s.after("APPEND ")` pattern with `let Some(rest) = line.strip_prefix("APPEND ") else {...}` would have been cleaner (I should have used that).
- Wished: user-defined function named `let_prefix` was a silly name; no issue.

## 08-sheet
- No compile errors; examples passed first run. Recursive method with `mut self` (`Sheet.value` <-> `Sheet.eval`, mutual recursion, mutating a cache) worked.
- Docs gap: mutual recursion between methods isn't mentioned but works.
- Docs gap: `const` expression types (`const LIMIT: Int = 1000000000000`) fine; `List.filled(n, Empty)` with a user enum value needs no annotation.
- Docs gap: no statement on whether `match` arms may be `Num(_) => {}` empty blocks for Unit; worked.
- Wished: 2D array/Grid type; I hand-flattened with cell_index. Also an `Int.clamp`.
- Perf note: worst-case alternating SET/GET over a fully populated sheet with big SUMs took ~3.3s for 20000 commands, acceptable.

## 09-todo
- Compile errors hit:
  - `expected an expression, found 'let'` for `if let Some(x) = e { ... }` — there is no `if let`; the docs only show `let ... else`. Docs should say explicitly "there is no `if let` / `while let`; use `match` or `let ... else`".
  - `'text' is already defined in this function (shadowing is not allowed)` — clear, but it fired where a *pattern-bound or earlier-block* name collided across sibling scopes? No: it was `let text` in a for-body while a function parameter `text` existed. Clear message; the rule is documented (§6).
- Docs gap: `Fs.mkdir` "creates missing parents" but the task wanted only the last component; I had to check `is_dir(parent)` myself (needed a hand-written `parent_of` — wished for `Path.parent()` / `Str.rsplit_once`).
- Docs gap: `sys.fs.within(dir)` with a relative dir containing `/` works; `Fs.write` is already atomic so my explicit temp+rename is redundant but spec-required.
- Docs gap: no `Str.rfind`; had to hand-roll a backwards loop. Wished for `rfind`, `split_once`.
- Docs gap: `Map.values()` insertion order after `remove` (stays in insertion order) — relied on it for id order; fine because ids only increase.
- `match` as the value of `return match ... { ... }` worked.

## 10-cachesim
- No compile errors after the first draft (an unnecessary `let_pos` helper was my own detour, since there is no `if let`; `match` with an empty `None => {}` arm is the idiom).
- Docs gap: `Option` in `match` with a `return` inside an arm (`Some(p) => { ...; return "L1" }`, `None => {}`) works but the docs never show an early `return` inside a `match` arm that is a Unit-typed statement.
- Docs gap: no bit operations (`& | << >>`) are mentioned; I checked power-of-two with a loop. Wished for bit ops or `Int.is_power_of_two`; also `Int.pow`.
- Docs gap: `List.remove(i)` returns the element (good) — mutating a struct field's list (`self.sets[s].remove(pos)`) in place works.
- Wished: hex parsing (`Str.to_int_radix(16)`), same as task 02.
- Performance was excellent (200k accesses in 0.3 s).

## Cross-cutting
- Docs gap: no `if let`/`while let`; only `let ... else`. Say so explicitly.
- Docs gap: user enums sharing variant names (Cmd.Delete vs Change.Delete) are an error at each construction site; the message is good but a type-directed resolution would be friendlier.
- Docs gap: no formatting specs (`{x:>3}`), no `Str.rfind`, `split_once`, `Int` radix conversion, bit ops, `Map.entry`.
- Docs gap: exit codes are only settable via `main -> Int`; documented in §9, easy to miss that `eprintln` + `return 2` is the idiom.
- Good: `Heap`, `Set`, `sort_by` with tuple keys, `m[k].method()` in place, `Console.flush`, the `Fs` capability API were easy to use. Error messages from the compiler had precise locations.
- Tests for `main`'s stdin laziness: `read_line` + `flush` worked for interactive protocols.
