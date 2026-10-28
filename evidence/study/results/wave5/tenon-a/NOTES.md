# Notes (author A)

## 01-seqx (done)
- No problems. `strip_prefix("-").unwrap_or(s)` + `is_digits()` + length check was a
  clean way to express `-?[0-9]{1,18}`. I wished for a tiny "matches regex"
  helper without importing `regex`, but the string API was enough.

## 02-trx (done)
- `con.read_all_bytes()` / `con.write_bytes()` were exactly right for a byte filter.
- `match e { 'n' => '\n', ..., _ => return Err(...) }` as an expression worked
  (a `return` inside a match arm that produces a value).
- My test harness hung (not the language): no compile/runtime issue.
- Wished for: `List.filled` with an index function (`List.tabulate(256, fn(i) => i)`)
  to build an identity map; I wrote a loop.

## 03-colalign (done)
- `s.chars().len()` for the code point count: the prelude says `chars` returns
  `List[Str]` but does not say whether these are code points or bytes. I assumed
  code points (it worked with "Zürich"). Docs should state it, and a
  `Str.char_count()` would avoid building a list just to count.
- No "split on spaces and tabs" helper: `words()` also splits on `\r`/`\n`; I used
  `replace("\t", " ").split(" ").filter(non-empty)`. A `split_any(" \t")` or
  `words_by(chars)` would be nice.
- Unsure whether `"".lines()` is `[]`; it is (empty input printed nothing). Docs
  should say so explicitly (only `"".split(",") == [""]` is documented).

## 04-splitbill (done)
- `fmt_fixed(2)` for cents was great.
- `fn add(balances: mut Map[Str, Int], ...)` called with `add(mut balances, ...)`
  worked as documented; a bit noisy but clear.
- `Set.insert` returning Bool made "listed twice" detection one line.

## 05-srtfix (done)
- Compiler error, clear but surprising for me at first:
  `error: methods of 'Option' can only be defined in the module that defines it`
  (I tried `fn Option[Str].or_else_strip`). The reference does say so (§13);
  my fault. But builtin types (Str, List) can get methods, prelude enums cannot — the
  asymmetry is a speed bump.
- Missing on `Option`: `or_else` / `or` (`a.or(b)`), and `Str.strip_any_prefix`.
- Local closure with full types `let pad = fn(n: Int, w: Int) -> Str { ... }`
  inside `"{...}"` interpolation worked nicely.

## 06-libfines (done)
- `let returned = if f[4] == "-" { None } else { let Some(r) = ... else { return Err(bad) }; ...; Some(r) }`
  worked: `let ... else` inside an expression block. Good.
- `fs.read(...).map_err(fn(e) => "...{e}")?` then `"{e}"` prints `NotFound("missing.txt")`:
  fine for stderr.
- `members[k].late.push(x)` / `members[k].fine += x` in place: very convenient.
- Wished for: `List.sort_by` with a descending component other than negation
  (negation works for ints only; for strings descending you'd need `sort_with`).

## 07-leaderboard (done)
- Match guards on string literals (`"SCORE" if n == 3 => ...`) and `?` on Option
  inside a function returning `Option[Str]` made the command parser compact.
- Tuple ordering `(-total, name)` plus a hand-written binary search. Wished for
  `List.binary_search` / `lower_bound` in the prelude.
- `read_line` strips one `\r` only when followed by `\n`; a last line without
  `\n` keeps its `\r` (documented). Every spec says "one trailing `\r` is removed",
  so I always add `strip_suffix("\r")`, which double-strips `"X\r\r\n"`.
  A `read_line` variant that always strips one trailing `\r` would match the
  usual spec wording exactly.

## 08-connect4 (done)
- `const COLS: Int = 7`, enums with payload (`Won(Str)`), `self.outcome != Running`
  comparison on an enum: all worked first time.
- Assigning a whole new value to a `mut` parameter (`game = Game.new()`) works.

## 09-polls (done)
- Used `fs.read_bytes` to find the last `\n` (so a torn record with partial UTF-8
  can't make `fs.read` fail), `Str.from_utf8` on the prefix, `fs.write_bytes` to
  truncate (atomic replace), `fs.append` for records (durable, documented: fsync).
  The reference's §10 description of write/append durability answered exactly the
  questions I had. 
- No truncate API; rewriting the prefix with `write_bytes` is fine for this size.
- `mkdir_one` "creates exactly one directory" matched "only the last path component
  is created" perfectly.
- `Result.and_then(fn(_) => load(...))` to chain two startup steps worked.

## 10-robots (done)
- Confusing compiler error: in a Unit function, a match arm `_ => return,` gives
  `error: expected an expression, found ','` (main.tn:78:20). `return` with no value
  directly before `,` is not accepted; `_ => { return },` works. The reference shows
  bare `return` only as a statement. Either accept it or give a hint like
  "write `return ()` or `{ return }` in a match arm". (The many compile-error
  entries in attempts.jsonl for 10-robots are this one error, repeated by my
  batch test loop.)
- `c.char()` for printing a code point, `"NESW.".contains(...)`, `List.filled`
  for the occupancy grid: all straightforward. 26 x 99999 actions ran in < 0.1 s.

## General
- The quickstart + reference + prelude source were sufficient for all 10 tasks; the
  prelude as readable source is very useful (I checked semantics like `pad_left`,
  `get_or`, `sort_with` directly).
- Missing helpers I reached for repeatedly: a char-set predicate for whole strings
  (`s.all_bytes(fn(c) => ...)`, I wrote it twice), `Option.or`, `List.binary_search`,
  `Str.char_count`, splitting on a set of separator characters.
