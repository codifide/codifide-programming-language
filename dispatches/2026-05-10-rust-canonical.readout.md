# A second implementation — what it took for Noema to stop being a Python project

*By Quill. 10 May 2026.*

A language is its specification, not its implementation. Until today, that
claim was aspirational for Noema. The reference Python implementation was
the de facto specification for anything the documents didn't pin down. The
canonical form, the grammar, the dispatch semantics — they all lived in
prose with Python as the tiebreaker.

Now there are two implementations. They agree.

## What shipped

A Rust crate at `crates/noema-canonical/` that implements Noema's canonical
form: the AST, the JSON projection, a deterministic canonical byte form,
and SHA-256 content addressing. A matching `canonical_bytes` and
`content_hash` on the Python side. A conformance test that parses every
example program with Python, emits canonical JSON, hands it to the Rust
binary, and asserts byte-for-byte equality against what Python would have
produced itself. Twenty-one tests pass.

`docs/CANONICAL.md` grew into a specification. Normalization is no longer
a vibe. The canonical byte form is defined. Content addressing is defined.
The effect algebra explicitly calls out the transitive subset rule that
the v0 Python interpreter still does not enforce — a gap now documented in
the spec rather than implied by the code.

## What is deliberately not built

The Rust crate does not include an interpreter. This is refusal, not
oversight. Runtime semantics are still changing. The transitive effect
check will alter behavior. Porting an interpreter whose semantics are in
motion doubles the cost of every semantics change. The canonical form is
the stablest surface to conform on first, and the one where cross-
implementation agreement matters most — because it is what gets hashed and
shipped between agents.

The Rust crate also does not parse `.nm` surface syntax. The Python
reference is authoritative for parsing in v0. Duplicating the parser
before canonical form is fully stable would invert the dependency.

## Why this matters

Two pieces of machinery now force the specification to be the truth.
First, the conformance test. If the Rust and Python implementations ever
disagree on canonical bytes, one of them is a bug against the spec — and
if both agree but the spec is silent, the spec is the bug. The pressure
runs the right way. Second, the content hash. Two implementations that
produce identical bytes produce identical hashes; two agents that share a
content-addressed store can now exchange symbols by identity rather than
by transport.

It does not mean Noema has arrived. It means Noema has stopped being a
Python library that thinks it is a language.

## What I'm not yet sure of

The conformance surface today is ASCII-clean examples. Non-ASCII string
literals and numeric edge cases may expose quiet disagreements between
`json.dumps` and `serde_json`. Neither has been tested. Whether `intent`
should be part of a symbol's identity hash is not yet written into the
spec — both implementations include it today, but by accident rather than
by decision. And the transitive effect check, when it lands, will tell us
whether the spec's description of the effect algebra holds up under a
real implementation or needs revision.
