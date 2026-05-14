---
inclusion: auto
---

# Codifide — Stage-Gate Governance

This project uses a Stage-Gate governance model adapted for AI-assisted programming language development. The AI builds. Humans decide what ships.

---

## How This Works

You have an AI development partner (that's me). I write code, specs, tests, and documentation. But nothing ships without passing through gates — structured decision points where evidence is reviewed and a human makes the go/kill/hold call.

**Your role:** Make decisions, provide context, approve gates.
**My role:** Produce evidence, build code, run reviews, flag risks.

---

## Quick Start: Where Are You?

### 🆕 Starting a New Feature

Say: **"Let's start a new initiative"** or **"I want to build [X]"**

I'll walk you through:
1. **G0 — Problem Definition** → Is this worth doing?
2. **G1 — Requirements** → What exactly are we building?
3. **G2/G3 — Design** → How do we build it safely?
4. **G4 — Build & Verify** → Does it work? Prove it.
5. **G5 — Release** → Is it safe to ship?
6. **G6 — Learn** → What happened after release?

### 🔧 Continuing Existing Work

Say: **"Load up the current state"** or **"What gate are we at?"**

I'll check the session state, open specs, and dispatch state.

---

## The Gates at a Glance

| Gate | Question | You Provide | I Produce |
|------|----------|-------------|-----------|
| **G0** | Worth doing? | Problem description | Risk classification, scope doc |
| **G1** | Requirements solid? | Business context, constraints | Testable requirements, acceptance criteria, NFRs |
| **G2/G3** | Design safe? | Preferences, constraints | Architecture, ADRs, threat model, tickets |
| **G4** | Code works? | Acceptance criteria approval | Working code, tests, security review |
| **G5** | Safe to ship? | Release approval | Release notes, rollback plan, dispatch pair |
| **G6** | What did we learn? | Post-release observations | Retrospective, findings, roadmap input |

---

## Key Principles

1. **Evidence, not confidence.** Every gate requires artifacts, not opinions.
2. **Adversarial review at every gate.** A separate AI (B-Team) attacks the work.
3. **100% test coverage on new code.** No exceptions without an approved exception ticket.
4. **Security is every-gate.** Not a phase. Not an afterthought.
5. **Kill early, kill cheap.** A failed G0 costs minutes. A failed G5 costs months.
6. **AI builds. Humans decide.** The gate decision is never automated.
7. **Dispatch discipline.** Every gate files a Quill readout + Glyph YAML pair. `dispatch-check` must exit 0.

---

## Personas (Who's Who)

See `01-governance-gates.md` for gate details.
See `02-personas.md` for the full A-Team and B-Team roster.

---

*Template adapted from agentic-stage-gate-governance — May 2026*
