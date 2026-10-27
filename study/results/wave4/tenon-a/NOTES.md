# NOTES (Tenon usability study, author A)

## 01-hexdump
- **No binary I/O at all.** `Console.read_all` replaces invalid UTF-8 with U+FFFD
  (documented for read_line only, in §11 Console), and `Fs.read` on a file with
  invalid UTF-8 returns `Err(Failed("scratch/b.bin: invalid UTF-8"))` — this is
  not documented anywhere (reference §10/§11 and prelude say nothing about
  Fs.read requiring UTF-8). There is no `read_bytes` / `List[Int]` byte API
  (`error: type Fs has no method 'read_bytes'`). So a hexdump of arbitrary bytes
  (spec example 2 has 0xff on stdin) is impossible; 0xff shows as `ef bf bd`.
  Gave up on that example only; everything else passes.
- Wished: `Fs.read_bytes(path) -> Result[List[Int], IoError]` and
  `Console.read_all_bytes()`, or a Bytes type.
- Minor: `Int.to_str_radix(16).pad_left(2, "0")` works fine, but a hex-format
  helper with width would be nice.

## 02-uniqx
- Smooth. `match` on string literals with `"-f" | "-s"` alternatives worked as hoped.
- Minor doc gap: `Str.lines()` "drops a final empty line" — had to reason that
  "\n\nx\n\n" gives ["", "", "x", ""] (one dropped); it does, but an example in
  the docs would help.
- No `Str.pad_left` on Int directly: wrote `"{size}".pad_left(7, " ")`. Fine.

## 03-icalc
- Compiled and passed on the first try. Recursive enum AST, `mut self` parser
  methods, `?` on Option inside methods, `checked_*` all worked as documented.
- `Some(x) if guard` in match and comparing `self.peek_op() == Some('-')`
  (Option equality) worked — nice; docs only imply it via "every type supports ==".

## 04-timesheet
- Passed first try. `const DAYS: List[Str] = [...]` worked (reference says
  "any expression", good). `week[p.name][p.day].push(...)` nested in-place
  mutation works as §6 promises.
- `match parts[3] { "IN" => true, "OUT" => false, _ => return None }` —
  `return` as a match-arm expression worked; not explicitly documented.

## 05-runoff
- Passed first try. `while true { ... return 0 ... }` as the last statement of
  an Int-returning main works as §7 describes.
- `if not (c.is_alnum() or c == '_')` fine. `Set.insert` returning Bool is handy.

## 06-mdtoc
- Passed first try. Interpolating an expression containing a string literal
  `"{" ".repeat(n)}- ..."` worked (quotes nested inside `{}`), which I was
  unsure about; the docs don't say whether string literals may appear inside
  an interpolation.
- No `Str.lower` per byte / `Int.to_lower`: wrote `(c - 'A' + 'a').char()`.

## 07-parking
- Passed first try. Tuple patterns in `let Some((spot, entry)) = m.remove(k) else {...}`
  and match arms `Some((spot, _))` work. Calling a `mut self` method on a
  struct field (`g.free.push`) works.
- Unsure whether variant names `In`/`Out` might clash with anything; they didn't.

## 08-pubsub
- Wrote `!s.is_empty()` by habit: `error: unexpected character '!'`. Clear
  enough, but a hint "use `not`" would be friendlier (the reserved-words list
  has `not`, but quickstart's translation table doesn't mention `!` -> `not`
  or `&&`/`||` -> `and`/`or`).
- Passing a named function as a predicate (`segs.all(is_segment)`,
  `chars_ok(s, 1, 16, is_seg_char)`) worked nicely.
- `self.clients[name].subs.push(p)` inside a `mut self` method works in place.

## 09-shorten
- Passed first try. `Fs.append` is documented as durable; `Fs.mkdir_one`
  semantics were exactly what the spec needed; `Fs.write` used to truncate to
  the valid prefix (atomic via journal.tmp, documented).
- Gap: a test-written journal containing invalid UTF-8 garbage would make
  `Fs.read` fail outright (see 01-hexdump), so the "longest valid prefix"
  cannot be recovered; I exit 1 there. A byte-level read (or a lossy read)
  is needed for crash recovery of arbitrary files.
- No way to truncate a file in place (only rewrite with `write`); fine here.
- `Err(NotFound(_)) => return Ok(st)` nested patterns on IoError worked.

## 10-elevator
- Passed (examples passed first try; I then fixed my own bug in an idle-tick
  shortcut). `dir == Up` on a user enum (derived ==) and `match dir { Up => if .. {Up} else {Down}, ... }`
  read well. `List.filled(floors, [])` for a list of lists worked with inferred
  element type from the annotation.
- 10000 requests / 100 floors ran in 0.3 s via the C backend.

## General
- try.sh builds with `tenon build`; compile errors are precise (file:line:col
  with a caret).
- Not documented: whether `"{...}"` interpolation may contain string literals
  (it may), and whether `return` can be used as a match-arm/if-branch value
  (it can).
- Quickstart table lacks `!`/`&&`/`||` -> `not`/`and`/`or`.

## Top 10 points
1. No binary I/O: `Fs.read` fails on non-UTF-8 files (`Failed("...: invalid UTF-8")`,
   undocumented) and `Console.read_all` silently replaces bytes with U+FFFD;
   there is no `read_bytes`. Made 01-hexdump impossible to pass.
2. The UTF-8 requirement of `Fs.read` is not stated anywhere in reference §10/§11
   or the prelude comments; it's a surprise at run time.
3. Crash recovery of an arbitrary/corrupt file (09-shorten) has the same hole:
   garbage bytes make the whole journal unreadable instead of yielding a prefix.
4. Quickstart translation table should list `!` -> `not`, `&&` -> `and`,
   `||` -> `or`; the error `unexpected character '!'` could suggest `not`.
5. Docs don't say string literals are allowed inside `{}` interpolation
   (`"{" ".repeat(n)}"` works) — worth one line in §8.
6. `return`/`continue` as expression values in match arms works but is only
   implied (`let ... else` section); an explicit sentence would help.
7. `Str.lines()` behaviour with multiple trailing empty lines deserves an
   example ("\n\nx\n\n" -> ["", "", "x", ""]).
8. Wished: a fixed-width zero-padded number formatter (e.g. `n.pad(8, 16)`)
   — `to_str_radix(16).pad_left(8, "0")` and `"{x}".pad_left(2, "0")` were
   written in every task.
9. Wished: ASCII per-code-point helpers like `Int.to_lower()` and a
   `Str.all_bytes(pred)` / regex-free char-class check; I hand-wrote byte
   loops for `[a-z0-9]{1,16}` style validation in 8 of 10 tasks (std regex
   exists, but compiling patterns for simple token checks felt heavy).
10. Overall the language was pleasant: 8 of 9 completed tasks passed on the
    first or second compile; value semantics with in-place nested mutation
    (`m[k].list.push(x)`), `let ... else`, and `?` on Option made parsers short.
