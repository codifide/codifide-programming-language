# Noema — Tutorial

A walk-through that takes you from a fresh clone to a symbol stored by
content hash, an index published, and a consumer module running against
that index. About thirty minutes end-to-end.

Every command shown here has been run. Every snippet is either copied from
`examples/` or small enough to verify by hand.

## Prerequisites

- Python 3.10 or newer.
- A Unix-like shell.
- Optional: Rust toolchain (`cargo`) for the conformance tests.

No pip installs. Noema's runtime has no third-party dependencies.

Verify the suite passes:

```bash
python3 -m noema test
```

You should see `Ran 68 tests` and `OK`. If the Rust toolchain is absent,
two conformance tests skip with a clear reason and the remainder pass.

## 1. Your first Noema program

The simplest Noema program that does something visible is `examples/greet.nm`:

```noema
module greet_example

def greet
  intent "welcome a known user by name, neutrally"
  sig    (name: String) -> String
  effects {io.stdout, clock.read}
  pre    ne(name, "")
  post   contains(result, name)
  cand
    now <- clock.now
    io.say("Hello, " ++ name ++ ", it's " ++ now.hm)

def main
  intent "entry point"
  sig    () -> String
  effects {io.stdout, clock.read}
  cand
    greet("Ada")
```

Run it:

```bash
python3 -m noema run examples/greet.nm
```

You should see something like:

```
Hello, Ada, it's 15:56
```

Three things here are worth knowing:

- **`intent` is required.** Every definition declares why it exists. The
  parser rejects a `def` without one.
- **`effects` is a contract.** `greet` is allowed to write to stdout and
  read the clock. If its body called anything else — say `net.get` — the
  module would fail to load.
- **`post` is machine-checked.** After `greet` returns, the interpreter
  evaluates `contains(result, name)`. If that is false, you get a
  `ContractViolation`, not a silent wrong answer.

The interesting idea: contracts, effects, and intent are not documentation.
They are the signature of the function, and the interpreter enforces them.

## 2. Contracts and effects

To see what the effect check actually catches, try adding a forbidden
effect. Save this as `/tmp/bad.nm`:

```noema
module bad_example

def shout
  intent "claim to be pure, actually write"
  sig    (name: String) -> String
  effects {}
  cand
    io.say("surprise")
```

Run it:

```bash
python3 -m noema run /tmp/bad.nm
```

The interpreter rejects the program before any body runs:

```
noema: 'shout' performed effect 'io.stdout' which is not in its declared set {}
```

Now try the transitive case. Save this as `/tmp/launder.nm`:

```noema
module launder_example

def loud
  intent "actually noisy"
  sig    () -> String
  effects {io.stdout}
  cand
    io.say("hi")

def quiet
  intent "claim to be silent, call a noisy callee"
  sig    () -> String
  effects {}
  cand
    loud()
```

```bash
python3 -m noema run /tmp/launder.nm
```

Same kind of rejection, this time at the module-load static pass:

```
noema: 'quiet' performed effect 'io.stdout' which is not in its declared set {}
```

The interesting idea: effects are not checked at call sites alone. A pure
function cannot call an effectful one and launder the effect. This property
is what makes the signature's effect declaration meaningful.

Contracts run under the same discipline, but inverted: pre, post, and
guard expressions evaluate with an empty effect budget regardless of what
the surrounding signature allows. A postcondition cannot call `io.say`.
Contracts describe state; they do not modify it.

Clean up:

```bash
rm /tmp/bad.nm /tmp/launder.nm
```

## 3. Belief dispatch and refusal

Values in Noema carry confidence. A primitive that produces uncertain
output — a classifier, a model call — returns a `Belief`, which pairs a
value with a confidence score. `believe` dispatches on that score:

```noema
def classify
  intent "label an image, refuse rather than guess"
  sig    (img: Image) -> Label
  effects {model.vision}
  cand
    label <- vision.classify(img)
    believe label
      ge(conf(label), 0.85) => label
      ge(conf(label), 0.60) => escalate(img, label)
      else                  => bottom
```

Run it:

```bash
python3 -m noema run examples/classify.nm
```

Output:

```
cat
```

The `test_image()` primitive returns an image tagged `"cat"` with
confidence `0.92`, which satisfies the first arm. Try editing
`examples/classify.nm` (or a copy) to change the confidence in the
`host_image("cat", 0.92)` line to `0.5`. Now both arms fail and the
function returns `bottom`. Since nothing handles the refusal, you get:

```
noema: 'main' returned ⊥ (refusal) and no caller chose to handle it. ...
```

The interesting idea: refusal is first-class. `bottom` is a value that
means "the function chose to abstain." A caller handles it in a `believe`
arm or at a call site; if it escapes to the top, the runtime raises a
typed `RefusalError`, never a silent zero. The `else => ...` arm on every
`believe` block is required so refusal is always an explicit choice, not
an accident.

## 4. Storing a symbol by content hash

Look at the canonical form of a program:

```bash
python3 -m noema canonical examples/greet.nm | head -20
```

This prints the JSON hypergraph. That JSON is the truth; the `.nm` file
is one projection of it. The byte form of that JSON is what gets hashed.

Store every symbol in `greet.nm`:

```bash
python3 -m noema store put examples/greet.nm
```

Output (your hashes will match; they are deterministic):

```
sha256:5abe9a7b3cd284bc27b652cf71a55b70dbda6b4c0de3bb84cfe98d29b7fd995b	greet
sha256:76d89b68148a414676f1c0597ecd6a4df7e872552209e67835abed8fc4c95bd0	main
```

The store defaults to `~/.noema/store`. Override with `--store <path>` or
`$NOEMA_STORE` if you want a scratch location.

List what the store holds:

```bash
python3 -m noema store list
```

Fetch a symbol by its identity:

```bash
python3 -m noema store get sha256:5abe9a7b3cd284bc27b652cf71a55b70dbda6b4c0de3bb84cfe98d29b7fd995b
```

The printed JSON is the exact canonical form that was hashed. Re-running
`store put` on the same module is a no-op; storing the same identity twice
leaves one object on disk.

The interesting idea: content addressing means a symbol's identity is a
property of its bytes. Two agents naming the same hash see the same
bytes, the same contracts, the same intent. The hash is the specification.
Storing is idempotent, reads are hash-verified, and corrupted bytes raise
an integrity error rather than returning a value.

## 5. Importing a symbol by hash

Publish a small library. Put this in `/tmp/lib.nm`:

```noema
module greet_lib

def hello
  intent "format a hello"
  sig    (name: String) -> String
  effects {}
  cand
    "Hello, " ++ name
```

Store it and note the identity:

```bash
python3 -m noema store put /tmp/lib.nm
```

Output:

```
sha256:88e8d6d28dd0d98dc86002b6ab71d16b616bb2e441f155e955797a34f23be403	hello
```

Now write a consumer. Put this in `/tmp/consumer.nm`, substituting the
identity you just received:

```noema
module consumer

import hello = sha256:88e8d6d28dd0d98dc86002b6ab71d16b616bb2e441f155e955797a34f23be403

def main
  intent "use a library symbol by content identity"
  sig    () -> String
  effects {}
  cand
    hello("Ada")
```

Run it:

```bash
python3 -m noema run /tmp/consumer.nm
```

Output:

```
Hello, Ada
```

The interpreter resolved the identity through the store, fetched the
canonical bytes, rehashed them, reconstructed a `Definition`, and called
`hello` with `"Ada"`. From the call site, there is no difference between
an imported symbol and a local `def`. The effect check ran on the
imported symbol exactly as it would have run on a local one.

Try tampering. Find the file on disk (the store's layout is Git-style
sharded):

```bash
find ~/.noema/store -name '*.json' | head
```

Edit one of them to change a character inside the JSON (a value, a
string — anything). Run your consumer again:

```bash
python3 -m noema run /tmp/consumer.nm
```

You get:

```
noema: cannot resolve import 'hello' = sha256:...: integrity check failed: expected '...', got '...'
```

The store rehashes bytes before returning them. Corrupted or tampered
data never makes it to the runtime.

The interesting idea: the content hash is not just for deduplication. It
is an integrity boundary. An adversary who wants to substitute a
more-effectful body has to mint a new identity, which every consumer
would have to actively update to. The effect set is part of the hash.

Restore the original by running `python3 -m noema store put /tmp/lib.nm`
again — idempotent writes re-put the correct bytes.

## 6. Publishing an index and using it

Importing a library with five functions would mean five `import` lines,
each with its own hash. An *index* is a module whose imports table is its
export map. It lets a consumer reference many symbols through a single
identity.

Mint an index over the `hello` symbol you just stored:

```bash
python3 -m noema store index --name greet_index \
    hello=sha256:88e8d6d28dd0d98dc86002b6ab71d16b616bb2e441f155e955797a34f23be403
```

Output:

```
sha256:89653ceea414125c8c52a1113f1fb85ff0c206c71f38ecb7896fefdff63dcf46	greet_index
```

That is the index's identity. It is content-addressed like any other
module — same entries produce the same hash, renaming the module produces
a different hash, entry order does not affect the hash.

Now write a consumer that pulls through the index. Replace `/tmp/consumer.nm`:

```noema
module consumer_via_index

from sha256:89653ceea414125c8c52a1113f1fb85ff0c206c71f38ecb7896fefdff63dcf46 import hello

def main
  intent "use a library symbol resolved through an index"
  sig    () -> String
  effects {}
  cand
    hello("Ada")
```

Run it:

```bash
python3 -m noema run /tmp/consumer.nm
```

Output:

```
Hello, Ada
```

The parser opened the store, fetched the index's canonical JSON, read its
imports table, and bound `hello` to the per-symbol identity the index
assigned it. From there the runtime behaves exactly as it did in §5 — the
index is not a concept the runtime knows about.

Clean up:

```bash
rm /tmp/lib.nm /tmp/consumer.nm
```

The interesting idea: indices separate discovery from identity without
giving up content addressing. One agent publishes symbols and an index
that names them; another agent needs only the index's hash to reach
every named symbol. No versioning, no lockfiles, no central registry.
The security properties still hold: a consumer that declares `effects {}`
cannot import an effectful symbol through an index, because the effect
set is part of the symbol's identity and the transitive check runs at
module load.

## Where to go next

- `docs/LANGUAGE.md` — the surface-syntax reference in one place.
- `docs/CANONICAL.md` — the specification an independent implementer
  follows. Written so the Rust crate agrees with Python byte-for-byte.
- `docs/ARCHITECTURE.md` — how the code is organized, for contributors.
- `docs/ROADMAP.md` — what is planned next.
- `dispatches/` — paired Quill readouts and Glyph dispatches for every
  milestone so far. Read them in filename order to see how the language
  grew in one session.
