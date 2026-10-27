# Study notes

## 01-seqx (done)
- No documentation gaps or confusing compiler errors encountered.
- Wished for a standard command-line option parser; manual parsing is straightforward but repetitive.

## 02-trx (done)
- No confusing compiler errors encountered; byte I/O and tuple equality worked as documented.
- Wished for a byte-set or fixed-size array abstraction for ASCII character tables.

## 03-colalign (done)
- Str length and padding use bytes; Unicode column widths require chars().len() and manual space padding. This is documented, but easy to misuse.
- Wished for a code-point count method that avoids materializing a list of characters.
- No confusing compiler errors encountered.

## 04-splitbill (done)
- Int.fmt_fixed(2) made exact-cent reporting convenient.
- No documentation gaps or confusing compiler errors encountered.
- Wished for a standard strict decimal parser with a selectable scale.

## 05-srtfix (done)
- No documentation gaps or confusing compiler errors encountered.
- Wished for standard duration/time parsing and formatting, and interpolation format widths; manual timestamp formatting is verbose.

## 06-libfines (done)
- Nested mutation of map-held structs and lists worked as the quickstart promised.
- No documentation gaps or confusing compiler errors encountered.
- Wished for concise contextual Result error conversion when file parsing mixes I/O and validation.

## 07-leaderboard (done)
- No documentation gaps or confusing compiler errors encountered.
- Explicit flush is available and clear; the protocol loop was straightforward.
- Wished for scoped shadowing: choosing different names for logically equivalent sorted lists in separate match arms adds naming overhead.

## 08-connect4 (done)
- No documentation gaps or confusing compiler errors encountered.
- List.filled and mutating struct methods were sufficient for the game state.
- Wished for a fixed-size multidimensional array type to express board dimensions directly.

## 09-polls (done)
- The journal module cannot be used for a prescribed plain-command log: it adds checksums and removes invalid complete records. Its source documents this accurately, but a configurable raw-record mode would be useful.
- Fs.append durability is documented in reference section 10, but absent from the prelude signature; adding that guarantee beside the API would improve discovery.
- Wished for truncate-to-length: discarding a torn suffix currently requires reading and atomically rewriting the complete prefix.
- No confusing compiler errors encountered.

## 10-robots (done)
- No documentation gaps or confusing compiler errors encountered.
- Wished for a concise character-set membership operation; validation currently chains comparisons or constructs a container.
- The documented byte/Unicode distinction made rejecting non-ASCII grid cells straightforward.

## Top 10 observations
1. A code-point count API would avoid allocating chars() just to measure Unicode fields.
2. String padding is byte-based, so Unicode column alignment needs manual padding.
3. Scoped shadowing would reduce naming overhead across independent match arms.
4. A truncate-to-length file operation would simplify torn journal recovery.
5. Put Fs.append's durability guarantee beside its prelude declaration, as well as in the reference.
6. A plain-record journal mode would help when the persisted format is externally prescribed.
7. Timestamp/duration parsing and formatting would remove verbose manual arithmetic and padding.
8. Interpolation format widths would make normalized numeric output easier to read.
9. Fixed-size arrays, especially multidimensional ones, would express character tables and game boards more directly.
10. Standard strict decimal parsing with a selectable scale would simplify exact-cent input.

All ten tasks compiled without compiler errors. No incorrect documentation claim was encountered.
