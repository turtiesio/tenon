# Notes (author tenon-a, study 7)

All 10 tasks done; one compile error over the whole set (task 08).

## 01-numlines
- Docs were enough. I read the input with `read_bytes`/`read_all_bytes` and wrote
  `con.write_bytes` to copy lines byte for byte. Building a `List[Int]` of output
  bytes works, but in a C build it costs 8 bytes per byte (library.md says so).
  I wished for a byte-exact `Str` path, or a note saying whether `Fs.read` +
  `print` is byte-exact for valid UTF-8 (it should be, but the docs never say it).
- `Str.is_digits` exists, but library.md's Str list is the only place it is
  mentioned and nothing describes it (is `""` digits? The prelude shows it is
  false). A one-line description would help.
- Wished for: a small `regex`-free way to check "matches `[1-9][0-9]{0,5}`".
  Every task needed this (numbers without leading zeros, bounded length), and I
  wrote the same 3-line helper in 8 of the 10 tasks. `import regex` is
  possible, but it seemed heavy for that.

## 02-checkdigit
- No problems. `rev_range(0, n).enumerate()` worked for "positions from the right".
- `ds + [c]` (list concatenation) is documented only as "`+` concatenates" in a
  long list of names; easy to miss.

## 03-detab
- Counting code points by byte: I used `b < 128 or b >= 192` (no bitwise ops).
  The docs say there are no bitwise operators and suggest `/` and `%`, which is
  fine. A `Str.char_offsets()` or a way to iterate code points with byte
  offsets would have been nicer than `chars()` (which allocates a string per
  character).
- `Str.repeat` exists, but it is listed with no description.

## 04-cidrmerge
- Fine. `2.pow(32 - p)` and 64-bit ints made it simple. Tuple ordering for
  `sort()` worked as documented.
- `merged[merged.len() - 1] = ...`: I wished for `xs.last_mut()` or negative
  indexing, but this works.

## 05-reconcile
- `Int.fmt_fixed(2)` was exactly right for money (`-50` -> `-0.50`, `0` -> `0.00`).
- `args.get(i + 1).unwrap_or("")` reads well. Fine overall.
- `Result.map_err(fn(e) => "...{e}")?` to change the error type worked; the
  reference says `?` does not convert error types, which is clear.

## 06-costbasis
- A guard on an alternative pattern (`"BUY" | "SELL" if t.len() == 4 =>`)
  worked. The reference documents guards and `|` separately; one example with
  both together would make it clear that the guard covers both alternatives.
- `book.remove(sym)` returns an Option, so it needs `let _ =`. The compiler
  required that (documented as "values are not silently dropped").

## 07-vending
- A `const DENOMS: List[Int] = [...]` worked. The reference says constants are
  "any expression" and evaluated again at each use; it is not clear whether a
  list constant is rebuilt at every use (a performance question).
- A closure inside a `mut self` method used `self.tubes` (captures a copy). This
  is documented and worked.

## 08-vfs
- **Confusing / undocumented:** `struct Fs { ... }` in my file gave
  `error: type 'Fs' is already defined`. Reference §6 and §13 say *"A
  top-level item (function, constant, struct, enum) defined in a file hides
  the prelude item of the same name in that file, so a new prelude name never
  breaks a program"*, and even show `struct Result { code: Int }`. Apparently
  this does not apply to builtin capability types (`Fs`, probably also
  `Console`, `Str`, ...). The docs should say which names cannot be hidden, and
  the error should say why ("'Fs' is a builtin type and cannot be redefined").
  I renamed it to `Tree`.
- My own enum variant `Failed(Str)` hid `IoError.Failed` without problems, as
  documented.
- An arena (`List[Node]` plus indices) is the natural tree design under value
  semantics. A sentence in the docs recommending it for trees with parent links
  would help newcomers.

## 09-bookmarks
- `Fs.write` writes `path + ".tmp"` and renames it. The task's protocol says
  "write `snapshot.tmp`, then rename it to `snapshot`". So `fs.write("snapshot.tmp")`
  internally uses `snapshot.tmp.tmp`. That is fine, but it doubles the
  rename. A non-atomic `Fs.write_plain` or `Fs.create` would map more directly
  onto such specs. I could also have just done `fs.write("snapshot", ...)`,
  which is already atomic; the docs make that clear.
- `Fs.append` is durable (fsync), as documented, which is what "write before
  answering" needs.
- `Fs.truncate` existed for the torn tail, and the reference even shows the
  idiom. Very helpful.
- `cmd == Compact` (comparing an enum value with `==`) worked via derived Eq.
- `if let Err(e) = fs.mkdir_one(dir) { ... }` after `else` (`} else if let`)
  worked.
- Not clear: whether `fs.exists`/`is_dir` follow symlinks (they did not matter here).

## 10-war
- Fine. `deck.remove(0)` for a queue; a `Deque` type would be nice, but 52
  cards do not need one.
- `up_a.map(card).join("/")` (a named function as a value) worked as documented.
- An `else if` starting a new line after `}` worked, as documented ("a line that
  begins with `else` continues the previous line").

## General
- The quickstart translation table is excellent; most tasks needed nothing else.
- library.md lists many method names without signatures or descriptions
  (`repeat`, `is_digits`, `find_from`, `extend`, `index_of`). I had to grep
  `prelude.tn` for signatures. A signature table in library.md would help.
- No `Str.is_digits`-like helper for "a decimal without leading zeros, at most N
  digits", which every CLI spec here needed.
- No bitwise operators (documented). They were not needed in these tasks.
