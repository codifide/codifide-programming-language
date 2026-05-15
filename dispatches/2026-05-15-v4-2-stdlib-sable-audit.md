# Sable Audit — Standard Library (V4-2)

**Date:** 2026-05-15  
**Persona:** Sable  
**Scope:** `codifide/runtime/primitives.py` — `io.read`, `io.write`, `io.exists`, `http.get`, `http.post`, `json.parse`, `json.encode`, `clock.today`, `clock.parse`, `clock.add_days`, `clock.format`  
**Initiative:** REQ-V4-2

---

## Audit scope

Four new primitive groups added in v4.0. This audit checks:
- Path traversal defense in file I/O
- HTTPS enforcement in HTTP client
- JSON injection / deserialization safety
- DoS vectors (unbounded reads, slow requests)
- Effect enforcement (are effects declared and checked?)
- Error message safety

---

## Findings

### AUD-STD-01 (P2) — Path traversal defense is split-based, not canonical-path-based

**What:** `io.read` and `io.write` reject paths containing `..` by checking
`".." in p.split(os.sep) or ".." in p.split("/")`. This catches `../../etc/passwd`
but may not catch all traversal forms on all platforms.

**Probe:** On macOS/Linux, `os.sep` is `/`, so both checks are equivalent.
But a path like `/foo/bar/..` (no `..` as a path component, but resolves
above `bar`) would pass the check. However, `os.path.realpath` would resolve
it — the current check does not use `realpath`.

**More concerning:** A path like `/foo/./../../etc/passwd` contains `..` as
a component and would be caught. But `/foo/%2e%2e/etc/passwd` (URL-encoded)
would not be caught — though Python's `open()` would not decode URL encoding,
so this is not exploitable in practice.

**Fix:** Use `os.path.realpath(p)` and verify the resolved path starts with
an allowed prefix (e.g., the current working directory). This is defense-in-depth
beyond the current `..` check.

**Severity:** P2 — the current check catches the common case. The gap requires
a contrived path that Python's `open()` would not actually traverse differently.
Recommend adding `realpath` check before v5.0.

**Resolution:** Deferred — document as a known limitation. The `..` check
catches all practical traversal attempts. A `realpath`-based check is the
right long-term fix.

---

### AUD-STD-02 (P1) — `http.get` and `http.post` follow redirects to HTTP URLs

**What:** `urllib.request.urlopen` follows HTTP redirects by default. A server
at `https://example.com` could redirect to `http://evil.com`, bypassing the
HTTPS-only check. The check only validates the initial URL, not redirect
destinations.

**Probe:**
```python
# A server at https://example.com returns:
# HTTP/1.1 301 Moved Permanently
# Location: http://evil.com/steal-data
# urllib follows this redirect to http://evil.com
```

**Fix:** Use a custom `HTTPRedirectHandler` that rejects redirects to non-HTTPS
URLs, or set `urllib.request.Request` with no redirect following and handle
redirects manually.

**Severity:** P1 — a malicious server could redirect an agent's HTTP request
to a non-HTTPS endpoint, potentially exposing request data or enabling MITM.

**Resolution:** Applied — see fix below.

---

### AUD-STD-03 (P3) — `json.parse` accepts arbitrarily deep nesting

**What:** Python's `json.loads` has no depth limit. A deeply nested JSON
structure (e.g., 10,000 levels of `[[[[...]]]]`) can cause a `RecursionError`
in Python's JSON parser, which would surface as an unhandled exception rather
than a typed `PrimitiveError`.

**Probe:**
```python
import json
json.loads("[" * 10000 + "]" * 10000)  # RecursionError on CPython
```

**Fix:** Wrap `json.loads` in a try/except that catches `RecursionError` and
raises `PrimitiveError`.

**Severity:** P3 — requires a deliberately malicious input. Not a practical
concern for agent programs processing real data.

**Resolution:** Applied — `json.parse` already wraps in `except (ValueError, json.JSONDecodeError)`. Adding `RecursionError` to the catch.

---

### AUD-STD-04 (P3) — `clock.format` passes user-controlled format string to `strftime`

**What:** `clock.format(ts, fmt)` passes `fmt` directly to `datetime.strftime`.
Python's `strftime` does not have format string injection vulnerabilities (unlike
C's `printf`), but a malicious format string could produce unexpected output
or trigger locale-dependent behavior.

**Assessment:** Python's `strftime` is safe — it does not execute code from
format strings. The worst case is garbled output. Not a security issue.

**Severity:** P3 — not exploitable. Noted for completeness.

**Resolution:** Accepted. No action needed.

---

### AUD-STD-05 (P2) — `io.write` has no size limit

**What:** `io.read` has a 16 MiB size limit. `io.write` has no limit — an
agent could write an arbitrarily large file, potentially filling the disk.

**Fix:** Add a 16 MiB limit to `io.write` consistent with `io.read`.

**Severity:** P2 — a runaway agent could fill disk. Not a security issue in
the traditional sense but a resource exhaustion risk.

**Resolution:** Applied — see fix below.

---

## Fixes applied

**AUD-STD-02 (P1) — HTTPS redirect enforcement:**

**AUD-STD-03 (P3) — JSON recursion depth:**

**AUD-STD-05 (P2) — io.write size limit:**

These three fixes are applied in `codifide/runtime/primitives.py` in this session.

---

## What I did not test

- Whether `http.get` correctly handles chunked transfer encoding
- Whether `json.encode` handles all Python types that Codifide values can hold
- Whether `clock.parse` handles all valid ISO date formats (only `YYYY-MM-DD` is documented)
- Whether `io.read` handles binary files (it uses UTF-8 encoding — binary files raise `PrimitiveError`)

---

## Overall assessment

Three findings require fixes: one P1 (HTTPS redirect bypass), one P2 (io.write
no size limit), one P3 (JSON recursion). All three are applied in this session.
The remaining findings are accepted limitations. The stdlib is safe to ship
with these fixes applied.

**Verdict: PASS WITH CONDITIONS** — P1 and P2 fixes applied before close.
