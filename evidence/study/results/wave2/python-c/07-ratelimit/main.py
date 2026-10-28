"""rl: deterministic token-bucket rate limiter driven by a line protocol."""
import re
import sys

NAME_RE = re.compile(r"[a-z0-9_.-]{1,32}")
TIME_RE = re.compile(r"[0-9]{1,15}")
COUNT_RE = re.compile(r"[0-9]{1,9}")


class CommandError(Exception):
    pass


BAD_COMMAND = CommandError("bad command")


def name(tok):
    if not NAME_RE.fullmatch(tok):
        raise BAD_COMMAND
    return tok


def time_value(tok):
    if not TIME_RE.fullmatch(tok):
        raise BAD_COMMAND
    return int(tok)


def positive(tok):
    if not COUNT_RE.fullmatch(tok) or int(tok) < 1:
        raise BAD_COMMAND
    return int(tok)


class Bucket:
    def __init__(self, tokens, anchor):
        self.tokens = tokens
        self.anchor = anchor


class Policy:
    def __init__(self, capacity, interval):
        self.capacity = capacity
        self.interval = interval
        self.buckets = {}
        self.allowed = 0
        self.denied = 0

    def refilled_bucket(self, client, now):
        bucket = self.buckets.get(client)
        if bucket is None:
            bucket = self.buckets[client] = Bucket(self.capacity, now)
        if bucket.tokens == self.capacity:
            bucket.anchor = now
        else:
            k = (now - bucket.anchor) // self.interval
            bucket.tokens = min(self.capacity, bucket.tokens + k)
            if bucket.tokens == self.capacity:
                bucket.anchor = now
            else:
                bucket.anchor += k * self.interval
        return bucket


class RateLimiter:
    def __init__(self):
        self.clock = 0
        self.policies = {}

    def handle(self, line):
        try:
            return self.dispatch(line.split(" "))
        except CommandError as e:
            return f"ERR {e}"

    def policy(self, policy_name):
        policy = self.policies.get(policy_name)
        if policy is None:
            raise CommandError("no such policy")
        return policy

    def advance_clock(self, now):
        if now < self.clock:
            raise CommandError("time went backwards")
        self.clock = now

    def dispatch(self, tokens):
        command, args = tokens[0], tokens[1:]
        if command == "POLICY" and len(args) == 3:
            policy_name, capacity, interval = name(args[0]), positive(args[1]), positive(args[2])
            if policy_name in self.policies:
                raise CommandError("policy exists")
            self.policies[policy_name] = Policy(capacity, interval)
            return "OK"
        if command == "HIT" and len(args) in (3, 4):
            now, policy_name, client = time_value(args[0]), name(args[1]), name(args[2])
            cost = positive(args[3]) if len(args) == 4 else 1
            self.advance_clock(now)
            policy = self.policy(policy_name)
            if cost > policy.capacity:
                raise CommandError("cost exceeds capacity")
            bucket = policy.refilled_bucket(client, now)
            if bucket.tokens >= cost:
                bucket.tokens -= cost
                policy.allowed += 1
                return f"ALLOW {bucket.tokens}"
            policy.denied += 1
            retry = bucket.anchor + (cost - bucket.tokens) * policy.interval - now
            return f"DENY {retry}"
        if command == "PEEK" and len(args) == 3:
            now, policy_name, client = time_value(args[0]), name(args[1]), name(args[2])
            self.advance_clock(now)
            bucket = self.policy(policy_name).refilled_bucket(client, now)
            return f"TOKENS {bucket.tokens}"
        if command == "RESET" and len(args) == 2:
            policy_name, client = name(args[0]), name(args[1])
            policy = self.policy(policy_name)
            if client not in policy.buckets:
                raise CommandError("no such client")
            del policy.buckets[client]
            return "OK"
        if command == "STATS" and len(args) == 1:
            policy = self.policy(name(args[0]))
            return f"allowed={policy.allowed} denied={policy.denied} clients={len(policy.buckets)}"
        raise BAD_COMMAND


def main(argv):
    if argv:
        print("usage: rl (takes no arguments)", file=sys.stderr)
        return 2
    limiter = RateLimiter()
    stdin, stdout = sys.stdin.buffer, sys.stdout
    while True:
        raw = stdin.readline()
        if not raw:
            break
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        stdout.write(limiter.handle(line) + "\n")
        stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
