# Codifide Agent Adoption Initiative — Tasks

## Track 1: External Agent Case Study

- [x] **T1-1** Write the pipeline task spec to give to each agent (content-moderation pipeline)
- [x] **T1-2** Run GPT-4o session — fresh context, pipeline task, document all failures and fixes
- [x] **T1-3** Run Gemini 2.5 Pro session — same task, same protocol
- [x] **T1-4** Run Claude baseline session — same task, for comparison
- [x] **T1-5** File Quill/Glyph dispatch pair for each session
- [x] **T1-6** Sable audit of all three sessions — findings, patterns, gaps
- [x] **T1-7** Write case study summary dispatch — what worked, what failed, what to fix

**Track 1 complete — 2026-05-13**

Key findings:
- Programs 1–4: all three models succeeded (with varying self-correction)
- Program 5 (content-addressed composition): universal failure point — transitive dependency + Rust parser gap
- Routing after believe block: hardest pattern — all three models struggled differently
- is_bottom() trap: Gemini used it as propagation catcher (dead code)
- bind-before-when footgun: Claude hit it; GPT-4o and Gemini avoided by accident
- 7 findings total: 4 applied, 3 deferred to Track 2 / v2.0

---

## Track 2: Adoption Infrastructure

- [ ] **T2-1** Generate `capability.json` and `capability.cbor` from current v1.0 implementation
- [ ] **T2-2** Add static files to publicsite, add Vercel routes, deploy
- [ ] **T2-3** Write `docs/AGENT_COOKBOOK.md` — top 10 failure modes from Track 1 + v1.0 reviews
- [ ] **T2-4** Write `dispatches/feedback/TEMPLATE.md`
- [ ] **T2-5** Implement `python3 -m codifide agent-quickstart` CLI subcommand
- [ ] **T2-6** Test quickstart in a clean environment
- [ ] **T2-7** File Quill/Glyph dispatch for Track 2 completion
- [ ] **T2-8** Sable audit of adoption infrastructure
- [ ] **T2-9** Update capability manifest schema — add `note` field on primitives; add `is_bottom()` caveat; regenerate `docs/capability-0.1.json` *(added from Track 1 finding AUD-T1-01)*

Cookbook (T2-3) should cover these failure modes from Track 1:
1. Content-addressed composition — index pattern, CODIFIDE_RUNTIME=python
2. Routing after believe block — bind in body, if/then/else
3. is_bottom() trap — cannot catch propagated bottom
4. bind-before-when — guards execute before bodies
5. contains() case-sensitivity — always use lower()
6. Transitive dependency problem — individual imports don't carry deps
7. from-import Rust parser gap — requires Python runtime

---

## Track 3: v2.0 Roadmap

- [ ] **T3-1** Collect all findings from T1-6 and T2-8
- [ ] **T3-2** Update `docs/ROADMAP.md` — justify each v2.0 item with adoption evidence
- [ ] **T3-3** Open new spec for v2.0 language work
- [ ] **T3-4** File Quill/Glyph dispatch for roadmap update
- [ ] **T3-5** Sable audit of v2.0 roadmap for internal consistency

Track 1 v2.0 implications (to feed T3-2):
- RPC API: confirmed highest priority — eliminates Program 5 friction
- Static bind-before-when detection: parser scope tracking needed
- Manifest note field: schema change for is_bottom() and future primitives

---

## Session Close

- [ ] **SC-1** `python3 -m codifide dispatch-check` exits 0
- [ ] **SC-2** All open Quill readouts have paired Glyph YAMLs
- [ ] **SC-3** session-close.readout.md and session-close.yaml filed
