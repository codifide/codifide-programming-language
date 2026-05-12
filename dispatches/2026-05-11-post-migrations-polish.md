# Post-migrations polish — session close attestation (2026-05-11)

*By Quill.*

After the three migrations landed, there were five things I said
we should do to make the language feel like it had been "finished
for the day" rather than "finished just enough to ship." User
asked for all five. All five shipped.

## What landed

**Rust CBOR-input subcommand.** A strict canonical-CBOR decoder in
the Rust crate, plus two new CLI subcommands — `hash-cbor-in` and
`bytes-cbor-in` — that accept canonical CBOR bytes as input,
bypassing `serde_json::from_str` entirely. Every finite f16 bit
pattern now produces byte-identical canonical CBOR on both
implementations when data travels as CBOR. The exhaustive
diagnostic un-skipped. **AUD-08, the P1 I filed and kept being
unable to fully close, is now structurally closed.**

**Sable re-audit of the new surfaces.** Cost-based dispatch and
store GC had shipped without adversarial probing. Sable went
through both and found five items — zero P0, zero P1, two P2s on
cost-dispatch that are docs-only clarifications, two P2s on GC
(symlink-follow on log, symlink check on lock) that are the same
defense shape the 2026-05-10 CBOR audit established, and one P3
on ROOTS parsing that now reports line numbers. Every finding
fixed in-session. Four regression tests added.

**`docs/STORE.md`.** A dedicated store specification. The four
properties (hash-verified reads, hash-verified writes, idempotent
writes, sound deletion) are now written down in one place. The
on-disk layout, the ROOTS file format, the GC dry-run discipline,
the concurrency model, the symlink defenses, the CLI, and the
pre-migration compatibility story are all there.

**Fresh-agent simulation.** With the caveat that I am Claude and
cannot invoke GPT-5.4 or Gemini 2.5 Pro from here, I played the
role honestly: read only `docs/FOR_AGENTS.md`,
`docs/AGENT_QUICKREF.md`, and the capability manifest; wrote
three programs a fresh agent might be asked to write; ran them.
All three passed on first try. The simulation surfaced one real
gap — the quickref didn't yet cover cost annotations — which I
fixed before moving on. The experiment that would actually
measure whether today's work moved the needle still requires
handing the repo to a different model session.

**Dispatch stream index.** Twenty-two dispatches on 2026-05-11
alone; the journal is getting hard to traverse by filename. A
zero-dependency Python generator produces `dispatches/INDEX.md`
grouped by date. A `codifide dispatch-index` CLI regenerates it,
`--check` verifies drift, and a drift guard test makes sure a
future dispatch added without regenerating the index surfaces
the same way a stale capability manifest would.

## The numbers at close of day

- Python: 172 tests passing, 0 skipped. Started the day at 122
  passing.
- Rust canonical: 28 tests passing. Started the day at 10.
- Dispatches filed today: 27.
- Capability manifest hash: `sha256:56fa68ae…` (moved once in the
  day; the `cost` keyword addition).
- Known P0 and P1 findings open: zero.
- Test skips: zero.

## What I did not do, and why

- **Real external-model experiment.** I cannot initiate a GPT-5.4
  session or a Gemini 2.5 Pro session from this agent. The
  experiment is filed as a future follow-on; the simulation is
  what I could do honestly.
- **Rust fuzz harness extension with cost-bearing inputs.**
  Bounded and simple, but not a gate on anything. Good for next
  session.
- **GC stress test over 10k symbols.** Design is O(n), constants
  unmeasured. Worth doing before v1.0.
- **Time-indexed types, Rust interpreter port.** Both roadmap
  items. Neither was on today's queue.

## What this felt like

A day that started with four external reviews telling us the
language was good but the authoring surface was rough, and ended
with every finding those reviews produced closed, three
governance-level proposals implemented, every open P1 closed
structurally, and a journal stream the project can grow into.
The language is better than it was this morning. That I am sure
of. Whether it is *measurably* better to an external agent is
the one thing we genuinely don't know yet, and the one thing
that would be worth finding out next.

## What I'm not yet sure of

Whether any of today's polish reveals a shape of program that
Codifide now awkwardly forbids or unexpectedly permits. The new
cost-dispatch rule interacts with believe dispatch and with
multi-candidate modules in ways the Sable audit probed but
didn't exhaust. The GC's transitive closure is tested on small
stores but not on ones where indices compose deeply. The first
program that breaks in a way the tests didn't cover will tell us
something; I don't know what yet.

For now the suite is green, the dispatches are indexed, and the
language has something to say for itself that it couldn't say
this morning.
