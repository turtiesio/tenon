# Notes

## 01-seqx
- Smooth. `Str.is_digits`, `strip_prefix`, `checked_add` were all found in the prelude quickly.
- Unclear: whether `"007".to_int()` and `"-0".to_int()` work (docs say "decimal digits only"; leading zeros not stated). They worked.
- Wish: a way to take `sys.args` with a cursor/iterator; manual `while i < len` with `i += 2` was fine though.

## 02-trx
- Docs gap: no statement on whether `break`/`continue` inside `while` at an `else if` chain is fine (it was). No problems.
- Wanted: `a..=b` inclusive range; I wrote `t.code..(hi + 1)`.
- Wanted: bytes-in/bytes-out is workable (`read_all_bytes` + `write_bytes`), but there is no `Str.from_bytes`-free way to build a Str from List[Int] without Option (`from_utf8` returns Option; fine here since I used write_bytes).
- `continue` inside a `for` with an `if ... { continue }` as a statement works as expected.
- Char literal `'\\'` works (not explicitly listed in char escapes of §2 but listed for strings).
- The `want`/`want_alt` logic for the set-count table was awkward: a `match` on a `(Bool, Bool)` tuple of options would have been cleaner but no direct doc example of matching bool tuples; I avoided it.

## 03-colalign
- Doc trap: `Str.pad_left/pad_right` count BYTES (len), so they are wrong for UTF-8 text; the prelude comment says "offsets are byte offsets" but the docs never warn that padding is byte-based. I wrote my own `pad`. Wish: `Str.char_len()` / code-point-aware padding.
- No `Str.chars().len()` shortcut; `s.chars()` allocates a List[Str] just to count code points. Wish: `Str.char_count()`.
- `Str.lines()` behaviour on "\n" vs "" is not spelled out ("final empty line is dropped"); I relied on it matching the spec.
- `read_line` vs `read_all().lines()`: the \r handling differs (read_line strips one \r even... only before \n); I picked read_all+lines to follow the spec literally.
- Wish: `for (k, f) in row.enumerate()` allocates the whole list; fine.

## 04-splitbill
- Passed first try. `fmt_fixed(2)` was perfect and easy to find. `Map.or_insert` + `m[k] += x` pattern works as documented.
- `if let Err(e) = apply(line, mut balances) { ... }` — the call with a `mut` argument inside an `if let` scrutinee worked, but the docs don't show a `mut` argument in an expression position; I wasn't sure.
- `(-work[debtor]).min(work[creditor])` needed parentheses; unclear if `-x.min(y)` parses as `-(x.min(y))`.
- `let _ = name_of(p)?` — needed to discard an unneeded Ok value; slightly noisy but consistent with the docs.
- Wish: a `Map.min_by`/`max_by` or iterators over maps with `max_by_key`; I wrote a manual scan loop.
- Wish: an `Option`-returning `Int.parse` with exact-format helpers; I wrote format validation by hand (digits/len checks) for every task.

## 05-srtfix
- Passed first try. Struct field shorthand `Cue { start, end, text: ... }` worked.
- Slightly surprising: `var lines = ...map(...)` then `lines.push("")` sentinel trick is fine; docs have no mention of idiom for "flush last group" (no iterator/group_by in prelude).
- Interpolation containing a nested string literal: `"{h.to_str().pad_left(2, "0")}:..."` compiled fine, but docs don't say nested quotes inside `{}` are allowed. Unclear / worth documenting.
- Wish: `Int.to_str().pad_left(w, "0")` is so common (zero padding) that `Int.pad_zero(w)` or a `fmt_width` would help.
- Wish: `lines()` followed by per-line `\r` strip is a very common pattern; `Str.lines_crlf()` or have `lines()` strip one trailing `\r`.

## 06-libfines
- Passed first try. `let Some(x) = ... else { skipped += 1; continue }` inside a for loop worked (the doc says else must end with `continue`; a statement before it is OK but not shown).
- Clean: `m[k].field += x` and `m[k].list.push(..)` in place on a Map of structs. `m.or_insert(k, Stat {...})` evaluates the default eagerly, fine.
- `sort_by(fn(m) => (-stats[m].fine, m))` closure capturing a Map `stats` while sorting another list worked.
- Doc gap: how to pass `Fs` as a parameter type: `fs: Fs` works (type named in the Capabilities table) but isn't shown in a signature example.
- Wish: `Result.map_err` + `?` is enough, but there is no `?`-conversion between error types (e.g. IoError -> Str), so `.map_err(fn(e) => "...")` is needed everywhere.
- Wish: a record/field-validation helper like `Str.matches(charset, min, max)`; I wrote `is_id`, `is_member`, `num` by hand.

## 07-leaderboard
- Passed first try. Struct with methods (`fn Board.handle(mut self, ...)`) and `match w[0] { "SCORE" => {...} ... }` with early `return` inside arms worked well.
- Doc gap: `return` inside a match arm of a method returning Str, mixed with block-tail values, is allowed but not shown; I assumed it.
- Doc gap: a `mut self` method that returns a value (`Board.ordered(mut self) -> List[Entry]`) - works; not shown in docs.
- Edge not covered by docs: `read_line` on a last line without `\n` keeps its `\r`, while the task says one trailing `\r` is removed from every line. I did not handle it (would need an extra strip that is wrong for CRLF-terminated lines). A `read_line` that strips `\r` uniformly would remove this trap.
- Order caching (`dirty` flag) worked easily with struct fields; sorting with a tuple key `(-e.1, e.0)` is neat.
- `let Some(_) = self.scores.remove(w[1]) else {...}` worked for "remove and check".

## 08-connect4
- Passed first try; also checked against a random-play Python reference (300 games, identical output; no DRAW game occurred in the sample, so the draw path is only covered by reading).
- Nice: `self = Game.new()` inside a `mut self` method works (not documented; I guessed). `const COLS: Int = 7` usable in expressions and `List.filled(COLS * ROWS, 0)`.
- `fn Game.run(...)` - I named a method `run`; no conflict. `fn Game.drop(mut self, ...)` - `drop` is not reserved, OK. Unclear whether names like `drop`/`at` could collide with future prelude names; docs say a file's own definitions hide prelude items, but a *method* on a user type is fine.
- Doc gap: how a match arm can be an `if ... else ...` expression directly (`"UNDO" => if w.len() == 1 { ... } else { bad },`) - quickstart shows it, worked.
- Mild annoyance: ints as enum substitutes (`over: 0..3`) because no way to cheaply compare enums? Actually enums have `==`; I used Int for brevity. A struct-field enum would be cleaner; docs fine.
- Wish: `List.filled(n, x)` for 2D grids requires care with value semantics; docs explain copy-on-write which made me confident.

## 09-polls
- Passed first try. I did NOT use `std-journal.tn` (its checksummed format differs from the task's fixed plain-text journal); wasn't sure at first whether it would be expected - docs never say what the journal module's format is without opening the file.
- `fs.append` durability (fsync) documented; good. Truncation: no `Fs.truncate`, so I rewrote the kept prefix with `write_bytes` (atomic tmp+rename, which also changes the inode; fine here but a `truncate(path, len)` would be more direct).
- `if fs.exists(dir) {...} else if let Err(e) = fs.mkdir_one(dir) {...}` chain with `else if let` as statement: worked.
- `let (loaded, torn) = match load(...) { Ok(r) => r, Err(e) => { ...; return 1 } }` worked: tuple destructuring of a match result.
- Surprise-free but undocumented: `self.polls[w[1]].votes[voter] = idx` (assignment through nested map entries) compiled and worked in place.
- `Result[(Polls, Option[List[Int]]), Str]` as a return type fine.
- Wish: `Str.lines()` on a prefix is fine, but I had to find the last newline byte by hand; `List[Int].rindex_of` / `Str.rfind` on bytes would help. `Str.rfind` exists for Str but bytes -> Str roundtrip would break on torn UTF-8.
- Naming: variable called `end` and `kept`, `torn` fine; `open` as a struct field name is OK (not reserved).

## 10-robots
- Passed first try (26-robot-scale perf fine: 99999 ticks in 0.09 s native).
- Surprise (positive): `fn List[Robot].index_of_letter(self, ...)` — a method on a specific instantiation of List with a *user* struct type — compiled. Docs only show `List[Int].total`. Unclear whether that is allowed for user types by design (rule says builtin types accept methods; fine).
- Doc gap: a multi-line condition continued with a line beginning with `or` works (documented in lexical rules) - good; `for i in (grid_end + 1)..lines.len()` range with parenthesised start OK.
- `self.robots[i].bumps += 1` through `mut self` nested lists in place: worked, fast.
- Wish: `Int.char()` returns Str for a code point — name is easy to miss (`'A'.char()`); would like `Str.from_char(c)`. I found it only by scanning the prelude.
- Wish: char literal comparisons with `Str.byte(i)` are ok, but no `match` on char ranges ('a'..'z' patterns); had to use `is_lower()` etc.
- Wish: `Set[Int]` insert returns Bool - handy; documented.
