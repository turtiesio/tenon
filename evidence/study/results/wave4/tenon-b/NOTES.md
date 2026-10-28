# NOTES

## 01-hexdump
- MAJOR: no way to read binary data. `Fs.read` returns `Err(Failed("path: invalid UTF-8"))` for non-UTF-8 files
  (undocumented in reference; only discovered by running), and `Console.read_all` silently turns invalid bytes into U+FFFD
  (documented only for read_line), losing the original byte. I guessed 0xFF for each U+FFFD in stdin; binary FILEs with
  invalid UTF-8 cannot be dumped at all. Wished: `Fs.read_bytes -> Result[List[Int], IoError]`, `Console.read_bytes`.
- Docs don't say that `Int.char()` on values >= 0x80 yields a multi-byte string (not relevant here, avoided).
- Good: `is_digits`, `to_str_radix`, `pad_left` were exactly what I needed.

## 02-uniqx
- No problems. `Str.lines()` doc ("drops a final empty line") was enough. Slight surprise: no way to `continue` with a
  value-producing loop is irrelevant; fine. Would have liked a `Str.trim_end_chars`/`strip_suffix("\r")` idiom note — the
  Option-returning strip_suffix + unwrap_or works but is wordy.
- `Option[Str]` var holding group representative + `if let Some(rep) = cur` worked fine (no shadowing rule bit me because I named distinctly).

## 03-icalc
- Compiled and passed first try. Recursive enum `Expr` + `Parser` struct with `mut self` methods returning `Result` and using `?` worked well.
- Docs gap: comparing `Option[Int]` with `==` (`self.peek_op() == Some('-')`) works (all types support ==) but I only inferred it from §4.
- Docs gap: precedence of `and`/`or`/`not` vs comparison not stated (I used parens-free `c != '*' and c != '/'` and it worked).
- Wished: `Str.contains` taking a char code; I used `"+-*/%()".contains(b.char())`.
- Note: when a multi-line `if ... { } \n else if` chain is used as an expression, `else` at line start is OK per §2.

## 04-timesheet
- Passed first try. `const DAYS: List[Str] = [...]` works; user-defined extension method `fn Str.index_of_day` in the main file works
  (reference §13 says methods may only be defined in the type's module, but the prelude's Str is apparently allowed — confusing statement: "Methods of a type can only be defined in the module that defines the type" vs. my success).
- `sort_by(fn(p) => (p.day, p.time))` with tuple key is stable and handy; documented in §4.
- A `let x = if c { true } else if d { false } else { return None }` (return in an expression branch) type-checked: nice but undocumented.
- `Map.or_insert` + `m[k].push` pattern is documented and works.

## 05-runoff
- Passed first try. `for ... { ... break }` inside nested for/while works; `while true { ... break }` followed by code works.
- Unclear in docs: whether `1..n` with n < 1 (empty range like `1..1` or `1..0`) is safe — I relied on it being empty (worked for `1..lines.len()` with len 1).
- `List.filled(n, x)` called as `List.filled(...)` with inferred type: works.
- `let Some(names) = header else {...}` where `header` is a var: fine.

## 06-mdtoc
- Passed first try. Nested string literals inside `"{...}"` interpolation (`"{" ".repeat(n)}- ..."`) work, but the reference
  never says so explicitly — I had to guess. `\{` for literal brace; `{` in `(#{h.slug})` — "#{" didn't need escaping since `#` isn't special. Good.
- `mut Set[Str]` parameter + `used.insert(...)` returning Bool requiring `let _ =` — correct per docs but easy to forget.
- A bare `#` followed by `{` in a string is fine.

## 07-parking
- Passed first try. `Heap[Int]` as a free-slot pool and `Int.fmt_fixed(2)` for cents were exactly right (well documented).
- `return match ... {}` / `return if ... {}` as expression statements work.
- Doc gap: reference §7 says `while let` + `con.read_line()` fine; no mention of interactive flush semantic beyond `flush()`. OK.
- Methods with `mut self` that return a value and call each other (`self.enter(..)` inside a `mut self` method) worked without a `mut` marker at the call site — the docs only show `mut` markers for function arguments; unclear whether method calls on a mut self need anything (they didn't).

## 08-pubsub
- Passed first try. Deep in-place update through map entries (`self.clients[name].mailbox.push(msg)`, `.dropped += 1`) worked in a `mut self` method as §3/§6 promise.
- `let _ = self.clients[..].mailbox.remove(0)` — discarding a returned value is verbose but consistent with docs.
- Wished: `List.remove_value`, `Map.entries_mut`; also a way to iterate map values mutably without re-lookup by key.
- Closure captured `t` (a List) inside a closure inside a `mut self` method: fine ("captures by value").

## 09-shorten
- Passed first try. `Fs.append` durable, `Fs.write` atomic rewrite (the `.tmp` warning in §10 noted), `mkdir_one` for "only the last component", `is_dir` / `exists` all there.
- A struct holding an `Fs` capability (`State { fs: Fs, ... }`) works although §10 only discusses passing capabilities as parameters; worth one sentence.
- Doc gap: no mention of what `Fs.read` does on invalid UTF-8 (returns Err(Failed("path: invalid UTF-8"))), which matters for torn journals (a torn record may cut a multi-byte char / contain garbage). I exit 1 in that case.
- Doc gap: `Fs.exists` on a path whose parent is a regular file; not tested.
- Kill-at-any-time test: stdout `flush()` + `append` before response gave the required order.
- Unused local variable (`kept`) produced no warning — fine, but there is no lint either.

## 10-elevator
- Passed first try; 10000 requests over ~300k ticks run in 0.3 s (compiled).
- `List.filled(n, [])` for a list of lists works with the element type inferred from the later `.push(...)`/annotation `List[List[Int]]`.
- `for f in floor + 1..floors` — range precedence (`+` binds tighter than `..`) works but is not stated in the reference.
- Shadowing rule: I had to avoid reusing `f` (used `for f in ...` then `var f = ...` would clash? I used `for f` inside an `else` and `var f` after the loop in the same block: compiled, so loop variables apparently don't count as declared after the loop. Docs don't say.)
- `dir = match dir { Up => ..., }` assigning a match on the variable being assigned: fine.

## Summary wishes (cross-task)
1. Byte-level I/O (Fs.read_bytes / Console.read_bytes) — hexdump cannot work for binary files at all.
2. A line-oriented splitter that strips "\r" (`lines()` leaves it; I wrote `strip_suffix("\r").unwrap_or(x)` in 8 tasks).
3. `Option.unwrap_or` after `strip_*` idiom — maybe `Str.trim_end_matches`.
4. Statement-level discard `let _ =` for `Set.insert`/`List.remove` is noisy.
5. No `loop`; `while true` with break is ok.
