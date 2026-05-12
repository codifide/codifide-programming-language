# Deferred items — taking first steps (2026-05-11)

User quoted the four items I deferred earlier and their reasons.
Interpreting that as "do the first step on each, not just note the
deferral." Each item had a specific blocker; the first step in each
case is the thing that removes the blocker — not the implementation
itself.

Governance stays intact: three of these produce **proposals that
require your approval before anything ships**. One (the CBOR re-audit)
does not need approval; audits are always in Sable's remit.

## Per-item first steps taken this session

### 1. Primary-hash migration JSON → CBOR.

*Blocker I named:* needs your go-ahead with a commit plan.

*First step taken:* write the migration proposal dispatch. Records
what changes, what breaks, the commit plan, the rollback story, and
what the post-migration world looks like. Paired Sable audit of the
proposal itself so the risks are on the record. **Nothing ships from
this.** After you read it, you approve (or modify) the plan, and a
future session executes it.

*Artifact:* `dispatches/2026-05-11-primary-hash-migration-proposal.{readout.md,yaml}`
plus `dispatches/2026-05-11-primary-hash-migration-audit.md`.

### 2. Store GC.

*Blocker I named:* needs a design dispatch before implementation.

*First step taken:* write the design dispatch. Answers the three
open questions I flagged (root-set semantics, dry-run discipline,
how GC participates in the three-property store contract), proposes
a specific design, and lists the follow-on implementation tasks.
**Nothing ships from this either.**

*Artifact:* `dispatches/2026-05-11-store-gc-design.{readout.md,yaml}`.

### 3. Cost-based candidate dispatch.

*Blocker I named:* spec amendment per governance.

*First step taken:* write the spec-amendment proposal dispatch with
Sable audit. Describes the grammar change, the canonical-form
extension, the dispatcher semantics, the compatibility rules, and
what conforming second implementations must do. Sable probes the
proposal for holes. **Requires your approval on the spec amendment
before any implementation starts.**

*Artifact:* `dispatches/2026-05-11-cost-based-dispatch-proposal.{readout.md,yaml}`
plus `dispatches/2026-05-11-cost-based-dispatch-audit.md`.

### 4. CBOR-aware Sable re-audit.

*Blocker I named:* nothing changed since last audit.

*Revised take:* something did change — not the CBOR code, but the
*knowledge* about it. AUD-2026-05-11-04 uncovered a cross-parser
decimal-text divergence between `serde_json` and Python `json`. That
changes what Sable should probe for. The re-audit is motivated by
new information, not new code.

*First step taken:* run the audit with that new context. Sable looks
for adjacent divergences — does the same parser gap hit canonical
JSON bytes? Does integer exactness hold past the i64 boundary? Are
there other places where "byte agreement" quietly depends on an
unstated parser assumption? Files what she finds (or doesn't).

*Artifact:* `dispatches/2026-05-11-cbor-reaudit.md`. Any P1 findings
get fixed in this session, same rule as before.

## What remains yours to decide

After reading these, you still own three explicit yes/no calls:

- **Primary-hash migration**: go or wait. If go, on what date.
- **Store GC**: approve the proposed design, modify it, or
  redirect to a different shape.
- **Cost-based dispatch**: approve the spec amendment as drafted,
  request changes, or reject.

The CBOR re-audit does not need a decision from you — findings
resolve themselves per Sable's normal discipline.

## What I'm not yet sure of

Whether any of the three proposals will survive first contact with
you without changes. The point of writing the proposal is to make
the disagreement specific rather than abstract. If you change any
of them materially, I'll mark the paired dispatch superseded and
re-issue.
