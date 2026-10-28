# Task 04: salesreport (CSV aggregation)

## Goal

Read a CSV file of sales rows, validate each row strictly, optionally filter by
an inclusive date range, and print a per-region summary as CSV. Each region
gets its total units, total revenue, average unit price and best-selling
product, followed by a grand-total row and a count of rejected rows. All money
arithmetic must be exact: use integer cents, never floating point.

## Interface

```
salesreport [--from DATE] [--to DATE] FILE
```

- **Arguments.** Exactly one `FILE` is required.
- **Options.** `--from DATE` / `--from=DATE` and `--to DATE` / `--to=DATE`
  filter by date, inclusive on both ends. `DATE` has the form `YYYY-MM-DD` and
  must be a real calendar date (rule 3). Options may come before or after
  `FILE`. If an option is repeated, the last one wins.
- **stdout.** The report (format below).
- **stderr.** One message per rejected row, for example
  `line 5: invalid date`. The wording is not tested.
- **Exit codes.**
  - `0`: the report was printed. Rejected rows do **not** change the exit code.
  - `1`: `FILE` cannot be read, or its first line is not the exact header.
    Nothing is printed to stdout.
  - `2`: usage error: no `FILE`, more than one `FILE`, an unknown option, a
    missing option value, or an invalid `DATE` in an option. Nothing is
    printed.

## Input format

- Lines are separated by `\n`. A trailing `\r` on any line is removed. The
  last line may lack `\n`.
- **Line 1** must be exactly `date,region,product,units,unit_price`. A
  zero-byte file also counts as a bad header and exits 1.
- **Every later line** is a data row. Completely empty lines are ignored
  silently: they are not rows and not counted.
- **CSV field syntax.** Fields are separated by `,`.
  - A field that starts with `"` is quoted. It continues up to the next `"`
    that is not immediately followed by another `"`, and inside it `""` stands
    for one `"`. The closing quote must be followed by `,` or the end of the
    line.
  - An unquoted field must not contain `"`.
  - A quoted field cannot span lines.
  - Any violation of these rules makes the row malformed.

## Rules

1. **Row validation.** A row is **rejected** (counted in `skipped`, with a
   stderr message) if any of these hold:
   - it is malformed CSV, or it does not have exactly 5 fields;
   - `date` is not a valid date (rule 3);
   - `region` or `product` is empty. Any other content is allowed, including
     commas and quotes when the field is quoted, and spaces are significant;
   - `units` does not match `[0-9]+` or is greater than 10000. Leading zeros
     are allowed;
   - `unit_price` does not match `[0-9]+\.[0-9][0-9]` (exactly two decimals)
     or is greater than `10000.00`. Leading zeros are allowed.
2. **Filtering.** Validation happens first. A **valid** row whose date is
   before `--from` or after `--to` is excluded **silently**: it is not printed
   and not counted in `skipped`. If `--from` is later than `--to`, no rows
   match. That is not an error.
3. **Dates.** `YYYY-MM-DD` is exactly 4+2+2 digits. The year is 0001-9999, the
   month 01-12, and the day must be within the length of that month. February
   has 29 days in leap years (divisible by 4, except centuries not divisible
   by 400).
4. **Money.** Convert `unit_price` to integer cents. A row's revenue is
   `units × cents`. Every total is an exact integer number of cents.
   Format cents `c` as `<c div 100>.<c mod 100 as 2 digits>`, for example
   `0.00`, `5.05`, `124.97`. There are no thousands separators.
5. **Average price.** `avg_price = revenue_cents / units`, rounded to whole
   cents **half-up**, which equals `floor((2·revenue + units) / (2·units))`. It
   is formatted like money. If `units` is 0, print `-`.
6. **Top product.** Within a group, take the product with the largest revenue.
   Break ties by product name in ascending byte order. A product with 0 revenue
   can still be the top product. If the group has no rows, print `-`.
7. **Regions.** Group the accepted, in-range rows by the exact `region` string.
   Print one row per region, in ascending byte order of the region name.
8. **TOTAL row.** Taken over all accepted, in-range rows. Its `top_product` is
   computed over products summed across all regions. It is printed even when
   there are no rows (`TOTAL,0,0.00,-,-`). A region literally named `TOTAL` is
   printed as a normal region row as well.
9. **Duplicate rows** are counted every time they appear.
10. **Limits.** At most 100000 data rows. All totals stay below 2^53 cents.

## Output format

```
region,units,revenue,avg_price,top_product
<one row per region>
TOTAL,<units>,<revenue>,<avg_price>,<top_product>
skipped <number of rejected rows>
```

- Each line ends with `\n`.
- Output fields that contain `,` or `"` are written CSV-quoted: wrapped in
  `"`, with every inner `"` doubled. All other fields are written as they are.

## Examples

Every line shown ends with `\n`. The examples use this `sales.csv`:

```
date,region,product,units,unit_price
2026-01-03,East,Widget,10,2.50
2026-01-04,West,"Gadget, large",3,19.99
2026-01-04,East,Gizmo,1,30.00
2026-02-30,East,Widget,1,2.50
2026-01-05,West,Widget,4,2.50
2026-01-06,East,Widget,2,2.5
```

Line 5 is rejected (there is no February 30) and line 7 is rejected (the price
needs exactly two decimals).

### Example 1: full report

cmd: `salesreport sales.csv`

stdout:
```
region,units,revenue,avg_price,top_product
East,11,55.00,5.00,Gizmo
West,7,69.97,10.00,"Gadget, large"
TOTAL,18,124.97,6.94,"Gadget, large"
skipped 2
```
exit: `0`

(The West average is 6997 cents / 7 = 999.57…, which rounds to 1000 cents,
`10.00`. Across all regions, Widget makes 3500 cents, `Gadget, large` 5997
and Gizmo 3000.)

### Example 2: date filter

cmd: `salesreport --from 2026-01-04 --to=2026-01-04 sales.csv`

stdout:
```
region,units,revenue,avg_price,top_product
East,1,30.00,30.00,Gizmo
West,3,59.97,19.99,"Gadget, large"
TOTAL,4,89.97,22.49,"Gadget, large"
skipped 2
```
exit: `0`

### Example 3: header only

`empty.csv` contains only the header line.

cmd: `salesreport empty.csv`

stdout:
```
region,units,revenue,avg_price,top_product
TOTAL,0,0.00,-,-
skipped 0
```
exit: `0`

### Example 4: zero units and quoted quotes

`q.csv`:
```
date,region,product,units,unit_price
2024-02-29,North,"The ""Best"" Mug",0,4.00
2024-02-29,North,Cup,0,1.00
```
cmd: `salesreport q.csv`

stdout:
```
region,units,revenue,avg_price,top_product
North,0,0.00,-,Cup
TOTAL,0,0.00,-,Cup
skipped 0
```
exit: `0` (both products have 0 revenue. `Cup` comes before `The "Best" Mug`
in byte order)

### Example 5: errors

- cmd: `salesreport` gives stdout (empty) and exit `2`.
- cmd: `salesreport --from 2026-13-01 sales.csv` gives stdout (empty) and
  exit `2`.
- cmd: `salesreport missing.csv` gives stdout (empty) and exit `1`.

## Not required

- Quoted fields that contain newlines.
- Negative numbers, or prices with other than exactly two decimals (these are
  simply rejected).
- Any particular stderr wording.
- Encodings other than UTF-8.
