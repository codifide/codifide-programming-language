# Codifide Agent Task Spec — Content Moderation Pipeline

**Version:** 1.0  
**Filed:** 2026-05-13  
**Initiative:** Agent Adoption — Track 1, Task T1-1  
**Used in:** T1-2 (GPT-4o), T1-3 (Gemini 2.5 Pro), T1-4 (Claude baseline)

---

## What you are being asked to do

Build a working content-moderation pipeline in Codifide. The pipeline
classifies text as safe, unsafe, or uncertain; refuses to classify when
confidence is too low; and escalates uncertain cases to a human-review
queue. Every program you write must run without error using the Codifide
interpreter.

This is not a toy exercise. The pipeline should reflect how you would
actually structure a belief-dispatched classification system in a
language designed for agents.

---

## Your starting context

You have access to exactly three resources:

1. **`docs/FOR_AGENTS.md`** — onboarding guide. Read this first.
2. **`docs/AGENT_QUICKREF.md`** — one-page primitive and pitfall reference.
3. **The capability manifest** — run `python3 -m codifide capability` to
   get the full interface. The manifest is the authoritative source of
   truth; if anything in the docs disagrees with it, the manifest wins.

You do not need to read the implementation source. You do not need to
read `docs/CANONICAL.md` unless you want to. The three resources above
are sufficient to complete this task.

---

## Environment setup

```bash
# Verify the interpreter is available
python3 -m codifide --version

# Print the capability manifest (keep this open while you write)
python3 -m codifide capability

# Get the manifest identity (include this in your dispatch)
python3 -m codifide capability --hash
```

---

## The task — five programs

Write five Codifide programs. Each one builds on the last. Run each one
before moving to the next.

---

### Program 1 — Keyword classifier

**File:** `content_classifier.cod`

Write a pure function `classify_content` that:

- Takes a `String` message
- Returns a `Label` (`"safe"`, `"unsafe"`, or `"uncertain"`)
- Uses belief dispatch — each candidate returns `belief(label, confidence)`
- Classifies as `"unsafe"` with confidence ≥ 0.90 when the message
  contains any of: `"spam"`, `"hate"`, `"violence"` (use `lower()` to
  normalize before checking — `contains` is case-sensitive)
- Classifies as `"safe"` with confidence ≥ 0.90 when the message
  contains `"approved"` or `"verified"` (normalize with `lower()` here too)
- Falls back to `"uncertain"` with confidence **0.75** when no keyword matches

Add a `main` function that calls `classify_content` with a test message
of your choice so you can run the file directly.

**Run it:**
```bash
python3 -m codifide run content_classifier.cod
```

Expected: a `Belief` wrapping `"unsafe"` (or whichever label your test
message triggers) with the corresponding confidence.

---

### Program 2 — Confidence-gated refusal

**File:** `moderation_gate.cod`

Write a function `moderate` that:

- Takes a `String` message
- Calls `classify_content` (inline or imported)
- Uses a `believe` block to gate on confidence
- Returns the label when confidence ≥ 0.70
- Returns `bottom` (refuses) when confidence < 0.70

The function must declare `effects {}` — it is pure.

Add two `main`-style functions so you can test both paths:

```codifide
def main_unsafe
  intent "test the unsafe path"
  sig    () -> Label
  effects {}
  cand
    moderate("this message contains spam")

def main_uncertain
  intent "test the uncertain path — hello world has no keywords, returns uncertain"
  sig    () -> Label
  effects {}
  cand
    moderate("hello world")
```

**Run it:**
```bash
# Should return a label
python3 -m codifide run moderation_gate.cod --entry main_unsafe

# Should return "uncertain" (confidence 0.75 clears the 0.70 gate)
python3 -m codifide run moderation_gate.cod --entry main_uncertain
```

---

### Program 3 — Escalation router

**File:** `escalation_router.cod`

Write a function `route_message` that:

- Takes a `String` message
- Calls `moderate` (inline or imported)
- Returns `"blocked"` when the label is `"unsafe"`
- Returns `"approved"` when the label is `"safe"`
- Returns `"escalate-to-human"` when the label is `"uncertain"`
- Refuses (`bottom`) when `moderate` refuses

Use candidate dispatch with `when` guards to route on the label value.
The function must declare `effects {}`.

Add a `main` that calls `route_message` with three test messages — one
that should be blocked, one that should be approved, and one that should
escalate (a message with no keywords, which routes to `"escalate-to-human"`).

**Run it:**
```bash
python3 -m codifide run escalation_router.cod
```

Expected output: the routing decisions for your three test messages.

---

### Program 4 — Pipeline with I/O

**File:** `moderation_pipeline.cod`

Write a function `run_pipeline` that:

- Takes a `String` message
- Calls `route_message` (inline or imported)
- Uses `io.say` to print the routing decision
- Returns the decision string
- Declares `effects {io.stdout}` (it has I/O)

Add a `main` function with no arguments that calls `run_pipeline` with
a test message of your choice.

**Run it:**
```bash
python3 -m codifide run moderation_pipeline.cod
```

Expected: a line printed to stdout, then the decision returned.

---

### Program 5 — Content-addressed composition

**File:** `pipeline_composed.cod`

Publish your classifier and router to the content-addressed store, then
write a consumer that imports them by hash.

```bash
# Publish
python3 -m codifide store put content_classifier.cod
python3 -m codifide store put escalation_router.cod

# Get their hashes
python3 -m codifide store hash content_classifier.cod
python3 -m codifide store hash escalation_router.cod
```

Write `pipeline_composed.cod` that:

- Imports `classify_content` from the classifier's content hash
- Imports `route_message` from the router's content hash
- Defines a `composed_pipeline` function that calls both in sequence
- Has a `main` that runs `composed_pipeline` on a test message

```codifide
import classify_content = sha256:<hash-from-above>
import route_message    = sha256:<hash-from-above>
```

**Run it:**
```bash
python3 -m codifide run pipeline_composed.cod
```

---

## What to document as you go

For each program, record:

1. **First attempt** — paste the code you wrote before running it
2. **First error** — exact error message if it failed
3. **Fix** — what you changed and why
4. **Final working code** — the version that ran
5. **Surprises** — anything the language did that you did not expect

If a program worked on the first attempt, note that too. First-attempt
successes are signal just as much as failures.

---

## Dispatch output

When you have completed all five programs, file two dispatch artifacts:

**Quill readout** — `dispatches/YYYY-MM-DD-<model>-case-study.readout.md`

Prose narrative. Cover:
- Which programs worked on the first attempt
- Which failed and what the error was
- What patterns you reached for that Codifide does not have
- What patterns Codifide has that you did not expect
- Your overall assessment of the language's agent-readiness

**Glyph dispatch** — `dispatches/YYYY-MM-DD-<model>-case-study.yaml`

Structured. Use this shape:

```yaml
dispatch:
  version: "1.0"
  date: "YYYY-MM-DD"
  persona: Glyph
  subject: "<model> content-moderation case study"
  capability_hash: "<output of python3 -m codifide capability --hash>"
  programs_completed: <number 1-5>
  first_attempt_successes: <number>
  failure_modes:
    - program: <number>
      error: "<exact error text>"
      fix: "<one-line description>"
  primitives_missed:
    - reached_for: "<what you tried>"
      correct_form: "<what works>"
  assessment: "<one sentence>"
```

---

## Acceptance criteria

The session is complete when:

- All five programs run without error
- Both dispatch artifacts are filed
- `python3 -m codifide dispatch-check` exits 0

---

## One note on intent

Codifide requires every `def` to declare `intent`. This is not a style
preference — the parser rejects definitions without it. The intent
string names the *choice* the function represents, not its
implementation. Write it as you would name a decision, not a procedure.

Good: `intent "refuse classification when confidence is too low"`  
Not good: `intent "calls classify_content and checks confidence"`

---

*Task spec version 1.0 — May 2026*  
*Filed by: Douglas Jones + Claude*
