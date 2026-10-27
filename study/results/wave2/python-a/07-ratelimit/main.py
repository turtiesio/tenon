#!/usr/bin/env python3
"""rl: token-bucket rate limiter driven by a line protocol on stdin."""

import re
import sys
from dataclasses import dataclass, field

NAME_RE = re.compile(r"[a-z0-9_.-]{1,32}")
TIME_RE = re.compile(r"[0-9]{1,15}")
COUNT_RE = re.compile(r"[0-9]{1,9}")

BAD_COMMAND = "ERR bad command"


@dataclass
class Bucket:
    tokens: int
    anchor: int


@dataclass
class Policy:
    capacity: int
    interval: int
    allowed: int = 0
    denied: int = 0
    buckets: dict = field(default_factory=dict)

    def refill(self, name, now):
        """Return the client's bucket, created if needed, refilled to `now`."""
        bucket = self.buckets.get(name)
        if bucket is None:
            bucket = self.buckets[name] = Bucket(self.capacity, now)
            return bucket
        if bucket.tokens == self.capacity:
            bucket.anchor = now
            return bucket
        k = (now - bucket.anchor) // self.interval
        bucket.tokens = min(self.capacity, bucket.tokens + k)
        if bucket.tokens == self.capacity:
            bucket.anchor = now
        else:
            bucket.anchor += k * self.interval
        return bucket


def is_count(text):
    """A capacity, interval or cost: 1..999999999."""
    return COUNT_RE.fullmatch(text) is not None and int(text) >= 1


class RateLimiter:
    def __init__(self):
        self.policies = {}
        self.clock = 0

    def execute(self, line):
        """Return the response line for one command."""
        parts = line.split(" ")
        command, args = parts[0], parts[1:]
        handler = {
            "POLICY": self.policy,
            "HIT": self.hit,
            "PEEK": self.peek,
            "RESET": self.reset,
            "STATS": self.stats,
        }.get(command)
        if handler is None:
            return BAD_COMMAND
        return handler(args)

    def advance(self, time):
        """Move the clock to `time`; return an error response if it goes backwards."""
        if time < self.clock:
            return "ERR time went backwards"
        self.clock = time
        return None

    def policy(self, args):
        if not (
            len(args) == 3
            and NAME_RE.fullmatch(args[0])
            and is_count(args[1])
            and is_count(args[2])
        ):
            return BAD_COMMAND
        if args[0] in self.policies:
            return "ERR policy exists"
        self.policies[args[0]] = Policy(int(args[1]), int(args[2]))
        return "OK"

    def hit(self, args):
        if len(args) not in (3, 4):
            return BAD_COMMAND
        time, policy_name, client = args[:3]
        cost_text = args[3] if len(args) == 4 else "1"
        if not (
            TIME_RE.fullmatch(time)
            and NAME_RE.fullmatch(policy_name)
            and NAME_RE.fullmatch(client)
            and is_count(cost_text)
        ):
            return BAD_COMMAND
        now, cost = int(time), int(cost_text)
        error = self.advance(now)
        if error:
            return error
        policy = self.policies.get(policy_name)
        if policy is None:
            return "ERR no such policy"
        if cost > policy.capacity:
            return "ERR cost exceeds capacity"

        bucket = policy.refill(client, now)
        if bucket.tokens >= cost:
            bucket.tokens -= cost
            policy.allowed += 1
            return f"ALLOW {bucket.tokens}"
        policy.denied += 1
        retry = bucket.anchor + (cost - bucket.tokens) * policy.interval - now
        return f"DENY {retry}"

    def peek(self, args):
        if not (
            len(args) == 3
            and TIME_RE.fullmatch(args[0])
            and NAME_RE.fullmatch(args[1])
            and NAME_RE.fullmatch(args[2])
        ):
            return BAD_COMMAND
        now = int(args[0])
        error = self.advance(now)
        if error:
            return error
        policy = self.policies.get(args[1])
        if policy is None:
            return "ERR no such policy"
        return f"TOKENS {policy.refill(args[2], now).tokens}"

    def reset(self, args):
        if not (len(args) == 2 and NAME_RE.fullmatch(args[0]) and NAME_RE.fullmatch(args[1])):
            return BAD_COMMAND
        policy = self.policies.get(args[0])
        if policy is None:
            return "ERR no such policy"
        if policy.buckets.pop(args[1], None) is None:
            return "ERR no such client"
        return "OK"

    def stats(self, args):
        if not (len(args) == 1 and NAME_RE.fullmatch(args[0])):
            return BAD_COMMAND
        policy = self.policies.get(args[0])
        if policy is None:
            return "ERR no such policy"
        return f"allowed={policy.allowed} denied={policy.denied} clients={len(policy.buckets)}"


def main(argv):
    if argv:
        print("usage: rl (takes no arguments)", file=sys.stderr)
        return 2
    limiter = RateLimiter()
    for raw in sys.stdin.buffer:
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(limiter.execute(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
