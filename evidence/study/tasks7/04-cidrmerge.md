# Task 04: cidrmerge (merge IPv4 address blocks)

## Goal

Write a program that reads a list of IPv4 addresses and CIDR blocks (such as
`10.0.0.0/24`), one per line, and prints the smallest list of CIDR blocks
that covers exactly the same addresses, in address order. Overlapping and
adjacent blocks are merged. With `-r` it prints the merged address ranges
instead, with their sizes. Malformed lines are reported and skipped. No
network access is involved: this is arithmetic on 32-bit numbers.

## Interface

```
cidrmerge [-r]
```

- **Arguments.** Either none, or exactly the one argument `-r`. Anything
  else is a usage error: print a message to stderr, print **nothing** on
  stdout, do not read stdin, and exit `2`.
- **stdin.** ASCII text. Lines are split on `\n`. If the input ends with
  `\n`, there is no extra empty line after it. A final line without `\n` is
  still a line. One trailing `\r` is removed from each line.
- **stdout.** The merged blocks (rule 5) or ranges (rule 6).
- **Exit codes.** `0` success, `1` if at least one line was bad (the output
  is still printed), `2` usage error.

## Rules

1. **Ignored lines.** An empty line and a line whose first character is `#`
   are ignored.
2. **Entries.** Every other line must be exactly one entry, with no spaces:
   - an address `a.b.c.d`, where each of the four octets is a decimal
     integer from 0 to 255 without leading zeros (`0` itself is allowed,
     `00` and `01` are not), or
   - a block `a.b.c.d/p`, with an address as above and a prefix length p
     from 0 to 32, also without leading zeros.
   An address alone means the block `a.b.c.d/32`.
3. **Numbers.** An address is the 32-bit number a×2^24 + b×2^16 + c×2^8 +
   d. The block `A/p` covers the 2^(32−p) addresses from A to
   A + 2^(32−p) − 1. A must be a multiple of 2^(32−p) (all bits after the
   first p are zero): `10.0.0.1/24` is bad, `10.0.1.0/24` is fine.
4. **Bad lines.** A line that is not ignored and is not a valid entry
   (wrong syntax, an octet above 255, a leading zero, a prefix above 32,
   non-zero bits after the prefix, spaces anywhere) is **bad**: print a
   message to stderr, skip it, and exit `1` after printing the output.
5. **Merging.** The union of all covered addresses is split into maximal
   ranges of consecutive addresses (two blocks that overlap or touch, such
   as `10.0.0.0/24` and `10.0.1.0/24`, are in one range). Each range from
   S to E is written as the fewest CIDR blocks, found greedily: starting
   at S, take the largest block that starts at S (S is a multiple of its
   size) and ends at or before E; print it; continue right after it until
   E is passed. Ranges are printed in increasing address order. Each block
   is printed as `a.b.c.d/p`, always with the `/p`, even for `/32`.
6. **Ranges (`-r`).** With `-r`, each maximal range is printed instead as
   `<first>-<last> <count>`, where `<first>` and `<last>` are the first and
   last address in dotted form and `<count>` is the number of addresses in
   the range, in decimal.
7. **Output lines.** Each line ends with `\n`. If there are no valid
   entries, nothing is printed.
8. **Limits.** At most 100000 lines. A count can be 2^32 = 4294967296, which
   does not fit in 32 bits.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: adjacent and overlapping blocks

cmd: `cidrmerge`

stdin (the line `192.168.1.6` ends with `\r\n`):
```
10.0.0.0/24
10.0.1.0/24
192.168.1.5
192.168.1.4
# comment

192.168.1.6
192.168.1.7
192.168.1.8/31
```
stdout:
```
10.0.0.0/23
192.168.1.4/30
192.168.1.8/31
```
exit: `0`

(192.168.1.4 to 192.168.1.9 is one range of 6 addresses. The largest block
starting at .4 that fits is /30 (.4 to .7), then .8/31 covers the rest.)

### Example 2: a range that needs several blocks

cmd: `cidrmerge`

stdin:
```
10.0.0.6
10.0.0.2/31
10.0.0.1
10.0.0.4/31
```
stdout:
```
10.0.0.1/32
10.0.0.2/31
10.0.0.4/31
10.0.0.6/32
```
exit: `0`

With `10.0.0.0/30` as an extra line, the range becomes 10.0.0.0 to 10.0.0.6
and the output is `10.0.0.0/30`, `10.0.0.4/31`, `10.0.0.6/32`.

### Example 3: ranges

cmd: `cidrmerge -r`

stdin:
```
10.0.0.6
10.0.0.0/30
10.0.0.4/31
172.16.0.0/12
172.32.0.0/16
1.2.3.4
```
stdout:
```
1.2.3.4-1.2.3.4 1
10.0.0.0-10.0.0.6 7
172.16.0.0-172.32.255.255 1114112
```
exit: `0`

(Without `-r`, the third range would be printed as `172.16.0.0/12` and
`172.32.0.0/16`.)

### Example 4: everything

cmd: `cidrmerge -r`

stdin:
```
1.2.3.4
0.0.0.0/0
```
stdout:
```
0.0.0.0-255.255.255.255 4294967296
```
exit: `0`

Without `-r` the output is `0.0.0.0/0`.

### Example 5: bad lines and usage errors

cmd: `cidrmerge`

stdin (the 6th line starts with a space):
```
10.0.0.1/24
256.1.1.1
01.2.3.4
1.2.3.4/33
1.2.3
 1.2.3.4
1.2.3.4/032
10.0.0.0/8
```
stdout:
```
10.0.0.0/8
```
exit: `1`

Each of these gives stdout (empty) and exit `2`: `cidrmerge -x`,
`cidrmerge -r -r`, `cidrmerge input.txt`.

## Not required

- IPv6.
- Subtracting blocks, or listing the gaps between ranges.
- Any particular stderr wording.
