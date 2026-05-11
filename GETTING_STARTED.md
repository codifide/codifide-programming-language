# Getting Started with Codifide

This is the fastest path back into the project after time away.

## Run the suite

```bash
python3 -m codifide test
```

Expect 68 tests passing in well under a second. Two of those (Rust
conformance) skip cleanly when `cargo` is not available and pass when it
is.

Rust canonical crate:

```bash
cargo test --release -p codifide-canonical
```

Expect 6 tests passing.

## Run the examples

```bash
python3 -m codifide run examples/greet.cod
python3 -m codifide run examples/sort.cod
python3 -m codifide run examples/classify.cod
python3 -m codifide run examples/unicode.cod
```

`examples/imports_demo.cod` has a placeholder identity by design and is not
runnable as written; see `docs/TUTORIAL.md §5` for a real import walk-through.

## Look at the canonical form

```bash
python3 -m codifide canonical examples/greet.cod
```

This prints the JSON hypergraph. That JSON is the truth; the `.cod` file is
one projection of it.

## Try the full story

Store, index, import, consume — the end-to-end path agents actually take:

```bash
# 1. Run a program.
python3 -m codifide run examples/greet.cod

# 2. Store every symbol from a module by content hash.
python3 -m codifide store put examples/greet.cod

# 3. List what's in the store.
python3 -m codifide store list

# 4. Mint an index over some of those symbols. Substitute the hashes
#    you just received.
python3 -m codifide store index --name greet_index \
    greet=sha256:<hash-from-step-2>

# 5. Consume the index from a new module. Write this to /tmp/consumer.cod
#    with the index hash from step 4:
#
#      module consumer
#      from sha256:<index-hash> import greet
#      def main
#        intent "use a library symbol through an index"
#        sig    () -> String
#        effects {io.stdout, clock.read}
#        cand
#          greet("Ada")
#
python3 -m codifide run /tmp/consumer.cod
```

The full walk-through, with explanations and the security properties at
each step, is in `docs/TUTORIAL.md`.

## Where things live

| You want to...                          | Go to                                   |
|-----------------------------------------|-----------------------------------------|
| Understand design principles            | `README.md`                             |
| Walk through the language               | `docs/TUTORIAL.md`                      |
| See the surface-syntax reference        | `docs/LANGUAGE.md`                      |
| Understand the canonical-form spec      | `docs/CANONICAL.md`                     |
| Read how the code is organized          | `docs/ARCHITECTURE.md`                  |
| Read about the Rust crate               | `docs/RUST.md`                          |
| See what's coming next                  | `docs/ROADMAP.md`                       |
| See what shipped                        | `CHANGELOG.md`                          |
| Read core types                         | `codifide/core/types.py`                   |
| Read the interpreter                    | `codifide/runtime/interpreter.py`          |
| Read effect enforcement                 | `codifide/runtime/interpreter.py` (`_check_transitive_effects`) |
| Read the primitive registry             | `codifide/runtime/primitives.py`           |
| Read the symbol store                   | `codifide/store/symbol_store.py`           |
| Read the Rust canonical implementation  | `crates/codifide-canonical/src/`           |
| Add a test                              | `tests/test_*.py`                       |
| Read about personas                     | `.kiro/steering/personas.md`            |
| Read the dispatches in order            | `dispatches/` (filename-sorted)         |

## Common next tasks

- **Store and consume a symbol.** Walk through `docs/TUTORIAL.md §4-§6`.
  That is the story content addressing exists to tell.
- **Add a primitive.** Edit `codifide/runtime/primitives.py`, register a new
  `reg.register(...)` call with its effect label and return type, then add
  a test that uses it in a `.cod` fixture.
- **Add a language construct.** Add the node type to
  `codifide/core/types.py`, handle it in the parser (`codifide/parser/`), project
  it in `codifide/projection/canonical.py`, evaluate it in
  `codifide/runtime/interpreter.py`, mirror it in the Rust crate, and write a
  round-trip test plus a conformance test.
- **Publish a new dispatch.** Quill produces a `.readout.md`; Glyph
  produces a `.yaml` with the same `subject`. Both land in `dispatches/`.
  Sable runs at gate transitions and files `*-audit.md`.

## Gotchas

- Every `def` must declare an `intent`. The parser rejects definitions
  without one. This is intentional.
- Every `def` must declare its `effects`. If a candidate body calls a
  primitive outside that set, or calls another user function whose
  declared effects exceed this function's, the module is rejected at
  load time.
- `believe` blocks require an `else => ...` arm. Partial dispatch is not
  allowed; use `else => bottom` to refuse explicitly.
- `bottom` propagating to a top-level `run` raises `RefusalError`. That is
  not a bug; it is the language telling you no caller chose to handle the
  refusal.
- Contracts (pre, post, guards) run with an empty effect budget. A
  postcondition cannot call an effectful primitive even if the
  surrounding function is allowed to.
- The interpreter bounds its own call depth at 64 by default. Deep
  recursion raises a typed `RecursionLimitError`.
- Symbol-store identities are `sha256:` followed by 64 lowercase hex
  characters. Anything else is a `ParseError` or `StoreError`.
- Imports require a store. `python3 -m codifide run` opens one on demand;
  pass `--store <path>` or set `$CODIFIDE_STORE` to override the default
  `~/.codifide/store`.
