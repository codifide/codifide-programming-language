---
inclusion: auto
---

# Adversarial Review Process

Every gate review MUST include an adversarial review by the B-Team before the gate can pass.

---

## The Rule

The builder cannot review their own work. Every gate requires **two independent reviews** using different AI models.

## Three-Model Architecture

- **A-Team** (Builders): Primary AI assistant. Designs, specs, implements, delivers.
- **B-Team** (Critics): Different AI model. Hostile personas. Has context. Finds defects — things that are wrong, incomplete, or risky.
- **Zero-Context Reviewer**: Different model again, no project context provided. Naive eye. Finds invisible assumptions — things that are undocumented, team-jargon-only, or would stop an agent or new contributor cold.

No two reviews use the same AI model. B-Team and Zero-Context use different models from each other and from the A-Team. This eliminates model-specific confirmation bias and shared blind spots.

---

## How to Run a B-Team Review

### Step 1: Prepare the Review Package

Concatenate the relevant artifacts into a single document. The B-Team must also receive links to the codebase before and after the change so holistic comparison can be performed.

### Step 2: Use the B-Team System Prompt

The full B-Team system prompt is in `02-personas.md`. Copy it into a **different AI** (GPT-4o, Gemini, etc.).

### Step 3: Submit the Spec/Code

Paste the review package after the system prompt. Let the B-Team run.

### Step 4: Bring Findings Back

Copy the B-Team output back to the A-Team (this conversation). The A-Team must respond to every finding:

| Response | Meaning |
|----------|---------|
| **Accept & Fix** | Finding is valid. Will fix before gate. |
| **Accept & Defer** | Finding is valid but not gate-blocking. Tracked with ticket and deadline. |
| **Reject** | Finding is incorrect. Must provide counter-evidence (not just disagreement). |

### Step 5: Resubmit if Needed

If the verdict is FAIL or PASS WITH CONDITIONS (with CRITICALs), fix and resubmit. Repeat until PASS.

---

## When to Invoke B-Team

- Before any gate passes (G0–G6)
- Before any major architecture decision is finalized (e.g. RPC API design)
- Before any release candidate is approved
- When the team disagrees on risk level
- When the change touches the interpreter, parser, canonical form, or store

---

## Scoring

| Verdict | Meaning | Action |
|---------|---------|--------|
| **PASS** | No CRITICALs, no unresolved MAJORs | Gate can proceed |
| **PASS WITH CONDITIONS** | No CRITICALs, MAJORs have resolution plan | Gate can proceed if conditions met |
| **FAIL** | CRITICALs present OR too many unresolved MAJORs | Must fix and resubmit |

---

## Sable vs. B-Team

These are different reviews with different purposes:

| | Sable | B-Team |
|---|---|---|
| **Who** | A-Team auditor persona (same model) | Different AI model entirely |
| **Bias** | Adversarial but informed | Adversarial and independent |
| **Focus** | Soundness, security, conformance | Everything — requirements, design, code, ops |
| **Output** | Findings list with severity + probes | CRITICAL/MAJOR/MINOR/OBSERVATION |
| **Paired with** | Quill readout + Glyph dispatch | A-Team response to each finding |

Both run at every gate. Sable first (informs the B-Team package), then B-Team.

---

## Sable Release Checklist — Publicsite Sync

Every G5 (Release Readiness) Sable audit **must** include the following
publicsite sync checks. A finding on any item is at minimum P2 and is a
release blocker.

### PS-1 — capability.json generator version
- Open `publicsite/capability.json`.
- Read the `generator` field.
- Run `python3 -m codifide capability | python3 -c "import sys,json; print(json.load(sys.stdin)['generator'])"`.
- **Pass:** the two values match.
- **Fail (P2):** they differ. The published manifest is stale.

### PS-2 — capability.cbor freshness
- Verify `publicsite/capability.cbor` was regenerated in the same commit
  as `publicsite/capability.json`.
- **Pass:** both files have the same commit timestamp.
- **Fail (P2):** CBOR is older than JSON, or JSON is older than the release commit.

### PS-3 — version stat in index.html
- Search `publicsite/index.html` for `lang-stat-num`.
- **Pass:** the version number matches the current release tag.
- **Fail (P2):** the version stat still shows the previous release.

### PS-4 — release description text
- Search `publicsite/index.html` for the release description paragraph
  adjacent to the version stat.
- **Pass:** the description references the current release's key features.
- **Fail (P3):** the description still describes the previous release.

### PS-5 — agent-facing doc excerpts
- Check whether `index.html` embeds or links to AGENT_QUICKREF.md,
  FOR_AGENTS.md, or AGENT_COOKBOOK.md content inline.
- If so, verify the inline content matches the current file.
- **Pass:** no stale inline excerpts.
- **Fail (P3):** inline content diverges from the source doc.

### PS-6 — dispatch-check exits 0
- Run `python3 -m codifide dispatch-check`.
- **Pass:** exits 0.
- **Fail (P1):** exits non-zero. Session cannot close with gaps outstanding.

---

## Tracking

All B-Team findings are tracked in the relevant spec's `G4_VERIFICATION.md` or `G5_RELEASE_READINESS.md` with:
- Finding ID
- Description
- Owner
- Resolution status (Accept & Fix / Accept & Defer / Reject)
- Deadline

Items past their deadline escalate to MAJOR at the next gate.
