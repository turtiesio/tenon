# TENON study notes

Only kit files were consulted. All solution builds and executions used try.sh.
Solutions and scratch test drivers are retained.

## Task observations

### 01-hexdump — gave-up
The text examples pass. The binary stdin example fails: expected `ff`, but
Console.read_all() exposes `ef bf bd`, with final offset `00000017` rather
than `00000015`. This loses information before byte() is called.
A binary file containing bytes 00 ff 80 41 fails with:
`Failed("scratch/binary.bin: invalid UTF-8")` (exit 1).
The reference calls Str UTF-8 text, but neither the I/O signatures nor the
quickstart explain these different invalid-UTF-8 policies. No documented
raw-byte input API is available, so the best text-only implementation remains.
I prematurely marked done before comparing the binary output; the subsequent
give-up event corrects that status.

### 02-uniqx — done
A parameter named `unique` caused:
`error: expected a name, found 'unique'`.
It is listed among reserved words, but this error should identify a reserved
keyword instead of making it sound as though no name was provided.
Field skipping needed careful byte scanning; words() deliberately discards the
separator information that this task needs.

### 03-icalc — done
Parsing to an AST and evaluating separately was straightforward with recursive
enums, Option, Result, and mutating parser methods. Checked multiplication is
essential because the domain limit is smaller than Int's machine range.
A final review changed the domain check from abs() to direct lower/upper
comparisons: a valid machine product can be INT_MIN, whose abs() would trap.
The added case `2147483648*-4294967296` correctly prints `error: overflow`.

### 04-timesheet — done
Stable tuple-key sorting and mutable map-entry lists worked as documented.
Explicit discard of remove/insert results is useful but adds boilerplate when
only the mutation matters.

### 05-runoff — done
`List[Bool].filled(...)` caused:
`error: unknown name 'List'`.
`var continuing: List[Bool] = List.filled(...)` works. The API source uses
List[T] in declarations, while the expression-level explicit type-argument
syntax is not explained. The error should explain the call syntax rather than
suggesting the builtin type does not exist.
A shell sequencing mistake initially marked done after a failed test. I fixed
the code and reran every example successfully, then recorded done again before
continuing the next implementation.

### 06-mdtoc — done
Set insertion with an explicitly discarded Bool worked. Literal braces in
strings need escaping even when not intended as interpolation; regex counted
repetition would need that extra layer as documented.

### 07-parking — done
Explicit flush() made the response protocol clear. Integer fmt_fixed(2) was a
good fit for cents; monetary values never needed floats.

### 08-pubsub — done
Value-captured predicate closures and deep mutation of map fields worked.
Mailbox removal uses List.remove(0); a queue interface would express intent
more clearly (mailboxes here are small, so performance is not a concern).

### 09-shorten — done
Fs.append's documented durability and Fs.write's replacement semantics support
the required journal. Tested exact journal contents, SIGKILL after acknowledged
responses, torn tails, sequence gaps, inconsistent records, and restarts.
Recovering the valid prefix required maintaining an explicit byte/string
prefix because lines() drops the final terminator distinction. A line-reading
API that also reports whether a terminator was present would help recovery code.
The journal module is documented as checksummed, so it would not implement this
task's externally fixed plain numbered record format directly.
Fs.read rejecting invalid UTF-8 also means arbitrary binary corruption in a
journal cannot be scanned to its valid text prefix through this API.

### 10-elevator — done
Per-floor lists and explicit type annotations for empty nested lists worked.
No shadowing is clear in the docs, but it required distinct binding names
across match arms and made long protocol handlers harder to name naturally.
The simulation skips idle intervals and scans at most 100 floors for targets.

## Top 10 usability points

1. Add raw-byte I/O and a byte buffer type: arbitrary binary hexdump input
   cannot be represented by the documented text I/O.
2. Document invalid UTF-8 policies explicitly: console input replaces bytes,
   while file input rejects them; both behaviors were observed.
3. Explain associated-call type arguments and improve `unknown name 'List'`
   for `List[Bool].filled(...)`; a result annotation plus List.filled works.
4. Diagnose reserved identifiers explicitly: `expected a name, found 'unique'`
   hides the useful explanation that unique is a keyword.
5. I wanted lexical shadowing, at least independent names in separate match
   arms; function-wide uniqueness increases naming overhead in protocol code.
6. I wanted a queue/deque API with pop_front for FIFO mailboxes and similar
   state machines, rather than expressing a queue operation as remove(0).
7. I wanted a line API that preserves whether the final newline was present;
   durable journal recovery must distinguish a torn last record.
8. I wanted concise ASCII validation helpers such as all_ascii_lower or a
   predicate over bytes; repeated manual validators are verbose. Regex exists,
   but introduces compilation/error handling and string escaping.
9. I wanted optional interpolation format specifiers: hex widths, zero
   padding, and aligned counts require repeated conversion/padding chains.
10. I wanted more bounded-arithmetic helpers or examples: checked operations
    protect the machine range, but application bounds still require explicit
    checks, and abs(INT_MIN) is unsafe for those checks.
