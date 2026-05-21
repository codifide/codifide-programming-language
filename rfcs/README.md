# Codifide RFCs

This directory holds Request-for-Comments documents — proposals that are
not yet decided. RFCs are the home for ideas that need discussion, evidence,
or implementation work before they can be promoted to specification.

## What belongs here

- Proposed language changes that haven't been adopted
- Open semantic questions the spec doesn't yet answer
- Design sketches for future versions
- External review material that needs evaluation against CPL's actual surface

## What does not belong here

- Specification of current behavior — that lives in `docs/CANONICAL.md`,
  `docs/LANGUAGE.md`, and `docs/CAPABILITY.md`
- Anything ratified as constitutional — those are spec-level documents
  that go through the governance process in `GOVERNANCE.md`

## RFC status values

Every RFC carries a `Status:` field at the top. Valid values:

- **Draft** — the RFC is proposed but not reviewed
- **Open** — the RFC is under active discussion
- **Accepted** — the RFC has been ratified and the work is scheduled
- **Rejected** — the RFC was considered and declined (with reason)
- **Withdrawn** — the author pulled the proposal
- **Superseded by RFC NNNN** — replaced by another RFC

## RFC numbering

RFCs are numbered sequentially as they are filed. Numbers do not
indicate priority. Numbers are not reused; a withdrawn RFC keeps its
number forever.

## Promotion path

For an RFC to move into the spec:

1. The RFC must reach `Status: Accepted`
2. A paired Quill readout + Glyph dispatch records the decision
3. A Sable audit covers the soundness implications (if security-adjacent)
4. The spec change is made; the RFC is marked `Status: Accepted` with a
   pointer to the spec section that absorbed it
5. Douglas approves on the commit

This matches the spec-change process in `GOVERNANCE.md`.

## Current RFCs

| Number | Title | Status |
|---|---|---|
| 0001 | Formal Semantics Gaps in CPL | Open |
| 0002 | Proposed Semantic Invariants | Draft |
| 0003 | Epistemic State Model | Draft |

