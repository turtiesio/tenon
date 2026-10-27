# csvq: language gaps met while writing it

No compiler crash and no interpreter/native disagreement turned up (all 96
scenario steps give identical transcripts on both backends). Friction:

1. **No comparator sort.** `List.sort_by` only takes a key function, so the
   pairwise rule "numeric when both values are numbers, else string" (which is
   not a key) cannot be expressed. Also a descending sort that stays stable
   cannot be had by reversing.
   - Wanted: `rows.sort_by_cmp(fn(a, b) => cmp_vals(a[c], b[c]))`
   - Did instead: a 20-line generic stable merge sort, `msort[T](xs, le: fn(T, T) -> Bool)`.
   - Snippet: `xs.sort_by(fn(a, b) => a < b)` fails with
     `type mismatch: expected fn(Int) -> _, found fn(_, _) -> Bool`.

2. **No top-level constants and no Int limits.** I needed `i64::MAX` for
   overflow checks (a trap cannot be caught, so sums must be checked before
   they overflow). `let MAX = 9223372036854775807` at file level is a parse
   error (`expected 'fn', 'struct' or 'enum', found 'let'`), and there is no
   `Int.max_value()`. Did instead: `fn int_max() -> Int { 9223372036854775807 }`.

3. **`Int` minimum cannot be written.** `let m = -9223372036854775808` gives
   `integer literal does not fit in Int (64-bit)` (the literal is lexed before
   the minus is applied). Worked around by keeping all values in
   `[-MAX, MAX]` so `abs()` never traps.

4. **No checked/wrapping arithmetic.** Overflow always traps, so decimal
   parsing and summing carry hand-written `add_checked` / `mul_checked`
   (`if a.abs() > int_max() / b.abs() { ... }`).

5. **No exact decimal type / no float formatting control.** `0.1 + 0.2` prints
   `0.30000000000000004`, and there is no "format with 2 decimals". Sums and
   averages are therefore done on scaled integers (`Num { units, scale }`) with
   hand-written rounding and printing.

6. **OS error text leaks through `IoError.Failed`.** Reading a directory gives
   `Failed("./: Is a directory")`-style text that differs by platform, so I did
   not put that case in the transcript. (Minor; `NotFound` is clean.)

7. **Doc gaps (all answered by experiment).** `reference.md` does not say
   that `+=` works on `Str` (it does), that a closure may be
   `fn(a, b) => if c { .. } else { .. }` (it can), or that a tuple pattern may
   nest inside `Some((a, b))` (it can). Not blocking, just guesses that paid off.

Spec ambiguities settled in `csvq.tn`'s header comment: grouping prints a header
line `group,count` / `group,sum` / `group,avg`; `--sort`/`--select` with
`--group` is an error; averages round half away from zero; all errors (also an
unreadable file) exit 2.
