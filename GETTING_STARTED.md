# Getting Started with Noema

This is the fastest path back into the project after time away.

## Run the suite

```bash
cd projects/noema
python3 -m noema test
```

Expect 19 tests passing in well under a second.

## Run the examples

```bash
python3 -m noema run examples/greet.nm
python3 -m noema run examples/sort.nm
python3 -m noema run examples/classify.nm
```

## Look at the canonical form

```bash
python3 -m noema canonical examples/greet.nm
```

This prints the JSON hypergraph. That JSON is the truth; the `.nm` file is one
projection of it.

## Where things live

| You want to...                        | Go to                                   |
|---------------------------------------|-----------------------------------------|
| Understand design principles          | `README.md`                             |
| Understand the hypergraph schema      | `docs/CANONICAL.md`                     |
| See the surface syntax reference      | `docs/LANGUAGE.md`                      |
| See what's coming next                | `docs/ROADMAP.md`                       |
| See what shipped in v0                | `CHANGELOG.md`                          |
| Read core types                       | `noema/core/types.py`                   |
| Read the interpreter                  | `noema/runtime/interpreter.py`          |
| Read effect enforcement               | `noema/runtime/primitives.py`           |
| Add a test                            | `tests/test_*.py`                       |
| Read about personas                   | `.kiro/steering/personas.md`            |
| Read the v0 status                    | `dispatches/2026-05-10-v0-snapshot.*`   |

## Common next tasks

- **Add a primitive.** Edit `noema/runtime/primitives.py`, register a new
  `reg.register(...)` call with its effect label, then add a test that uses
  it in a `.nm` fixture.
- **Add a language construct.** Add the node type to `noema/core/types.py`,
  handle it in the parser (`noema/parser/`), project it in
  `noema/projection/canonical.py`, evaluate it in
  `noema/runtime/interpreter.py`, and write a round-trip test.
- **Publish a new dispatch.** Quill produces a `.readout.md`, Glyph produces
  a `.yaml` with the same `subject`. Both land in `dispatches/`.

## Gotchas the v0 will ask you about

- Every `def` must declare an `intent`. The parser rejects definitions
  without one. This is intentional.
- Every `def` must declare its `effects`. If a candidate body calls a
  primitive outside that set, the interpreter refuses to run it.
- `believe` blocks require an `else => ...` arm. Partial dispatch is not
  allowed; use `else => bottom` to refuse explicitly.
- `bottom` propagating to a top-level `run` raises `RefusalError`. That is
  not a bug; it is the language telling you no caller chose to handle the
  refusal.
