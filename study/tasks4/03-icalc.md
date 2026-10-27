# Task 03: icalc (integer expression calculator)

## Goal

Write a command-line calculator that evaluates one integer arithmetic
expression given as an argument and prints the result. Expressions have
`+`, `-`, `*`, `/`, `%`, unary minus, parentheses and named variables whose
values are set with `-D` options. Division truncates toward zero. Errors in
the expression (bad syntax, division by zero, overflow, an undefined
variable) are reported on stdout with a fixed message and exit code `1`;
command-line mistakes are usage errors with exit code `2`.

## Interface

```
icalc [-D NAME=VALUE]... EXPR
```

- **Arguments** are processed left to right. An argument that is exactly
  `-D` is an option, and the **next** argument is its value, whatever it
  looks like. Every other argument is EXPR (so `-3+4` and `--` are EXPRs).
  There must be exactly one EXPR.
- **`-D` value.** Must match `[a-z][a-z0-9_]{0,15}=-?[0-9]{1,15}` exactly: a
  variable name, `=`, and an integer (leading zeros allowed; `-0` is 0). If
  the same name is defined more than once, the last definition wins.
- **Usage errors (exit 2).** No EXPR, more than one EXPR, `-D` without a
  following argument, or a malformed `-D` value. Print a message to stderr
  and print **nothing** on stdout.
- **stdin.** Not used.
- **stdout.** On success, the result as a decimal integer (with `-` if
  negative, no leading zeros, `0` for zero) followed by `\n`. On an
  expression error, exactly one line `error: <reason>` (rule 5).
- **Exit codes.** `0` success, `1` expression error, `2` usage error.

## Rules

1. **Tokens.** EXPR is ASCII. Spaces (only the character 0x20) may appear
   between tokens and at either end, and are ignored. The tokens are:
   - a **number**: a maximal run of the digits `0`-`9`, 1 to 15 digits long
     (leading zeros allowed, `007` is 7). A run of 16 or more digits is a
     syntax error;
   - a **name**: a letter `a`-`z` followed by a maximal run of `a`-`z`,
     `0`-`9` and `_` (any length);
   - one of the characters `+ - * / % ( )`.

   Any other character (including upper-case letters, tabs and `.`) is a
   syntax error.
2. **Grammar.** From lowest to highest precedence:

   ```
   expr   := term (("+" | "-") term)*
   term   := unary (("*" | "/" | "%") unary)*
   unary  := "-" unary | primary
   primary:= number | name | "(" expr ")"
   ```

   Binary operators are left-associative: `10-4-3` is `(10-4)-3`. Unary minus
   binds tighter than every binary operator and may be repeated: `-7/2` is
   `(-7)/2`, `2*-3` is `2*(-3)` and `--3` is 3. There is no unary `+`. The
   whole EXPR must be exactly one `expr`; an empty EXPR, a leftover token or
   a missing operand is a syntax error.
3. **Syntax first.** The whole EXPR is checked for syntax before anything is
   evaluated. If it has any syntax error, the result is `error: syntax`,
   even if evaluating a part of it would have failed in another way.
4. **Evaluation.** A binary operation evaluates its left operand completely,
   then its right operand, then applies the operator. The first error stops
   the evaluation.
   - A name evaluates to its `-D` value. A name without a definition is the
     error `undefined <name>`.
   - `a / b` is the quotient **truncated toward zero**: `7/2` is 3, `-7/2` is
     -3, `7/-2` is -3.
   - `a % b` is the remainder `a - (a / b) * b` with the truncated quotient,
     so it has the sign of `a`: `-7%3` is -1, `7%-3` is 1.
   - If `b` is 0, `/` and `%` give the error `division by zero`.
   - **Overflow.** The value of every `+`, `-`, `*`, `/` and `%` operation must
     have an absolute value of at most 999999999999999 (10^15 − 1);
     otherwise it is the error `overflow`. (Numbers, `-D` values and unary
     minus cannot exceed this limit by themselves.)
5. **Error output.** The reasons are exactly `syntax`, `division by zero`,
   `overflow` and `undefined <name>`, for example `error: undefined rate`.
6. **Limits.** EXPR is at most 1000 bytes and nests parentheses at most 50
   deep.

## Examples

Each output line shown ends with `\n`. In `cmd`, arguments are separated by
spaces, except that an argument that contains spaces is shown in double
quotes (the quotes are not part of the argument).

### Example 1: precedence and truncation

- cmd: `icalc 1+2*3` gives stdout `7\n` and exit `0`.
- cmd: `icalc (1+2)*3` gives stdout `9\n` and exit `0`.
- cmd: `icalc -7/2` gives stdout `-3\n` and exit `0`.
- cmd: `icalc -7%3` gives stdout `-1\n` and exit `0`.
- cmd: `icalc "-17 / 5 * 5 + -17 % 5"` gives stdout `-17\n` and exit `0`.
- cmd: `icalc " 0007 "` gives stdout `7\n` and exit `0`.

### Example 2: variables

- cmd: `icalc -D x=10 -D y=-4 "x*x + y"` gives stdout `96\n` and exit `0`.
- cmd: `icalc -D rate=7 -D rate=3 -D n_2=-0 "(rate - n_2) * -(2 + rate) / 4"`
  gives stdout `-3\n` and exit `0`. (`rate` is 3; `3 * -5` is -15, and
  `-15 / 4` is -3.)

### Example 3: evaluation errors

- cmd: `icalc 1/0` gives stdout `error: division by zero\n` and exit `1`.
- cmd: `icalc 5%0` gives stdout `error: division by zero\n` and exit `1`.
- cmd: `icalc 999999999999999+1` gives stdout `error: overflow\n` and exit
  `1`.
- cmd: `icalc 999999999999999*2/2` gives stdout `error: overflow\n` and exit
  `1` (the product already overflows).
- cmd: `icalc z+1` gives stdout `error: undefined z\n` and exit `1`.
- cmd: `icalc 1/0+z` gives stdout `error: division by zero\n` and exit `1`.
- cmd: `icalc z+1/0` gives stdout `error: undefined z\n` and exit `1`.

### Example 4: syntax errors

Each of these gives stdout `error: syntax\n` and exit `1`:

- cmd: `icalc 1+`
- cmd: `icalc 1/0+` (syntax is checked before evaluation)
- cmd: `icalc +1`
- cmd: `icalc 2x`
- cmd: `icalc X`
- cmd: `icalc "1 2"`
- cmd: `icalc ()`
- cmd: `icalc 1234567890123456`
- cmd: `icalc --`
- cmd: `icalc` with a single empty-string argument (the `cmd` file is one
  empty line)

### Example 5: usage errors

Each of these gives stdout (empty) and exit `2`:

- cmd: `icalc`
- cmd: `icalc 1 2`
- cmd: `icalc -D`
- cmd: `icalc -D x=5`
- cmd: `icalc -D x 1`
- cmd: `icalc -D X=1 1`

## Not required

- Exponentiation, bitwise operators, comparison operators, functions.
- Unary `+`, floating-point numbers, numbers in other bases.
- Assignment inside EXPR, or more than one expression per run.
- Any particular stderr wording.
