# Task 08: pubsub (topic-based message broker)

## Goal

Write an in-memory publish/subscribe broker driven by a line protocol on
stdin and stdout. Clients subscribe to topic patterns with single-level
(`*`) and multi-level (`#`) wildcards. A published message is copied into
the mailbox of every client with at least one matching subscription. Each
mailbox holds at most 3 messages and drops the oldest one when full. Clients
fetch their messages with `POLL`. Each command produces exactly one response
line.

## Interface

```
pubsub
```

- **Arguments.** None. Any argument is a usage error: message on stderr,
  exit `2`, stdin not read, stdout empty.
- **stdin.** One command per line. A line ends with `\n` (a trailing `\r` is
  removed), and the last line may lack `\n`.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit codes.** `0` at end of input, `2` usage error.

## Commands

Tokens are separated by exactly one space. There are no leading or trailing
spaces, and command names are uppercase.

```
SUB <client> <pattern>
UNSUB <client> <pattern>
PUB <topic> <text>
POLL <client> <max>
STATS <client>
```

- `<client>` matches `[a-z][a-z0-9]{0,15}`.
- `<topic>` is 1 to 8 **segments** joined by `.`, each segment matching
  `[a-z0-9]{1,16}`. Examples: `news`, `news.sport.uk`.
- `<pattern>` is 1 to 8 segments joined by `.`. Each segment is either a
  normal segment (`[a-z0-9]{1,16}`), `*`, or `#`; `#` is allowed only as the
  **last** segment. Examples: `news.*`, `news.#`, `#`, `*.#`.
- `<text>` matches `[A-Za-z0-9_.!?-]{1,32}` (no spaces).
- `<max>` matches `[1-9][0-9]{0,2}` (1 to 999).

Any line that is not exactly one of these forms (bad token, wrong token
count, extra spaces, lower-case command, empty line) gets `ERR bad command`
and changes nothing.

## Rules

1. **Clients.** Every client name implicitly exists, with no subscriptions,
   an empty mailbox and a drop count of 0. A client's mailbox and drop count
   are kept when it unsubscribes.
2. **SUB.** If the client already has a subscription with exactly the same
   pattern string: `ERR already subscribed`. Otherwise add it: `OK`.
3. **UNSUB.** If the client has a subscription with exactly this pattern
   string, remove it: `OK`. Otherwise `ERR not subscribed`. (Patterns are
   compared as strings, not by what they match: `UNSUB c a.*` does not
   remove `a.#`.)
4. **Matching.** Let the pattern have segments p1..pk and the topic t1..tn.
   - If pk is `#`: the pattern matches if n ≥ k − 1 and p1..p(k−1) match
     t1..t(k−1) segment by segment. So `a.#` matches `a`, `a.b` and `a.b.c`,
     and `#` matches every topic.
   - Otherwise: the pattern matches if n = k and every pi matches ti.
   - A segment `*` matches any one topic segment; a normal segment matches
     only an identical topic segment.
5. **PUB.** For every client that has **at least one** subscription matching
   the topic, the message `<topic>=<text>` is appended to the end of that
   client's mailbox, **once** even if several of its subscriptions match.
   If the mailbox already holds 3 messages, its oldest message is first
   removed and the client's drop count increases by 1. The response is
   `DELIVERED <n>`, where n is the number of clients that received the
   message (0 is fine).
6. **POLL.** Remove the k = min(max, mailbox size) oldest messages from the
   client's mailbox and respond `MSGS <k>` followed by those messages,
   oldest first, each preceded by one space. With k = 0 the response is just
   `MSGS 0`.
7. **STATS.** `subs=<s> queued=<q> dropped=<d>`: the client's current number
   of subscriptions, mailbox size and drop count.
8. **Limits.** At most 100000 commands and 1000 distinct clients.

## Examples

Each line shown ends with `\n`. For every example, cmd is `pubsub` and exit
is `0`, except where noted.

### Example 1: wildcards and a full mailbox

stdin:
```
SUB ann news.sport
SUB bob news.*
SUB cy news.#
PUB news.sport Goal!
PUB news.weather Rain
PUB news Extra
PUB news.sport.uk Win
PUB other Hi
POLL ann 10
POLL bob 1
POLL bob 5
POLL cy 10
POLL cy 10
```
stdout:
```
OK
OK
OK
DELIVERED 3
DELIVERED 2
DELIVERED 1
DELIVERED 1
DELIVERED 0
MSGS 1 news.sport=Goal!
MSGS 1 news.sport=Goal!
MSGS 1 news.weather=Rain
MSGS 3 news.weather=Rain news=Extra news.sport.uk=Win
MSGS 0
```

(`cy` received 4 messages; the 4th pushed out `news.sport=Goal!`.)

### Example 2: overlapping subscriptions, UNSUB and STATS

stdin:
```
SUB dee a.#
SUB dee a.b
SUB dee a.#
PUB a.b m1
PUB a.c m2
PUB a m3
PUB a.b.c m4
STATS dee
POLL dee 2
STATS dee
UNSUB dee a.#
UNSUB dee a.#
PUB a.c m5
PUB a.b m6
STATS dee
POLL dee 9
STATS zed
POLL zed 1
```
stdout:
```
OK
OK
ERR already subscribed
DELIVERED 1
DELIVERED 1
DELIVERED 1
DELIVERED 1
subs=2 queued=3 dropped=1
MSGS 2 a.c=m2 a=m3
subs=2 queued=1 dropped=1
OK
ERR not subscribed
DELIVERED 0
DELIVERED 1
subs=1 queued=2 dropped=1
MSGS 2 a.b.c=m4 a.b=m6
subs=0 queued=0 dropped=0
MSGS 0
```

(`PUB a.b m1` matches both of dee's patterns but is delivered once.)

### Example 3: malformed commands

stdin (the 12th line is empty):
```
SUB Ann x
SUB ann x.#.y
SUB ann #
SUB ann *.#
PUB a.* m
PUB a hello world
PUB a.b.c.d.e.f.g.h.i m
POLL ann 0
POLL ann 1000
sub ann x
STATS

PUB a
PUB q x,y
SUB ann a..b
```
stdout:
```
ERR bad command
ERR bad command
OK
OK
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
```

### Example 4: usage error

cmd: `pubsub 3`

stdout: (empty)

exit: `2`

## Not required

- Persistence, acknowledgements or redelivery.
- Retained messages or messages that arrived before a subscription.
- Message texts with spaces.
- Any particular stderr wording.
