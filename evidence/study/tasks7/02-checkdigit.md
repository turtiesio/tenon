# Task 02: checkdigit (verify and compute check digits)

## Goal

Write a command-line tool that verifies or computes the check digit of
identification numbers under one of three schemes: the Luhn algorithm (used
by payment card numbers), ISBN-10 and ISBN-13. In `check` mode each value is
a complete number and is reported as correct, wrong or malformed; in `make`
mode each value is a number without its check digit, and the tool prints it
with the check digit appended. Values may contain single hyphens between
groups of digits, as printed numbers often do.

## Interface

```
checkdigit SCHEME MODE VALUE...
```

- **Arguments.**
  - SCHEME is exactly `luhn`, `isbn10` or `isbn13`.
  - MODE is exactly `check` or `make`.
  - At least one VALUE follows.
  - Fewer than 3 arguments, or an unknown SCHEME or MODE, is a usage error:
    print a message to stderr, print **nothing** on stdout, and exit `2`.
    A malformed VALUE is **not** a usage error (rule 2).
- **stdin** is not read.
- **stdout.** One line per VALUE, in argument order (rule 6).
- **Exit codes.** `0` if every value was reported `ok` (in `check` mode) or
  got a check digit (in `make` mode); `1` if at least one value was `bad`
  or `invalid`; `2` usage error.

## Rules

1. **Digits of a value.** The *digits* of a VALUE are its characters with
   every `-` removed, in order. In ISBN-10 `check` mode the character `X`
   stands for the digit value 10.
2. **Well-formed values.** A VALUE is **well formed** if all of these hold;
   otherwise it is **invalid**:
   - It is one or more groups separated by single hyphens: it matches
     `[0-9X]+(-[0-9X]+)*`. So it has no leading or trailing hyphen, no two
     hyphens in a row, and no other characters (no spaces, no lower-case
     `x`). The empty string is invalid.
   - `X` appears only in ISBN-10 `check` mode, and only as the very last
     character of the value.
   - The number of digits is:

     | SCHEME | `check` | `make` |
     |---|---|---|
     | `luhn` | 2 to 19 | 1 to 18 |
     | `isbn10` | exactly 10 | exactly 9 |
     | `isbn13` | exactly 13 | exactly 12 |

   - For `isbn13` the first three digits are `978` or `979`.
3. **Luhn.** Number the digits from the right, starting at 1 for the
   rightmost. Every digit at an even position is doubled, and if the result
   is greater than 9, 9 is subtracted from it. The digits at odd positions
   are kept. A number is correct if the sum of all these values is
   divisible by 10. In `make` mode, the check digit is the digit c from 0 to
   9 such that the digits followed by c form a correct number (there is
   exactly one).
4. **ISBN-10.** With digits d1 ... d10 from left to right, the number is
   correct if 10×d1 + 9×d2 + 8×d3 + ... + 2×d9 + 1×d10 is divisible by 11.
   In `make` mode, with s = 10×d1 + 9×d2 + ... + 2×d9, the check value is
   (11 − (s mod 11)) mod 11, written as its digit, or as `X` if it is 10.
5. **ISBN-13.** With digits d1 ... d13 from left to right, the weights
   alternate 1, 3, 1, 3, ... starting with 1 for d1. The number is correct
   if the weighted sum of all 13 digits is divisible by 10. In `make` mode,
   with s the weighted sum of d1 ... d12, the check digit is
   (10 − (s mod 10)) mod 10.
6. **Output lines.** Every line ends with `\n`. VALUE is always printed
   exactly as given.
   - `check` mode: `<VALUE> ok` if the number is correct, `<VALUE> bad` if
     it is well formed but not correct, `<VALUE> invalid` if it is not well
     formed.
   - `make` mode: for a well-formed value, the VALUE followed by its check
     character; if the VALUE contains at least one hyphen, a `-` is put
     between them. For a value that is not well formed: `<VALUE> invalid`.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: Luhn check

cmd: `checkdigit luhn check 79927398713 79927398710 4111-1111-1111-1111 12a 4`

stdout:
```
79927398713 ok
79927398710 bad
4111-1111-1111-1111 ok
12a invalid
4 invalid
```
exit: `1`

(`4` has only one digit; `check` mode needs at least 2.)

### Example 2: Luhn make

cmd: `checkdigit luhn make 7992739871 411111111111111 0 4-1-1`

stdout:
```
79927398713
4111111111111111
00
4-1-1-9
```
exit: `0`

(For `4-1-1` the digits are 4, 1, 1 and c. From the right: c, 1×2 = 2, 1,
4×2 = 8, so c + 11 must be divisible by 10 and c = 9. The value has a
hyphen, so `-9` is appended.)

### Example 3: ISBN-10

cmd: `checkdigit isbn10 make 030640615 0-306-40615 080442957`

stdout:
```
0306406152
0-306-40615-2
080442957X
```
exit: `0`

(For `030640615`: s = 0+27+0+42+24+0+24+3+10 = 130, 130 mod 11 = 9, and
(11 − 9) mod 11 = 2. For `080442957`: s = 199, 199 mod 11 = 1, and the check
value 10 is written `X`.)

cmd: `checkdigit isbn10 check 0306406152 0-8044-2957-X 0306406153 X306406152 080442957x`

stdout:
```
0306406152 ok
0-8044-2957-X ok
0306406153 bad
X306406152 invalid
080442957x invalid
```
exit: `1`

### Example 4: ISBN-13

cmd: `checkdigit isbn13 make 978030640615 978-0-306-40615 123456789012`

stdout:
```
9780306406157
978-0-306-40615-7
123456789012 invalid
```
exit: `1`

(For `978030640615`: 9+21+8+0+3+0+6+12+0+18+1+15 = 93, and (10 − 3) mod 10
= 7. `123456789012` does not start with 978 or 979.)

cmd: `checkdigit isbn13 check 9780306406157 9780306406158 97803064061 978--0306406157`

stdout:
```
9780306406157 ok
9780306406158 bad
97803064061 invalid
978--0306406157 invalid
```
exit: `1`

### Example 5: usage errors

Each of these gives stdout (empty) and exit `2`:

- cmd: `checkdigit luhn check`
- cmd: `checkdigit luhn`
- cmd: `checkdigit isbn check 0306406152`
- cmd: `checkdigit luhn verify 79927398713`
- cmd: `checkdigit LUHN check 79927398713`

## Not required

- Other schemes (EAN-8, UPC, IBAN, Verhoeff, ...).
- Spaces as group separators, or a lower-case `x`.
- Reading values from stdin.
- Any particular stderr wording.
