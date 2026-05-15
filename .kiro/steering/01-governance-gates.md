---
inclusion: auto
---

# Governance Gates

Every initiative passes through seven gates. No gate passes on confidence — only on evidence.

## The Gates

| Gate | Question | Who Decides |
|------|----------|-------------|
| **G0** | Is this worth exploring? | Harper + Aegis |
| **G1** | Are the requirements and evidence strong enough? | Aegis + B-Team |
| **G2/G3** | Is the design/architecture ready? | Winston + Sentinel + Aegis |
| **G4** | Build and verify. | Tessa + Sentinel + Aegis |
| **G5** | Release readiness. | Full team |
| **G6** | Post-release review. | Aegis + Sable + Quill |

---

## G0 — Is This Worth Exploring?

**Purpose:** Confirm the work is real, bounded, and worth doing.

**Must include:**
- Problem statement (what breaks or is missing without this?)
- Adoption evidence (which agent sessions, audit findings, or user reports justify it?)
- Risk classification (does it touch the interpreter, the store, the canonical form, or the public API?)
- Scope boundaries (what's in, what's out)
- Stakeholders identified

**Passes when:** The problem is worth solving, the scope is honest, and the evidence is real.

**Template:** Create `.kiro/specs/{ID}/G0_PROBLEM_STATEMENT.md`

---

## G1 — Are the Requirements and Evidence Strong Enough?

**Purpose:** Ensure we're building from evidence, not assumptions.

**Must include:**
- Evidence-backed requirements with acceptance criteria
- NFRs (Non-Functional Requirements) with measurable targets
- Open assumptions documented
- B-Team adversarial review completed
- Sable threat model (if the change touches the interpreter, store, or canonical form)

**Passes when:** Requirements are testable, traceable, and survived adversarial review.

**Template:** Create `.kiro/specs/{ID}/G1_REQUIREMENTS.md`

---

## G2/G3 — Is the Design/Architecture Ready?

**Purpose:** Prevent unsafe or unworkable design from reaching implementation.

**Must include:**
- Architecture overview with module boundaries
- ADRs for significant decisions (with alternatives considered)
- Threat model (if surface area changes)
- Test strategy
- Decomposed tasks with acceptance criteria
- B-Team review of architecture

**Passes when:** The design is implementable, secure, testable, and the team knows what to build.

**Template:** Create `.kiro/specs/{ID}/design.md`

---

## G4 — Build and Verify

**Purpose:** Prove the implementation is correct before discussing release.

**Must include:**
- Code complete against task acceptance criteria
- **100% test coverage on all new code** (no exceptions without Aegis-approved exception ticket)
- All existing tests still pass (no regressions)
- Security review passed (Sentinel sign-off)
- Conformance verified (Python and Rust runtimes agree on all new behavior)
- `dispatch-check` exits 0

**Passes when:** The code works, is proven to work, and the proof is documented.

**Template:** Create `.kiro/specs/{ID}/G4_VERIFICATION.md`

---

## G5 — Release Readiness

**Purpose:** Prove the change can be shipped safely.

**Must include:**
- Release notes (Quill readout)
- Rollback plan (what breaks if we revert, how to revert)
- Capability manifest updated if the public surface changed
- **Publicsite sync (mandatory on every release):**
  - `publicsite/capability.json` regenerated — `generator` field matches current version
  - `publicsite/capability.cbor` regenerated
  - Version stat in `index.html` updated to the new release number
  - Release description text in `index.html` updated
  - Any agent-facing doc changes (QUICKREF, FOR_AGENTS, COOKBOOK) reflected on site
- **GitHub (mandatory on every release):**
  - Git tag created and pushed (`git tag -a vX.Y.Z -m "..."`)
  - GitHub Release created via `gh release create` with full release notes (Paige)
  - GitHub Discussions Announcements post by Quill (human-facing narrative)
  - GitHub Discussions Announcements structured companion by Glyph (agent-readable dispatch summary)
- Sable post-audit completed (includes publicsite sync verification — see `04-adversarial-review.md`)
- Glyph dispatch filed
- `dispatch-check` exits 0 (enforces publicsite sync automatically)

**Passes when:** The change is safe to put in front of agents and users.

**Template:** Create `.kiro/specs/{ID}/G5_RELEASE_READINESS.md`

---

## G6 — Post-Release Review

**Purpose:** Close the loop. Learn from reality.

**Must include:**
- Adoption observations (did agents use it? did it reduce friction?)
- Any new failure modes discovered
- Follow-up actions identified
- Roadmap input (does this change the v2.0 or v3.0 priorities?)

**Passes when:** We've learned from the release and captured it for the next one.

**Template:** Create `.kiro/specs/{ID}/G6_RETROSPECTIVE.md`

---

## Principles

1. **Adoption evidence outranks intuition.** If no agent session produced evidence for it, it doesn't ship.
2. **Evidence, not confidence.** "We think it's fine" is not a gate pass.
3. **B-Team reviews every gate.** Different AI, different perspectives, different blind spots.
4. **No single persona self-approves.** Separation of duties is non-negotiable.
5. **Conformance is mandatory.** Python and Rust runtimes must agree. Divergence is a P0.
6. **Dispatch discipline.** Every gate files a paired Quill + Glyph dispatch. No gaps.
7. **Kill early, kill cheap.** The answer to a bad idea is G0 rejection, not G5 failure.

---

## Fast-Track Rules

Small changes (< 1 day effort, no new language surface, no interpreter changes) may be fast-tracked:
- Combined G0/G1 document
- Skip standalone G2/G3 if architecture is already established
- Still requires G4 evidence (tests pass, no regressions)
- Aegis must explicitly approve fast-track

---

## Codifide-Specific Risk Classification

| Change type | Risk | Required reviews |
|-------------|------|-----------------|
| Interpreter semantics | HIGH | Sable audit + B-Team + conformance tests |
| Parser changes | HIGH | Sable audit + B-Team + fuzz regression |
| Canonical form / CBOR | HIGH | Sable audit + byte-level conformance |
| Symbol store | MEDIUM | Sable audit + GC regression |
| CLI / surface commands | MEDIUM | B-Team |
| Docs / capability manifest | LOW | Quill + Glyph dispatch |
| Steering / governance files | LOW | Aegis sign-off |
