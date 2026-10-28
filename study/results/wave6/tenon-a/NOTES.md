# Notes

## 01-wcx
- Went smoothly; compiled first try. Docs did not say what `Fs.read_bytes` does on a directory, so I checked `is_dir` first.
- No byte-to-code-point counting helper for List[Int] (fine: count non-continuation bytes by hand).
- Wished for: a `Str.from_utf8(bytes).char_count()` shortcut was available, but decoding just to count felt heavy.

## 02-b64
- Compiled first try. No bitwise operators (documented) — shifting with `/` and `%` and powers of 64 works but is noisier than `>>`/`&`.
- Wished for: `Str.char_at`/indexing a Str by byte to a one-char Str; I used `ALPHABET.slice(i, i + 1)` repeatedly. `List[Int]` -> Str of ASCII bytes would also help.
- Could not tell from the docs whether a `const` of type `Str` is allowed (it is).

## 03-hsize
- Smooth; compiled first try. `Int.pow`, `is_digits`, `pad_left` and `read_line`'s `\r` handling matched the spec directly.
- `match` on a Str with an `other => return usage(...)` arm worked as I hoped; unclear from the docs whether `return` in an arm whose siblings are assignments type-checks (it does).

## 04-shoplist
- Bug I wrote: used `trim_chars("0")` to drop trailing zeros, forgetting it trims BOTH ends ("025" -> "25"). Wished for `trim_end_chars` / `trim_start_chars` (or `trim_end` taking a set of chars). Had to loop with `ends_with`/`slice`.
- `return` inside a `match` arm that is used as a `let` initializer (`let (small, big) = match kind { Count => return "...", ... }`) works — nice, but not obviously documented.
- Pattern `let (qty, kind) = if ... { (q, Count) } else { match ... }` worked fine.
- `Map[K, V]` with a struct value: `recipes[rname].items.push(...)` in place is great.

## 05-orgchart
- Compiled first try. No shadowing forced `let (org0, ...) = match build(..)` then `var org = org0` to get a mutable copy; a `var (a, b) = ...` destructuring or `let` -> `var` rebind would be nicer. (Not sure if `var (x, y) = ...` is allowed; docs don't say.)
- Wanted a way to destructure into a mix of `var` and `let` names.
- Closure with typed param returning a tuple (`fn(i: Int) -> (Str, Str) { ... }`) as a sort key passed to `sort_by` for many lists worked fine.
- `"{"  ".repeat(depth)}"` — a string literal inside interpolation works as documented.

## 06-climate
- Compiled first try. Tuple keys in a `Map[(Str, Str), V]` and nested tuple patterns in `for ((station, date), temp) in latest` worked well; sorting tuple keys by derived ordering gave exactly the required byte order.
- `?` inside an `Option`-returning helper made the parsing short.
- Minor: `match` arm with an assignment `Some(s) => groups[key] = ...` reads fine but I wasn't sure an assignment is allowed as an arm expression without braces (quickstart shows it, good).

## 07-rooms
- Compiled and passed first try. Match guards on string literal arms (`"ROOM" if t.len() == 3 => ...`) plus `?` inside `Option`-returning `parse` made the command parser compact.
- Format spec `{t / 60:02}` worked as documented.
- I avoided naming a field `where` (unsure if reserved — it is not in the reserved list, but I used `where_` defensively).
- Comparing tuples `(s, cap, name) < b` for tie-breaking is very handy.

## 08-locks
- Compiled and passed the examples first try, but I then caught my own bug: sorting the formatted `"name:mode"` strings is not byte order of names (`a1:S` < `a:S` since '1' < ':'). Sort the tuples by name first. Not a language issue.
- Unit enum variants format as their name (`{mode}` -> `S`), which I guessed; the formatting table in §8 doesn't show a payload-less variant other than `None`.
- `match t[3] { "S" => S, "X" => X, _ => return None }` inside an `Option` function is pleasant.
- Updating a nested place `self.res[r].queue = self.res[r].queue.filter(...)` works; there's no `retain` (in-place filter) on List — wished for one.
- `(["OK"] + grants).join(" ")` — list `+` documented and handy.

## 09-helpdesk
- Compiled and passed first try. Fs.append being durable, Fs.write being atomic (used for truncating a torn tail) and mkdir_one ("only the last component") mapped exactly onto the spec — the §10 text was precise enough.
- There is no `Fs.truncate`; rewriting the whole kept prefix with `write` is fine but O(file).
- `desk.replay(line).map_err(...)?` as a statement: I wasn't sure a `?` expression of type Unit needs `let _ =`; it doesn't (Unit), good.
- Unsure whether `fs.append` itself flushes/fsyncs per call (docs say durable/fsync) — 10000 appends took ~0.5 s, acceptable.
- `if let Err(e) = fs.mkdir_one(dir) { ... }` chained after `else` (`} else if let Err(e) = ...`) worked.

## 10-sand
- Compiled and passed first try. Char literals as Int constants (`const GRAIN: Int = 'o'`), `line.bytes()` for a grid and `Str.from_utf8(row).unwrap()` to print it back worked well.
- `for dx in [0, -1, 1]` with `break` out of the inner loop only — as expected.
- No `for y in (0..h).rev()` / descending range; had to write a `while y >= 0` loop. Wished for a reversed range or step.
- Not obvious whether `0..(h - 1)` needs the parentheses; I added them defensively.

## Overall top points
1. `trim_chars` trims both ends; no `trim_end_chars`/`trim_start_chars` — caused a real bug in 04 (2.025 printed as 2.25).
2. No descending range (`(0..n).rev()` or a step), so bottom-up loops need manual `while`.
3. No `retain`/in-place filter for List; wrote `x = x.filter(...)` on a deep place.
4. No bitwise operators; Base64 shifting with `/`, `%` and powers of 2 is noisy (documented, but missed).
5. No cheap "one byte of a Str as a one-character Str" (Str indexing); used `s.slice(i, i + 1)` repeatedly.
6. No-shadowing plus `let (a, b) = match ...` forced `let x0 = ...; var x = x0` to make one part of a destructured tuple mutable; docs don't say whether `var (a, b) = ...` exists.
7. Formatting of payload-less enum variants (`{mode}` -> `S`) isn't shown in the §8 table; had to guess.
8. `Fs.read_bytes` on a directory: behaviour not documented (I pre-checked with `is_dir`). No `Fs.truncate`.
9. `return` inside a `match` arm used as a value (`let x = match k { A => return ..., ... }`) works but isn't explicitly documented; same for `"lit" if guard =>` arms on strings — both very useful.
10. Positive: tuple ordering/keys, `group_by`/`max_by`, `?` on Option, format specs (`{n:02}`), and the precise Fs semantics (`append` durable, `write` atomic, `mkdir_one`) made every task pass on the first or second compile; error messages were never needed.
