# Task 10: cachesim (two-level cache hierarchy simulator)

## Goal

Write a simulator for a two-level CPU cache (L1 and L2) in front of main
memory. It reads a trace of memory reads and writes, decides for each access
whether it hits in L1, hits in L2, or has to go to memory, and prints that
decision followed by summary counters. Both caches are set-associative with
least-recently-used (LRU) replacement and write-back. Dirty L1 victims are
written back into L2, and dirty L2 victims into memory. The result is fully
determined by the rules below.

## Interface

```
cachesim [-b BLOCK] [-1 SETS:WAYS] [-2 SETS:WAYS]
```

- **Options** (each option and its value are two separate arguments, in any
  order; if an option is repeated, the last one wins):
  - `-b BLOCK`: the block size in bytes. BLOCK must match `[0-9]{1,4}` and
    be a power of two from 1 to 4096. Default: `16`.
  - `-1 SETS:WAYS`: the L1 geometry. Default: `4:2`.
  - `-2 SETS:WAYS`: the L2 geometry. Default: `16:4`.

  In a geometry, SETS must match `[0-9]{1,4}` with a value from 1 to 4096
  (it need not be a power of two), and WAYS must match `[0-9]{1,2}` with a
  value from 1 to 64.
- **Usage errors (exit 2):** any other argument, an option without a value,
  or a malformed or out-of-range value. Print a message to stderr, print
  nothing on stdout, and do not read stdin.
- **stdin.** The trace, one access per line. Lines are split on `\n`. A final
  line without `\n` is still a line. One trailing `\r` is removed from each
  line. Lines that are empty or contain only spaces are ignored. Every other
  line must be exactly:

  ```
  <op> 0x<hex>
  ```

  with a single space, where `<op>` is `R` (read) or `W` (write), the prefix
  is `0x` (lower-case `x`), and `<hex>` is 1 to 8 hexadecimal digits in any
  case.
- **Invalid trace (exit 1).** If any line breaks these rules, print a message
  to stderr, print **nothing** on stdout, and exit `1`. The whole trace is
  validated before any output is written.
- **stdout.** One line per access, then the summary (rule 6). Every line ends
  with `\n`.
- **Exit codes.** `0` success, `1` invalid trace, `2` usage error.

## Rules

1. **Blocks and sets.** The address `a` is the hexadecimal number. Its
   *block* is `a / BLOCK` (integer division). In a cache with S sets, a block
   `b` lives only in set `b mod S`. A set holds at most WAYS blocks. Each held
   block has a *dirty* flag. Within a set, blocks are ordered by last use;
   the *LRU* block is the one used longest ago. "Make MRU" means mark the
   block as the most recently used in its set.
2. **Installing.** To install block `b` into a cache: if `b`'s set already
   holds WAYS blocks, first remove its LRU block (the *victim*); then add `b`
   as MRU with the given dirty flag. Victim handling is described in rules 4
   and 5.
3. **An access** to block `b` with operation `op`:
   1. **L1 lookup.** If L1 holds `b`: this is an **L1 hit**. Make `b` MRU in
      L1; if `op` is `W`, set its dirty flag. The access is done; the result
      is `L1`.
   2. Otherwise it is an **L1 miss**. **L2 lookup:** if L2 holds `b`, it is an
      **L2 hit**: make `b` MRU in L2 (its dirty flag is unchanged), and the
      result is `L2`. Otherwise it is an **L2 miss**: the block is read from
      memory and installed into L2, clean (rule 2, with rule 5 for the
      victim), and the result is `MEM`.
   3. Then install `b` into L1 (rule 2, with rule 4 for the victim), dirty
      if `op` is `W` and clean if it is `R`.

   L2 keeps its copy of `b` after `b` is brought into L1, and a block may be
   in L1 without being in L2 (L2 is not inclusive).
4. **L1 victims.** A clean L1 victim is dropped. A dirty L1 victim `v` is
   **written back** to L2 (counted in L1 `writebacks`): if L2 holds `v`, set
   its dirty flag and make it MRU in L2; otherwise install `v` into L2 as
   dirty (rule 2, with rule 5 for that victim). A write-back is not an L2
   lookup: it counts as neither an L2 hit nor an L2 miss.
5. **L2 victims.** A clean L2 victim is dropped. A dirty L2 victim is written
   to memory (counted in L2 `writebacks`). Removing a block from L2 never
   affects L1.
6. **Output.** For each access, in trace order, print the `<op>` and the
   address exactly as written in the trace (for example `R 0xAbC`), a space,
   and the result: `L1`, `L2` or `MEM`. After the last access, print exactly
   two lines:

   ```
   L1 hits=<h1> misses=<m1> writebacks=<w1>
   L2 hits=<h2> misses=<m2> writebacks=<w2>
   ```

   where `h1`/`m1` count L1 hits/misses, `h2`/`m2` count L2 hits/misses,
   `w1` counts dirty L1 victims written back to L2, and `w2` counts dirty L2
   victims written to memory. Blocks still dirty at the end are not written
   back.
7. **Limits.** At most 200000 accesses.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: misses, hits and write-backs

cmd: `cachesim -b 16 -1 1:2 -2 2:2`

stdin:
```
R 0x00
R 0x04
W 0x10
R 0x20
R 0x00
R 0x14
R 0x30
W 0x50
R 0x58
```
stdout:
```
R 0x00 MEM
R 0x04 L1
W 0x10 MEM
R 0x20 MEM
R 0x00 L2
R 0x14 L2
R 0x30 MEM
W 0x50 MEM
R 0x58 L1
L1 hits=2 misses=7 writebacks=1
L2 hits=2 misses=5 writebacks=1
```
exit: `0`

Step by step (L1 has one set of 2 ways; L2 has 2 sets of 2 ways; blocks are
0, 0, 1, 2, 0, 1, 3, 5, 5; a `*` marks a dirty block; sets are listed from
LRU to MRU):

| Access | Block | L1 after | L2 set 0 after | L2 set 1 after | Notes |
|---|---|---|---|---|---|
| R 0x00 | 0 | 0 | 0 | | |
| R 0x04 | 0 | 0 | 0 | | L1 hit |
| W 0x10 | 1 | 0 1* | 0 | 1 | |
| R 0x20 | 2 | 1* 2 | 0 2 | 1 | L1 victim 0 is clean |
| R 0x00 | 0 | 2 0 | 2 0 | 1* | L1 victim 1* is written back to L2 |
| R 0x14 | 1 | 0 1 | 2 0 | 1* | L1 victim 2 is clean |
| R 0x30 | 3 | 1 3 | 2 0 | 1* 3 | |
| W 0x50 | 5 | 3 5* | 2 0 | 3 5 | L2 victim 1* is written to memory |
| R 0x58 | 5 | 3 5* | 2 0 | 3 5 | L1 hit |

### Example 2: a write-back that installs into L2

cmd: `cachesim -b 4 -1 1:1 -2 1:1`

stdin:
```
W 0x0
R 0x4
R 0x0
R 0x8
```
stdout:
```
W 0x0 MEM
R 0x4 MEM
R 0x0 L2
R 0x8 MEM
L1 hits=0 misses=4 writebacks=1
L2 hits=1 misses=3 writebacks=1
```
exit: `0`

(At `R 0x4`, block 1 replaces the clean block 0 in L2. Then L1 evicts the
dirty block 0, which is installed into L2 as dirty and evicts block 1. At
`R 0x0`, block 0 is found in L2. At `R 0x8`, L2 evicts the dirty block 0 to
memory.)

### Example 3: defaults and address echo

cmd: `cachesim`

stdin:
```
R 0xABC
R 0xab0
```
stdout:
```
R 0xABC MEM
R 0xab0 L1
L1 hits=1 misses=1 writebacks=0
L2 hits=0 misses=1 writebacks=0
```
exit: `0`

(Both addresses are in block 0xAB with the default 16-byte blocks.)

### Example 4: empty trace

cmd: `cachesim -2 1:1`

stdin: (empty)

stdout:
```
L1 hits=0 misses=0 writebacks=0
L2 hits=0 misses=0 writebacks=0
```
exit: `0`

### Example 5: errors

- cmd: `cachesim -b 12` gives stdout (empty) and exit `2`.
- cmd: `cachesim -1 0:2` gives stdout (empty) and exit `2`.
- cmd: `cachesim -1 4` gives stdout (empty) and exit `2`.
- cmd: `cachesim -b` gives stdout (empty) and exit `2`.
- cmd: `cachesim trace.txt` gives stdout (empty) and exit `2`.
- cmd: `cachesim` with stdin `R 0x10\nX 0x10\n` gives stdout (empty) and
  exit `1`.
- cmd: `cachesim` with stdin `R 10\n` gives stdout (empty) and exit `1`.
- cmd: `cachesim` with stdin `W 0x123456789\n` (9 digits) gives stdout
  (empty) and exit `1`.

## Not required

- Timing, cycle counts, prefetching, or other replacement policies.
- Write-through or no-write-allocate caches.
- Flushing dirty blocks at the end.
- Any particular stderr wording.
