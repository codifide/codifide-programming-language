# Codifide Agent Adoption Initiative — Tasks

## Track 1: External Agent Case Study

- [ ] **T1-1** Write the pipeline task spec to give to each agent (content-moderation pipeline)
- [ ] **T1-2** Run GPT-4o session — fresh context, pipeline task, document all failures and fixes
- [ ] **T1-3** Run Gemini 2.5 Pro session — same task, same protocol
- [ ] **T1-4** Run Claude baseline session — same task, for comparison
- [ ] **T1-5** File Quill/Glyph dispatch pair for each session
- [ ] **T1-6** Sable audit of all three sessions — findings, patterns, gaps
- [ ] **T1-7** Write case study summary dispatch — what worked, what failed, what to fix

## Track 2: Adoption Infrastructure

- [ ] **T2-1** Generate `capability.json` and `capability.cbor` from current v1.0 implementation
- [ ] **T2-2** Add static files to publicsite, add Vercel routes, deploy
- [ ] **T2-3** Write `docs/AGENT_COOKBOOK.md` — top 10 failure modes from v1.0 reviews
- [ ] **T2-4** Write `dispatches/feedback/TEMPLATE.md`
- [ ] **T2-5** Implement `python3 -m codifide agent-quickstart` CLI subcommand
- [ ] **T2-6** Test quickstart in a clean environment
- [ ] **T2-7** File Quill/Glyph dispatch for Track 2 completion
- [ ] **T2-8** Sable audit of adoption infrastructure

## Track 3: v2.0 Roadmap

- [ ] **T3-1** Collect all findings from T1-6 and T2-8
- [ ] **T3-2** Update `docs/ROADMAP.md` — justify each v2.0 item with adoption evidence
- [ ] **T3-3** Open new spec for v2.0 language work
- [ ] **T3-4** File Quill/Glyph dispatch for roadmap update
- [ ] **T3-5** Sable audit of v2.0 roadmap for internal consistency

## Session Close

- [ ] **SC-1** `python3 -m codifide dispatch-check` exits 0
- [ ] **SC-2** All open Quill readouts have paired Glyph YAMLs
- [ ] **SC-3** session-close.readout.md and session-close.yaml filed
