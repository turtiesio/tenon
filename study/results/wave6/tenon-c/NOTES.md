# TENON study notes

## 01-wcx (done)
- The quickstart and prelude supplied the byte input, Unicode count, collection, and padding APIs needed. No compiler errors or documentation gaps encountered.
- Wished for dynamically specified interpolation widths; pad_left worked clearly.

## 02-b64 (done)
- No documentation gaps or compiler errors encountered. Byte-list input/output made binary filtering straightforward.
- Wished for a documented byte-buffer abstraction or reserve capacity for up to one million bytes; used List[Int] and amortized append.

## 03-hsize (done)
- No compiler errors or missing documentation encountered. Integer arithmetic and explicit padding expressed the required exact rounding cleanly.

## 04-shoplist (done)
- The reference explicitly explains that Str.lines retains CR, whereas Console.read_line removes it. This distinction was useful but required a targeted lookup; the prelude's short lines comment alone does not mention CR.
- No compiler errors encountered. Wished for a decimal formatting helper that trims fractional trailing zeros; implemented it explicitly.

## 05-orgchart (done)
- No compiler errors or missing documentation encountered. Tuple sort keys and mut parameters worked as described.
- Wished for integer formatting with thousands separators; implemented a small formatter.
- Function-wide no-shadowing requires distinct names across separate scopes; it remained manageable but is less natural than block-scoped names for parsing and traversal.

## 06-climate (done)
- No compiler errors or missing documentation encountered. Derived tuple-key ordering simplified grouping and sorted reporting.
- Wished for standard Gregorian date validation; the rules were small enough to implement locally.

## 07-rooms (done)
- No compiler errors or missing documentation encountered. Enum payload commands provided a clear boundary between validation and state changes.
- Function-wide no-shadowing is surprisingly permissive across separate match arms (reused room/id names compiled). The docs say a name may be bound once per function, which does not precisely describe this behavior; clarification of mutually exclusive arms would help.

## 08-locks (done)
- No compiler errors or missing documentation encountered. Nested mutating method calls on map entries behaved as documented.
- Wished for a deque: pumping a FIFO with List.remove(0) shifts the remaining entries. The reference documents that cost, so it was predictable.

## 09-helpdesk (done)
- The prelude lists Fs.append but does not state when data reaches the OS; the reference §10 does explicitly promise durability (fsync). That guarantee was essential for this task and could use a prelude comment or quickstart pointer.
- No compiler errors encountered. Tested an actual SIGKILL after three acknowledged responses, then replay and numbering, plus torn-tail recovery and invalid journals left unchanged.
- Wished for a direct truncate operation. Atomic write_bytes of the valid prefix supplied a correct recovery path using the documented API.

## 10-sand (done)
- No compiler errors or missing documentation encountered. Nested list mutation and bottom-up while loops expressed the simulation directly.
- Wished for a descending range syntax; used an explicit decreasing index, since the documented range is ascending and half-open.

## Top 10 observations
1. No confusing compiler errors occurred: all ten initial implementations compiled and their example runs matched the specifications.
2. Clarify the no-shadowing rule: the documentation says once per function, but distinct match arms allowed repeated payload-binding names.
3. Put the Fs.append durability guarantee in the prelude API comments or provide a pointer to reference §10; it matters for persistence correctness.
4. Put the CR behavior of Str.lines in its prelude comment, alongside its final-empty-line behavior; it differs from Console.read_line.
5. A deque would make FIFO services more natural and avoid List.remove(0) shifting costs.
6. A direct file truncation API would simplify journal torn-tail recovery; atomic prefix replacement worked.
7. Dynamic widths in interpolation would simplify count tables; pad_left is an adequate documented alternative.
8. Thousands-separator integer formatting would avoid a custom orgchart formatter.
9. A descending range syntax would simplify bottom-up grid traversal.
10. A byte-buffer or capacity-reservation API would be useful for large binary filters; List[Int] worked, but uses a full Int per byte.
