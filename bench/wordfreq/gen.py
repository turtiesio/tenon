# Deterministic input: ~16 MB of Zipf-ish words.
import random
r = random.Random(42)
vocab = ["w%d%s" % (i, "xyz"[i % 3] * (i % 5)) for i in range(50000)]
weights = [1.0 / (i + 1) for i in range(len(vocab))]
words = r.choices(vocab, weights=weights, k=2_000_000)
lines = [" ".join(words[i:i + 12]).capitalize() for i in range(0, len(words), 12)]
open("input.txt", "w").write("\n".join(lines) + "\n")
