---
inclusion: auto
---

# NFRs, KPIs, and Benchmarks Are Mandatory

## Rule

Every initiative that reaches G1 MUST include measurable targets. If you can't measure it, you can't ship it.

---

## What's Required

### NFRs (Non-Functional Requirements)
Technical performance targets with pass/fail thresholds.

**Format:**
| ID | Metric | Target | Measurement Method | Gate |
|----|--------|--------|--------------------|------|
| NFR-PERF-001 | Interpreter throughput | ≥ baseline (no regression) | `python3 -m pytest tests/` | G4 |
| NFR-CONF-001 | Python/Rust conformance | 100% on conformance suite | `tests/test_conformance.py` | G4 |
| NFR-SEC-001 | Effect enforcement | 0 escapes on fuzz corpus | Rust fuzz harness | G4 |

### KPIs (Key Performance Indicators)
Adoption and quality outcome targets.

**Format:**
| ID | Metric | Baseline | Target | Measurement | Owner |
|----|--------|----------|--------|-------------|-------|
| KPI-001 | Agent Program 5 success rate | 0/3 (Track 1) | 3/3 | Next agent case study | Harper |
| KPI-002 | Dispatch pairs complete | 100% (current) | 100% | `dispatch-check` | Glyph |

### Benchmarks
Baseline comparisons (before vs. after, Python vs. Rust).

**Format:**
| ID | Comparison | Current | Target | When Measured |
|----|-----------|---------|--------|---------------|
| BM-001 | Rust vs. Python interpreter throughput | 2x (v2.0 Shape A) | ≥ 2x (no regression) | G4 |

---

## Ownership

| Category | Defines | Measures | Enforces |
|----------|---------|----------|----------|
| NFRs | Forge (Performance) | CI / test suite | Build gates |
| KPIs | Harper (Product) | Agent case studies, dispatch-check | Release go/no-go |
| Benchmarks | Forge + Tessa | Benchmark suite | Phase gate evidence |

---

## Enforcement

- **G1 will not pass** without NFRs and KPIs defined
- **G4 will not pass** without NFR evidence (test results, not promises)
- **G5 will not pass** without KPI baseline collected or measurement plan documented
- **G6 requires** KPI actuals vs. targets comparison

---

## Codifide-Specific NFR Baselines (as of v2.0)

These are the current baselines. Any change that regresses them is a G4 blocker.

| Metric | Baseline | Source |
|--------|----------|--------|
| Python test suite | 289 passing, 0 skipped | 2026-05-13 |
| Rust canonical tests | 28 passing | 2026-05-13 |
| `dispatch-check` | exits 0 | 2026-05-13 |
| `agent-quickstart` | exits 0 | 2026-05-13 |
| Capability manifest hash | `sha256:713d6f6b3a6cfb747cec3bfba0f25331c61b0052bdd166523c175daa2c1f6756` | 2026-05-13 |
