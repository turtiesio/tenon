# Task 08: locks (shared/exclusive lock manager service)

## Goal

Write a lock manager driven by a line protocol on stdin and stdout. Clients
acquire shared (`S`) or exclusive (`X`) locks on named resources. A request
that cannot be granted at once waits in a first-come-first-served queue for
that resource; when locks are released, waiting requests are granted from
the front of the queue as far as they are compatible. A client can also be
dropped, which cancels everything it is waiting for and releases everything
it holds. Each response reports which waiting requests were granted as a
result.

## Interface

```
locks
```

- **Arguments.** None. Any argument is a usage error: print a message to
  stderr, print **nothing** on stdout, do not read stdin, and exit `2`.
- **stdin.** One command per line, ASCII. Lines are split on `\n`. If the
  input ends with `\n`, there is no extra empty line after it. A final line
  without `\n` is still a line. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. Flush stdout after every response.
- **Exit codes.** `0` at end of input, `2` usage error.

## Rules

1. **State.** For each resource there is a set of **holders** (each a client
   with a mode, `S` or `X`) and a FIFO **queue** of waiting requests (each a
   client with a mode). A client holds at most one lock on a resource and
   has at most one waiting request on it, never both at once. A client may
   hold or wait on any number of different resources.
2. **Compatibility.** A request with mode m is **compatible** with the
   current holders of a resource if there are no holders, or if m is `S`
   and every holder holds `S`. (`X` is compatible only with no holders.)
3. **New requests.** A new `LOCK` request is granted at once only if the
   resource's queue is **empty** and the request is compatible with the
   holders. Otherwise it is appended to the end of the queue, even if it is
   compatible with the holders (no overtaking).
4. **Granting from the queue.** Whenever a resource loses a holder or a
   waiting request, it is **pumped**: while its queue is not empty and the
   request at the front is compatible with the current holders, that request
   is removed from the queue and granted (the client becomes a holder with
   that mode). Each such grant is reported as `<client>:<resource>:<mode>`.
5. **Upgrades** are not supported: a client that holds `S` and asks for `X`
   gets `ERR already held`.

## Commands

Command names are upper case. Tokens are separated by exactly one space,
with no leading or trailing spaces. `<client>` and `<res>` match
`[a-z0-9]{1,12}`; `<mode>` is `S` or `X`.

| Command | Response |
|---|---|
| `LOCK <client> <res> <mode>` | `GRANTED` if granted at once (rule 3), `WAITING` if queued. `ERR already held` if the client holds a lock on `<res>`; `ERR already waiting` if it has a waiting request on `<res>`. |
| `UNLOCK <client> <res>` | Release the client's lock on `<res>` and pump `<res>`. The response is `OK` followed by ` <grant>` for each grant, in the order they were made. `ERR not held` if the client holds no lock on `<res>` (also when it is only waiting). |
| `DROP <client>` | First remove all of the client's waiting requests from all queues, then release all of its locks. Then pump every resource where something was removed or released, one resource at a time in byte order of the resource names. The response is `OK released=<a> cancelled=<b>` (a: locks released, b: waiting requests removed) followed by ` <grant>` for each grant, in the order they were made. A client with nothing gets `OK released=0 cancelled=0`. |
| `STATUS <res>` | `<res> holders=<h> queue=<q>`. `<h>` is the holders as `<client>:<mode>`, sorted by client name (byte order), joined with `,`. `<q>` is the queue from front to back, as `<client>:<mode>` joined with `,`. An empty list is written `-`. Any resource name may be asked about. |
| `HELD <client>` | The client's locks as `<res>:<mode>`, sorted by resource name (byte order), joined with `,`, or `-` if it holds none. |

**Errors.** A line that is not exactly one of the forms above (unknown or
lower-case command, wrong token count, malformed name or mode, extra
spaces, an empty line) gets `ERR bad command`. For `LOCK`, `ERR already
held` is checked before `ERR already waiting`. A command that gets an `ERR`
response changes nothing.

At most 10000 commands, 1000 clients and 1000 resources.

## Examples

Each line shown ends with `\n`. cmd is `locks` in every example.

### Example 1: shared, exclusive, and the queue

stdin:
```
LOCK ann db S
LOCK bob db S
LOCK cy db X
LOCK dee db S
LOCK ann db X
LOCK cy db S
STATUS db
UNLOCK ann db
UNLOCK bob db
STATUS db
UNLOCK cy db
UNLOCK cy db
HELD dee
STATUS db
STATUS nothing
```
stdout:
```
GRANTED
GRANTED
WAITING
WAITING
ERR already held
ERR already waiting
db holders=ann:S,bob:S queue=cy:X,dee:S
OK
OK cy:db:X
db holders=cy:X queue=dee:S
OK dee:db:S
ERR not held
db:S
db holders=dee:S queue=-
nothing holders=- queue=-
```
exit: `0`

(`dee` asks for `S` while only `S` locks are held, but waits behind `cy`
because the queue is not empty.)

### Example 2: dropping a client

stdin:
```
LOCK ann a X
LOCK ann b S
LOCK bob b S
LOCK cy b X
LOCK dee b S
LOCK cy a S
LOCK eve a S
HELD ann
DROP cy
STATUS b
DROP ann
STATUS a
STATUS b
HELD eve
DROP zed
```
stdout:
```
GRANTED
GRANTED
GRANTED
WAITING
WAITING
WAITING
WAITING
a:X,b:S
OK released=0 cancelled=2 dee:b:S
b holders=ann:S,bob:S,dee:S queue=-
OK released=2 cancelled=0 eve:a:S
a holders=eve:S queue=-
b holders=bob:S,dee:S queue=-
a:S
OK released=0 cancelled=0
```
exit: `0`

(Removing `cy`'s waiting `X` request from the front of `b`'s queue lets
`dee`'s `S` request through, although nothing was released on `b`.)

### Example 3: grants on several resources, malformed lines

stdin (there is an empty line after the 10th line; the line `STATUS r1`
ends with `\r\n`; the last line has no `\n`; the 10th line has two spaces
after `UNLOCK`):
```
LOCK p r2 X
LOCK p r1 X
LOCK q r2 S
LOCK s r2 S
LOCK q r1 X
LOCK t r1 S
DROP p
lock q r1 S
LOCK q r1 W
UNLOCK  q r1

LOCK Q r1 S
STATUS r1
UNLOCK t r1
UNLOCK q r1
```
stdout:
```
GRANTED
GRANTED
WAITING
WAITING
WAITING
WAITING
OK released=2 cancelled=0 q:r1:X q:r2:S s:r2:S
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
r1 holders=q:X queue=t:S
ERR not held
OK t:r1:S
```
exit: `0`

(`DROP p` pumps `r1` before `r2`. On `r1`, `q`'s `X` is granted and `t`'s
`S` must keep waiting.)

### Example 4: usage error

cmd: `locks -v` gives stdout (empty) and exit `2`.

## Not required

- Lock upgrades or downgrades, timeouts, or deadlock detection.
- Persisting state between runs.
- Any particular stderr wording.
