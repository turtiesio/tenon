# NOTES

## 01-wrap
- No hexadecimal integer literals (`0x20`). Error is confusing: `error: expected '{', found 'x20'` (lexes `0` then identifier `x20`). Reference §2 lists literal forms but doesn't say hex is absent; workaround: char literals `' '`, `'~'`.
- Unclear from docs whether `main` returning Int 1 is allowed (1 is listed in "reserved exit codes", and reserved codes "trap instead"). Tested: returning 1 works. Doc should say which codes are reserved for Int returns (70-74 only?).
- Build errors repeat once per try.sh invocation, fine; but no multi-error recovery issue.

## 03-globgrep
- Went smoothly. Enum equality `pat[j] == Star` works as documented (derived ==).

## 04-csvjoin
- Wished for `Result.and_then` / `Result.map` (Option has them, Result only has `map_err`/`ok`); I ended up writing a helper fn with `?` instead, which is fine but the asymmetry is surprising.
- `match` arm `Err(e) => return Err(...)` as an expression arm worked; nice.
- No way to build a Str from a byte other than `Int.char()` / slicing; OK for ASCII.

## 05-standings / 06-buildorder
- Both compiled and passed first try. Tuple-key sort (`sort_by(fn(t) => (key, name))`) with negated ints for descending works well.
- `let _ = set.insert(x)` needed to discard the Bool: slightly noisy but documented (§7).
- Wished for a `Str.is_blank()` or `trim_chars(" ")` being discoverable; found it in reference, good.
- Heap[Str] of strings for "smallest ready" worked out of the box.

## 07-linebuf
- Smooth. Enum-of-changes undo/redo worked first try.
- Wished for a `match` that can fall through to code below without the `None => {}` arm noise, e.g. `if let Some(rest) = s.strip_prefix("X ") { ... }`. Tenon has `let ... else` but no `if let`, so prefix-dispatch parsing becomes a ladder of `match ... { Some(r) => {...}, None => {} }`.
- Unclear perf: `List.insert`/`remove` documented O(n), slice+concat also O(n); fine.

## 08-sheet
- Struct patterns are not supported in `match` (`Some(Cell { contents: Formula(t), .. })`): error `expected ',', found '{'` — doesn't say "struct patterns not supported". The reference's pattern list (§7) omits them, so it's technically documented, but the error message could be clearer.
- No shadowing: `let v = ...; match v { Some(v) => ... }` errors with "'v' is already defined in this function (shadowing is not allowed)". Clear message, but the rule bites on common idioms (match arm bindings count as redeclarations).
- Performance gotcha: I needed `var memo = self.memo; self.memo = []; ...; self.memo = memo` to avoid copy-on-write when passing a field as `mut` while also calling a method on `self`. Not sure if `self.value(i, mut self.memo)` would be legal; docs don't say whether a `mut` argument may alias a field of a (non-mut) receiver. Wished for guidance on this pattern.
- First version with a fresh Map memo per GET took 38 s on a stress input; switching to a List memo cached across GETs took 3.8 s. Map[Int, _] with ~2500 entries seemed comparatively slow.

## 09-todo
- Docs say `Fs.write` already does temp-file+fsync+rename internally; the spec wanted an explicit `todo.db.tmp` + rename, so I did both (write tmp, rename). Unclear what temp file name `Fs.write` itself uses (could it collide with/leave junk in DIR?). Docs don't say.
- `Fs.mkdir` always creates missing parents; no option for "create only the last component", so I had to compute the parent path by hand and check `is_dir`. Wished for `mkdir` vs `mkdir_all`, or a path-join/parent helper.
- No path utilities at all (join, parent, basename).
- Unclear: does `sys.fs.within(dir)` accept an absolute `dir`? Avoided it and concatenated paths.
- `let Some(rest) = ... else { <non-trivial block ending in return> }` worked nicely for dispatch.

## 10-cachesim
- Passed first try. No hex parsing in the prelude (`to_int` is decimal only); wished for `Str.to_int_radix(16)` / `Int.to_str_radix`. Hand-rolled (also in 02-radix).
- `?` inside an expression (`addr * 16 + hex_digit(c)?`) works nicely.

## Overall top points
1. No hex (or binary) integer literals; the error for `0x20` is "expected '{', found 'x20'", which hides the cause.
2. No `if let`; prefix-dispatch parsers need `match ... { Some(r) => ..., None => {} }` ladders or `let-else` contortions.
3. No struct patterns in `match` (`Cell { field: P, .. }`); error "expected ',', found '{'" does not say so.
4. No shadowing, including match-arm bindings vs. earlier `let`s: common `let v = f(); match v { Some(v) => ...}` is rejected (clear message though).
5. `Result` lacks `map`/`and_then` while `Option` has them.
6. Exit-code docs are ambiguous: code 1 is listed as "reserved", and reserved codes "trap instead" when returned from main as Int — but returning 1 works. Say which codes trap.
7. No path helpers (join/parent/basename), and `Fs.mkdir` always creates parents (no "create only the last component" variant).
8. `Fs.write` is documented as atomic via a temp file, but the temp file name/location isn't documented; matters when a spec owns the directory.
9. No radix conversion helpers (`to_int_radix`, `to_str_radix`).
10. Performance guidance for passing a struct field as a `mut` arg while also using `self` is missing; I resorted to "take the field out, set it to [], put it back" to avoid copy-on-write copies. Also Map[Int,_] memo was much slower than a List.
