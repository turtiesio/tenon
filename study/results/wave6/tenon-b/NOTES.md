# Notes

## 01-wcx
- No problems. Docs were enough. `read_all_bytes` / `read_bytes` made byte counting easy.
- Mild surprise: no bitwise ops, so counting UTF-8 code points had to use `b < 128 or b >= 192`.
- Wish: a `Str.char_count`-like helper on byte lists; `Int.is_space` excludes \v and \f (ASCII ws 11,12), so I wrote my own `is_ws`.
- `"{e}"` on IoError prints `NotFound("nope.txt")`, fine but noisy for user-facing messages.

## 02-b64
- No compile problems. Without bitwise ops I used `/ 4096 % 64` etc.; works but it is noisy. A bit-shift/`&` or at least a documented idiom for 6-bit extraction would help (docs only mention `x / 2.pow(k)`).
- `const ALPHABET: Str` plus `ALPHABET.slice(n, n+1)` is the natural lookup; no `Str.at(i)`/char-indexing returning a Str, only `byte(i)` (Int).
- `con.print(s)` with no trailing newline and `con.write_bytes(list)` were easy to find in the prelude. Reference says nothing about whether `write_bytes` output order relative to `print` is consistent (assumed yes).
- Wish: `List.filter`-style ops on bytes work fine; but a `for b in data` + `if cond { text.push(b) }` was needed as I wanted no closure capture; OK.

## 03-hsize
- No problems; passed first try. Matching on `Str` literals in `match args[i] { "0" => ..., other => ... }` worked well. Assigning in a match arm (`"0" => places = 0,`) compiled without complaint.
- `10.pow(places)` — a literal followed by `.pow` worked.
- Array literal of strings in an `if` expression (`if decimal { [..] } else { [..] }`) inferred fine.

## 04-shoplist
- Compiled and passed first try. Things I had to look up/guess: `strip_suffix("\r").unwrap_or(raw)` for the CR removal (fine); `trim_chars(" ")` for blank-line check; `continue` inside `for` OK.
- `Result` + `?` with `map_err(fn(e) => "...{e}")?` is pleasant. Needed the error type to be `Str` everywhere, which was OK.
- Struct field shorthand `Recipe { serves, items: [] }` worked; `[]` literal typed from the field.
- Slight oddity: I had to introduce `name2` since no shadowing (`let Some(name) = ...; let Some(name2) = ...`). No-shadowing is documented but is annoying in chains of `let ... else`.
- Closure that captures `t` (a List) inside `any(fn(it) => it.name == t[0])` worked.
- Missing: a `Str.strip_prefix`+`strip_suffix` combo e.g. `s.strip_surround("[", "]")`; no regex-lite is needed since the regex module exists but I did not use it (compile returns Result, import adds ceremony).
- `match` on Str with arms that assign (`"g" => kind = 1,`) mixed with block arms is OK.

## 05-orgchart
- Passed first compile. Used a struct with a method taking `out: mut Str` (`fn Org.emit(self, out: mut Str, ...)`), called as `self.emit(mut out, k, depth+1)`: worked, and docs described it well.
- Unclear at first: whether a closure bound to a `let` (`let order = fn(i: Int) => (...)`) can be passed to `sort_by` twice. It can.
- `sys.args.first()` giving `Option[Str]` is neat.
- Gotcha avoided: `"\r"` handling – `lines()` keeps `\r`, so I used `strip_suffix("\r").unwrap_or(raw)`; a `Str.lines_trimmed()`-like helper would be handy since every task repeats this.
- Wish: a `join`-less way to get comma-grouped numbers; format specs have no thousands separator (wrote with_commas by hand).

## 06-climate
- Compiled and passed first try. Tuple map keys `Map[(Str, Str), Int]` and tuple destructuring in `for ((station, date), temp) in used.entries()` worked (nested pattern in `for` is not explicitly documented; reference says only "patterns that always match").
- `groups[key].days += 1` in-place update works as documented; but I repeated `groups[key]` 4 times. A `Map.update` exists but takes a whole-value closure: fine, but struct-with-4-fields updates via closure are awkward. Wish: `get_mut`/`entry` API.
- The `-0.0` rule falls out naturally with ints. Format `"{a / 10}.{a % 10}"` fine.
- Doc gap: `Str.char_count()` for the station limit is documented well; no doc for whether `s.starts_with(" ")` etc. are byte-based (obviously fine).
- `.sort()` on a `List[(Str, Str)]` works (derived ordering) — documented in §4 only implicitly for tuples.

## 07-rooms
- Compiled first try; all examples pass. Notable positives: `"{h:02}"` format spec worked as documented; `fn List[Booking].index_of_id` (method on a specific instantiation of a builtin type) worked and could be used before its definition.
- Doc gap: whether a `match` arm can be `Some(b) => if cand < b { best = Some(cand) },` (an `if` without else as an arm value, Unit) — it compiled, but the reference never states arms may be unit-typed statements.
- Doc gap: `let _ = self.rooms[name].bookings.remove(i)` – needed because `remove` returns the element; the "values are not silently dropped" rule is in quickstart, so I expected it. It would be nicer to have a `remove` variant without return (or allow dropping).
- Wish: `Map.values()` iteration while the map is behind `self`; fine. A `min_by`-with-tuple-key on the rooms list would have been an alternative to my manual loop.
- `for p in t { if p.is_empty() { return ... } }` is a bit verbose for "any token empty"; `t.any(fn(p) => p.is_empty())` would do (and I used it elsewhere).

## 08-locks
- Compiled and passed on the first try. 
- Pleasant: deep in-place updates such as `self.resources[name].queue.remove(0)` / `.holders.push(front)` inside a `mut self` method (documented in the performance section, which is where I found out it is safe and cheap).
- `while true { let Some(i) = ... else { break } ... }` — `let ... else { break }` worked inside a loop as documented.
- Annoying: `let _ = x.remove(i)` again for List.remove; I'd like `List.remove_at(i)` returning Unit or permission to drop a result with a name like `_ = ...`.
- Doc gap: not stated whether `Map.or_insert(k, v)` evaluates `v` eagerly (it does, as args are); fine.
- Mild: methods defined on a user struct can't be named `drop`/`lock`? They could (no reserved word problem). Good.

## 09-helpdesk
- Compiled and passed on the first try (examples 1-4 reproduced, including torn journal truncation).
- Doc gap / trap: `docs/std-journal.tn` (checksummed lines `BODY #CHECKSUM`) does NOT fit tasks that fix the journal format; I read it and wrote against `fs.append` / `fs.write` directly. Maybe the reference should say the std journal imposes its own on-disk format.
- Doc: `Fs.append` is documented as durable (fsync) – good, that answered "is it flushed before I ack?" directly. The reference describes `Fs.write` (atomic via `path.tmp`) so I used it for truncating the torn tail; it would be nice to have an explicit `Fs.truncate`.
- Needed `if let Some(i) = ... { } else { }` as an *expression* (`complete = if let Some(i) = text.rfind("\n") { ... } else { "" }`) and it worked.
- `else if let Err(e) = sys.fs.mkdir_one(dir) { ... }` chain with an `if` that has no final else (Unit) also worked.
- Pattern alternatives with payload wildcards: `Assign(_, _) | Close(_) | Reopen(_) => ...` worked.
- Annoying: no shadowing meant parameter `desk` vs `d`, and `Open(customer, title)` binding names had to differ from struct field names in the same function. Also `exec(cmd)` after `match cmd {Assign(..) | ..}` – cmd could still be used (not linear), fine.
- `let _ = self.exec(Open(customer, title))` needed because the reply is a value.
- Wish: `Fs.truncate`, and `Fs.append` returning without needing a handle for many appends (it reopens each time – fine for ≤10000 commands).

## 10-sand
- Compiled and passed on the first try after I removed a draft mistake of my own (logic, not language).
- `const EMPTY: Int = '.'` char literal as const worked; `Str.from_utf8(row).unwrap()` is the way to turn a byte list back into a line — natural but I had to find it in the prelude (quickstart mentions it only for read_bytes).
- Nested in-place updates `self.cells[y + 1][tx] = GRAIN` work, as the performance section promises.
- `else if let Some(tx) = self.target(x, y) { ... }` after `if cond { }` chain worked inside a `for` that also uses `continue`.
- `while y >= 0` with `var y = h - 1` for a downward loop: there is no reverse range (`(0..n).rev()`); I used while. A `for y in (0..h).reversed()` would be nicer.
- `0..(h - 1)` when h == 1 gives an empty range (fine, not a trap) — the docs say "half-open range" but don't say what `a..b` with b < a does; I relied on empty.
