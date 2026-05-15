# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 4.x     | ✅ Current release — security fixes applied |
| 3.x     | ⚠️ Critical fixes only |
| < 3.0   | ❌ No longer supported |

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Use GitHub's private vulnerability reporting instead:
1. Go to the [Security tab](https://github.com/codifide/codifide-programming-language/security)
2. Click **"Report a vulnerability"**
3. Fill in the details

We will acknowledge receipt within **48 hours** and aim to provide a fix or
mitigation within **14 days** for critical issues.

## What counts as a security vulnerability

- **Interpreter sandbox escapes** — a Codifide program that performs effects
  not declared in its `effects {}` signature, bypassing the transitive effect
  check
- **Store integrity bypass** — a way to write to the symbol store without
  hash verification, or to read bytes that do not match the declared identity
- **Path traversal in `io.read` / `io.write`** — bypassing the `..` defense
- **HTTPS enforcement bypass in `http.get` / `http.post`** — making HTTP
  requests to non-HTTPS URLs
- **Registry authentication bypass** — accessing `POST /symbols` without a
  valid `REGISTRY_WRITE_TOKEN`
- **Denial of service** — inputs that cause the interpreter to hang, exhaust
  memory, or crash the host process

## What does not count

- Programs that produce wrong output due to a logic bug (use a regular issue)
- Performance problems that do not constitute a DoS (use a regular issue)
- Theoretical vulnerabilities without a proof of concept

## Security design notes

Codifide's security model is documented in the interpreter and store:

- **Effect enforcement** is transitive and checked at module load, not at
  runtime. A pure function cannot call an effectful one without the violation
  being caught before any code executes.
- **Content addressing** means the store cannot return different bytes under
  the same identity — every read is hash-verified.
- **The RPC server** binds to `127.0.0.1` only by default. It is not safe to
  expose over a network without a reverse proxy with TLS and authentication.
- **`io.read` and `io.write`** reject paths containing `..` before any
  filesystem access.
- **`http.get` and `http.post`** reject non-HTTPS URLs before any network
  request.

## Disclosure policy

We follow coordinated disclosure. We will credit reporters in the release
notes unless they prefer to remain anonymous.
