# Notes

## 01-numlines (done)
- Docs: `s.is_digits()` is only named in the Str method list, no semantics (is "" digits? negative?). I guarded with len checks.
- Docs: no statement of whether `con.print` of one large string is fine/efficient; I assumed yes.
- No way to read a file as "bytes copied verbatim" into a Str except read_bytes + from_utf8_lossy (fine, but two steps); `fs.read` fails on invalid UTF-8 which for a "copy file" tool is a surprising Err.
- `List.pop()` returns Option, so dropping the last element needed `let _ = lines.pop()` (ok, documented rule, but a bit noisy).
- Wished: a getopt-like helper; `s.chars()` etc. not needed here.

## 02-checkdigit (done, first try)
- Docs: `args.slice(2, args.len())` on List: slice semantics (half-open, end exclusive, trap if out of range?) are not spelled out for List in library.md; I guessed same as Str.slice. Worked.
- Docs: `else if` chain inside a `for` where branches are `()`-typed worked as expected; `(if c { a } else { b }) * d` parenthesised `if` expression as operand worked (not documented explicitly).
- `b - '0'` where b is a byte (Int) and '0' Int literal: nice, documented.
- No issues with compiler errors.

## 03-detab (done, first try)
- Docs: no function to iterate characters with byte offsets; I walked `s.byte(i)` and counted non-continuation bytes (`b < 128 or b >= 192`). Worked, but a documented `char_indices`/`chars` with offsets would be nicer. `s.chars()` builds a List[Str] (allocation per char).
- Docs: `for ... in` over a `List` with an early `return` inside a function returning Int worked.
- `Str.from_utf8_lossy` was my only route to "copy file bytes"; fine.

## 04-cidrmerge (done, first try)
- Docs: `entries.sort()` on a `List[(Int, Int)]` (tuples) is not in the List method list as "sort() with no args" but sort/sorted are listed; derived ordering for tuples documented in §4, so I guessed right.
- Docs: assigning a tuple field of a list element in place (`merged[i].1 = last`) is allowed by §6 ("field/element of one") but tuple-field assignment is not explicitly shown; worked.
- `for (first, last) in entries` with tuple pattern: documented for maps/enumerate, worked for list of tuples too.
- Wished: bitwise ops (`<<`, `&`) -- I used `2.pow(k)` and `%` instead (documented as the replacement).

## 05-reconcile (done, first try)
- Docs: `Int.fmt_fixed(2)` behaviour for negative numbers is not stated ("1234 as 12.34"); I avoided it by formatting `-` + (-cents).fmt_fixed(2). Don't know if it handles negatives itself.
- Docs: `Result.map_err(fn(e) => "{path}: {e}")?` worked; "?" needing the same error type was documented and useful (I made everything Str).
- A `match` arm `None => return Err(..)` without trailing comma at end of match was accepted when last; `Some(r) => recs.push(r),` unit-typed arms in a match statement fine.
- `m.or_insert(k, [])` then `m[k].push(x)`: worked, matches doc.
- `for j in by_amount.get_or(b.cents, [])`: empty list literal typed by inference, worked.
- `match m { 4 | 6 | 9 | 11 => 30, _ => 31 }` or-patterns on ints worked.

## 06-costbasis (done, first try)
- Docs: passing a map entry as a `mut` argument (`take(mut book[sym], k)`) is not shown explicitly (only `mut path` for a variable); I guessed it is a legal place, and it compiled and worked. Worth one sentence in §6.
- Docs: `List.remove(i)` returns the removed element (so needs `let _ =`); the signature is only in the prelude, library.md just lists the name.
- Docs: `book.keys()` returns a List[Str] I can `.sort()` after `var`; assumed from "keys" in the Map list; fine.
- `let Some(x) = ... else { ...; continue }` inside a `while let`: worked, and the else block may contain several statements.
- Enum variants used unqualified (`Buy(sym, q, p)`) in patterns and constructors: nice and worked; tag `Trade` unused name otherwise.

## 07-vending (done, first try)
- Docs: `const` with a List value (`const COINS: List[Int] = [...]`) is allowed ("any expression") and `COINS[i]`, `COINS.index_of(c)` work; but every use re-evaluates it (per §12 note) -- I wasn't sure about performance in a hot loop; not tested.
- Docs: `fn Machine.new() -> Machine` associated function then `var m = Machine.new()` and `m.handle(..)` on a `mut self` method: worked as documented.
- Docs: a `mut self` method that calls another `mut self` method (`self.load(t)`) is not mentioned explicitly; it worked.
- Docs: `Int.min(other)` exists (`avail[i].min(...)`), fine.
- Docs: `Option` returned from `index_of` is `Option[Int]` (guessed; the library list says only `index_of`).
- `con.println(...)` + `con.flush()` per line: documented in library.md, clear.

## 08-vfs (done, first try)
- Docs: `enum Res { Found(Int), Missing(Int, Str), Fail(Str) }` with a method taking `mut self` that does `match sres { Fail(e) => return e, ..., Found(n) => id = n }` -- `return` in match arms used as statements while other arms assign worked. Not shown in docs but natural.
- Docs: `return match r { ... }` (match as the operand of return, with blocks containing statements then a value) worked.
- Docs: `let id = match r { Fail(e) => return e, ... Found(id) => id }`: the arm pattern binding `id` while the outer `let id` is being declared did not trigger the no-shadowing error (pattern binding scope precedes the let name?). Surprising but accepted; unclear whether intended.
- Docs: `fn Tree.contains(self, ...)` ends with `while true {...}` and then a trailing `false`; the reference says a function may end with `while true` without `break`; I added `false` anyway and it compiled (no "unreachable code" error). Fine.
- Docs: a method named `Tree.move` -- `move` is not reserved; ok. A struct named `Fs` would clash with the prelude capability -- I avoided it.
- `for (_, kid) in n.kids` pattern with `_` over a map: worked.
- Wished: `Map.keys()` sorted variant (`sorted_keys`), and list `reverse()` being in place vs. `reversed()` -- both exist, documented by name only (I had to guess `reverse` is in place on a var).

## 09-bookmarks (done; one self-inflicted garbage line fixed before the first run passed)
- Docs: `Fs.write` is described as "writes path.tmp, fsyncs, renames over path". That is exactly the spec's snapshot protocol, so `fs.write(snap, text)` implements COMPACT's first three steps. This is only discoverable by reading §10 closely; a sentence in library.md "use Fs.write for snapshot files" would help (the `journal` module note points the other way: "cannot read a file format that a task fixes").
- Docs: `Fs.exists` / `is_dir` return plain Bool (not Result), visible only in prelude.tn. library.md lists names only.
- Docs: `fs.mkdir_one(dir)` for "create only the last path component" -- good, documented in reference §10.
- Docs: `Fs.truncate` requires an existing file; to empty a journal that may not exist I used `fs.write(path, "")`. Fine but a "create or truncate" would be handy.
- Docs: `s.rfind("\n")` returns Option[Int] (library says "byte offset of the last match"); `slice(0, i + 1)` fine.
- Docs unclear: a `mut` parameter of struct type (`store: mut Store`) called with `mut store`, combined with a `mut self` method called on it inside (`store.apply(cmd)`): worked.
- `if let Compact = cmd { ... } else { ... }`: pattern with a payload-less variant, worked.
- Surprise: `List.pop()` result must be discarded explicitly (`let _ = lines.pop()`), consistent with the rule; but `lines.slice(1, lines.len())` for a tail is verbose; wished `lines.tail()`/`drop(1)`.
- Wished: a `for line in text.lines()` that tells me whether the last line ended with "\n" (I used ends_with + split + pop).

## 10-war (done, first try)
- Docs: no deque/queue type; I wrote a small `Deck` struct (list + head index). A builtin `Deque` (or `List.pop_front`, which `remove(0)` O(n) is the only substitute for) would help for simulations.
- Docs: `let (Some(a), Some(b)) = (x, y) else { ... }` worked (let-else with a tuple of variant patterns); nowhere shown in the reference.
- Docs: multi-line boolean expression with `and` at the start of the continuation line worked, matching §2.
- Docs: `Str.find(sub)` returns Option[Int]; used `RANKS.find(b.char())` as an "index in alphabet" idiom. No `Str.index_of`-style helper for chars; fine.
- Docs: a method named `Deck.len` / `Deck.put` on my own struct -- fine; method names shadowing builtin-looking names did not matter.
- Pitfall noticed, not hit: `s.slice(i, i+1)` on a multi-byte character may split it; docs say offsets are bytes but not whether slice traps in the middle of a character.
- Tool pitfall (mine): macOS sed -i needs an argument; not a Tenon problem.
