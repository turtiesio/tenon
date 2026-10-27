# Task 05: latency (access-log percentile report)

## Goal

Parse an HTTP access log and report, for each endpoint, the request count,
the server-error count and rate, nearest-rank latency percentiles (p50, p90,
p99) and the maximum latency. Endpoints are normalized by replacing numeric
path segments with `:id` and dropping query strings. Malformed lines are
counted, not fatal.

## Interface

```
latency [--sort=count|p99|name] [--min-count=N] [FILE]
```

- **Input.** If `FILE` is given, read it. Otherwise read standard input. At
  most one `FILE` may be given.
- **Options.**
  - `--sort=KEY` chooses the output order (default `count`).
  - `--min-count=N` hides endpoints with fewer than N requests. N is a decimal
    integer from 1 to 1000000000, digits only. Default: 1.
  - Only the `--opt=value` form is accepted. Options may come before or after
    `FILE`, and a repeated option's last value wins.
- **stdout.** The report (format below).
- **stderr.** Not tested.
- **Exit codes.**
  - `0`: success, even if some lines are malformed.
  - `1`: `FILE` cannot be read. Nothing printed.
  - `2`: usage error: an unknown option, an invalid `--sort` key, an invalid
    `--min-count`, or more than one `FILE`. Nothing printed.

## Log line format

Lines are separated by `\n`, the last line may lack `\n`, and a trailing `\r`
is removed. Split each line on runs of spaces and/or tabs, ignoring leading
and trailing whitespace. A valid line has **exactly 5 fields**:

```
<timestamp> <method> <path> <status> <latency_ms>
```

| Field | Must match |
|---|---|
| timestamp | `[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z` (format only, no calendar check) |
| method | `[A-Z]{1,10}` |
| path | starts with `/`, then any non-whitespace characters |
| status | `[1-5][0-9][0-9]` (100-599) |
| latency_ms | `[0-9]{1,9}` (leading zeros allowed, value 0-999999999) |

- Any other non-empty line is **malformed**.
- Empty or whitespace-only lines are ignored. They are neither valid nor
  malformed.

## Rules

1. **Normalization.**
   - Remove everything from the first `?` in the path onward.
   - Split the rest on `/` and replace every segment that consists only of
     digits (one or more) with `:id`. Then rejoin.
   - Empty segments are kept: `/a//1/` becomes `/a//:id/`, and `/` stays `/`.
   - The endpoint **name** is `<method> <normalized path>`, with one space.
2. **Errors.** A request is an error if its status is 500-599.
3. **Error percentage.** `err_pct` is `errors × 100 / count`, rounded half-up
   to one decimal. Compute it in integers: `t = floor((2000·errors + count) /
   (2·count))`, and print `t div 10`, `.`, `t mod 10`. For example: 1/3 gives
   `33.3`, 2/3 gives `66.7`, 1/16 gives `6.3`, 0/5 gives `0.0`, 4/4 gives
   `100.0`.
4. **Percentiles.** Use the nearest-rank method. Sort the endpoint's latencies
   ascending as `v[1..n]`. Then `pP = v[k]` with `k = ceil(P·n / 100)`
   (computed as `floor((P·n + 99) / 100)`). `max` is `v[n]`.
5. **Sorting.**
   - `count`: count descending, then name ascending (byte order).
   - `p99`: p99 descending, then name ascending.
   - `name`: name ascending.
6. **min-count.** Endpoints with `count < N` are not printed, but their lines
   still count in `total`.
7. **Limits.** At most 1000000 lines.

## Output format

One line per printed endpoint:

```
<name> count=<c> errors=<e> err_pct=<x.y> p50=<a> p90=<b> p99=<d> max=<m>
```

followed by a final line:

```
total=<number of valid lines> malformed=<number of malformed lines>
```

- Fields are separated by single spaces, and every line ends with `\n`.
- All numbers are plain decimal integers without leading zeros (latencies are
  printed as numbers, so `007` prints as `7`), except `err_pct`.

## Examples

Every line shown ends with `\n`. The examples use this `access.log`:

```
2026-03-01T10:00:00Z GET /users/42 200 30
2026-03-01T10:00:01Z GET /users/7?full=1 200 10
2026-03-01T10:00:02Z GET /users/7 503 90
2026-03-01T10:00:03Z POST /users 201 50
garbage line
2026-03-01T10:00:04Z GET /health 200 1
2026-03-01T10:00:05Z GET /users/x1 200 5
2026-03-01T10:00:06Z DELETE /users/42 204 abc
```

### Example 1: default sort

cmd: `latency access.log`

stdout:
```
GET /users/:id count=3 errors=1 err_pct=33.3 p50=30 p90=90 p99=90 max=90
GET /health count=1 errors=0 err_pct=0.0 p50=1 p90=1 p99=1 max=1
GET /users/x1 count=1 errors=0 err_pct=0.0 p50=5 p90=5 p99=5 max=5
POST /users count=1 errors=0 err_pct=0.0 p50=50 p90=50 p99=50 max=50
total=6 malformed=2
```
exit: `0`

### Example 2: sort by p99

cmd: `latency --sort=p99 access.log`

stdout:
```
GET /users/:id count=3 errors=1 err_pct=33.3 p50=30 p90=90 p99=90 max=90
POST /users count=1 errors=0 err_pct=0.0 p50=50 p90=50 p99=50 max=50
GET /users/x1 count=1 errors=0 err_pct=0.0 p50=5 p90=5 p99=5 max=5
GET /health count=1 errors=0 err_pct=0.0 p50=1 p90=1 p99=1 max=1
total=6 malformed=2
```
exit: `0`

### Example 3: min-count, stdin

cmd: `latency --min-count=2`

stdin: the contents of `access.log`.

stdout:
```
GET /users/:id count=3 errors=1 err_pct=33.3 p50=30 p90=90 p99=90 max=90
total=6 malformed=2
```
exit: `0`

### Example 4: percentiles over 10 values, empty segments

cmd: `latency`

stdin:
```
2026-03-01T00:00:00Z GET //a/ 200 10
2026-03-01T00:00:00Z GET //a/ 200 20
2026-03-01T00:00:00Z GET //a/ 200 30
2026-03-01T00:00:00Z GET //a/ 200 40
2026-03-01T00:00:00Z GET //a/ 200 50
2026-03-01T00:00:00Z GET //a/ 200 60
2026-03-01T00:00:00Z GET //a/ 200 70
2026-03-01T00:00:00Z GET //a/ 200 80
2026-03-01T00:00:00Z GET //a/ 599 90
2026-03-01T00:00:00Z GET //a/ 200 0100
```
stdout:
```
GET //a/ count=10 errors=1 err_pct=10.0 p50=50 p90=90 p99=100 max=100
total=10 malformed=0
```
exit: `0`

### Example 5: empty input and usage errors

- cmd: `latency` with empty stdin gives stdout `total=0 malformed=0` and
  exit `0`.
- cmd: `latency --sort=speed` gives stdout (empty) and exit `2`.
- cmd: `latency --min-count=0` gives stdout (empty) and exit `2`.
- cmd: `latency nope.log` (the file does not exist) gives stdout (empty) and
  exit `1`.

## Not required

- Calendar validation of timestamps, and time-window filtering.
- URL decoding, and normalizing anything other than all-digit segments.
- `--sort KEY` (the space-separated form), `--help`.
- Any particular stderr wording.
