# Language gaps hit while writing mdhtml

No compiler crashes, and no interpreter/native disagreements (the transcript is
identical on both backends).

## 1. A line cannot continue with a leading binary operator

What I wanted: wrap a long boolean condition with the operator at the start of
the continuation line, as in most languages.

```tenon
fn starts_block(line: Str) -> Bool {
    is_fence(line) or line == "---"
        or item_marker(line).0 > 0
}
```

Error: `error: expected an expression, found 'or'` (at the `or`). It points at
the continuation line rather than saying that a newline ended the statement.

Section 2 of the reference does say that only lines beginning with `.` or `else`
continue the previous line, so this is documented. What is missing is a hint in
the diagnostic and in the docs that a trailing operator (or wrapping the whole
expression in parentheses) is the way to break a long condition.

Workaround: parenthesise the expression and end the first line with the operator:

```tenon
    (is_fence(line) or line == "---" or
        item_marker(line).0 > 0)
```

## 2. No string builder; `out += piece` is the only way to build output

I wanted a `StringBuilder` or `List[Str].join("")` that is obviously linear.
I used `var out = ""; out += a + b`, which works (a 830 KB input converts in
0.3 s native, 1.7 s in the interpreter), so this is only a note: the reference
does not say whether `Str +=` is amortised linear, and I had to measure it.
