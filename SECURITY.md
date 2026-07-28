# Security

This document states what MagnetAI defends against, how, and — importantly — where
the deliberate trade-offs are. Controls without stated limits are marketing.

## Reporting a vulnerability

Email the maintainer rather than opening a public issue. Include reproduction
steps and, if the API returned one, the `request_id` from the response body: it
retrieves the full server-side log trail for that request.

---

## Threat model

MagnetAI is multi-tenant, spends money per request, and fetches URLs that users
supply. That produces four primary risks:

1. **Cross-tenant data access.** Leads are a customer's most commercially
   sensitive asset. One account reading another's leads is the worst outcome here.
2. **Server-side request forgery.** The analyzer fetches an arbitrary user-supplied
   URL, which without validation is a direct path to cloud metadata credentials and
   internal services.
3. **Cost abuse.** Analysis and generation each spend real Gemini and Vercel budget.
   An unauthenticated or unlimited endpoint is a way to spend someone else's money.
4. **Credential compromise.** Stolen tokens or weak password storage compromise
   every widget and lead an account owns.

---

## Controls

### Authentication

- **Argon2id** password hashing (`argon2-cffi` defaults, RFC 9106 profile). Hashes
  are re-computed on login when parameters fall behind current policy.
- **Password policy** is length-first per NIST SP 800-63B: 12 characters minimum,
  letters plus digits, and a common-password blocklist — not forced symbol classes.
- **JWTs** are HS256 with a `typ` claim, so a long-lived refresh token cannot be
  replayed as an access token; a `jti` for revocation; and an `iss` claim. Required
  claims are enforced on decode, so `alg: none` and claim-stripping are rejected.
- **Access tokens live 30 minutes; refresh tokens 30 days and are single-use.**
  Refreshing rotates the pair, so a stolen refresh token stops working as soon as
  the legitimate client refreshes.
- **Logout revokes** the refresh token via a Redis denylist keyed on `jti`, with a
  TTL matching the token's own expiry so entries self-clean.
- **Login does not enumerate users.** Unknown emails and wrong passwords return
  identical status and body, and an unknown email still performs a hash comparison
  against a dummy hash so response timing does not distinguish the two.
- Deactivating or deleting an account invalidates its tokens immediately, because
  every request re-checks the user row rather than trusting the token's claims.

### Authorization

- Every widget, lead, heal event, deployment, and payment query is filtered by
  `user_id`. There is no unfiltered read path on an authenticated endpoint.
- Cross-tenant access returns **404, not 403** — a 403 would confirm the resource
  exists. Covered by explicit tests in `tests/features/widgets/test_ownership.py`.
- Non-UUID path parameters are rejected before reaching the database, so a
  malformed id cannot raise a driver error that leaks schema details.
- Foreign keys with `ON DELETE CASCADE` mean deleting an account genuinely removes
  its data rather than orphaning it.

### SSRF protection

`app/platform/security/url_guard.py` validates every user-supplied URL before the
analyzer or heal sweep touches it:

- Only `http`/`https`, and only ports 80/443/8080/8443.
- Hostnames are resolved and **every** returned address is checked, so a
  multi-answer DNS record cannot slip one private address through.
- Rejected: loopback, private, link-local, CGNAT, reserved, multicast, and
  unspecified addresses; cloud metadata IPs (AWS/GCP/Azure/Alibaba/Oracle,
  including IPv6); IPv4-mapped and tunnelled IPv6 forms that smuggle a private v4
  destination inside a v6 literal.
- URLs with embedded credentials are rejected (a redirect/parser-confusion vector).
- Fragments are stripped; a trailing dot cannot bypass the hostname blocklist.
- For fetches the backend performs itself, redirects are followed manually and each
  hop is re-validated, capped at five hops.

**Known limitation — DNS rebinding.** A hostname could resolve to a public address
during validation and a private one at fetch time. This is accepted because the
page fetch is performed by Gemini's own sandboxed URL tool, not from inside our
network, so a rebind lands in Google's fetcher. The one fetch we make directly (the
deployment health check) re-validates each redirect hop.

**Escape hatch.** `MAGAI_ALLOW_PRIVATE_TARGET_URLS=true` disables address checks
for local development. Production configuration validation rejects it outright.

### Rate limiting

Redis fixed-window counters, per-user when authenticated and per-IP otherwise, so
one tenant cannot exhaust another's quota:

| Endpoint | Default | Why |
|---|---|---|
| `POST /api/widgets/analyze` | 10/hour | Spends a Gemini call |
| `POST /api/widgets/build` | 5/hour | Spends generation + a Vercel deploy |
| `POST /api/widgets/{id}/architect-preview` | 20/hour | Spends a Gemini call |
| `POST /api/leads/{id}` | 30/minute | Public and unauthenticated |
| `/api/auth/*` | 10/minute | Slows credential stuffing |

**Trade-off — fails open.** If Redis is unreachable, requests are allowed and the
failure is logged. These limits protect budget, not correctness, and a Redis blip
should not take the API offline. The distributed lock makes the **opposite** choice
and fails closed, because a double rebuild is worse than a skipped one.

### HTTP layer

- **CORS** uses an explicit origin allowlist with credentials enabled. `*` is
  rejected in production — wildcard-plus-credentials is invalid per spec and would
  let any site drive the API with a victim's token.
- **Security headers** on every response: `nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, a `default-src 'none'` CSP with
  `frame-ancestors 'none'`, `Permissions-Policy`, COOP/CORP, and `Cache-Control:
  no-store` so tokens and lead data are never cached by intermediaries. HSTS is
  asserted only over HTTPS, so it cannot poison `localhost` in development.
  (These lock down *the API*; generated widgets are framed from their own Vercel
  origin, so embedding is unaffected.)
- **Body size cap** (1 MiB default) checked against `Content-Length` *and* by
  counting streamed bytes, so a chunked request cannot bypass it.
- **`TrustedHostMiddleware`** blocks Host-header injection when
  `MAGAI_TRUSTED_HOSTS` is configured.
- **Error responses never leak internals.** Database and unexpected errors return a
  generic message plus a `request_id`; the traceback goes to the logs only.
  Validation errors return field paths and messages but never the submitted values,
  so a rejected password is not echoed back.
- **API docs are disabled in production** — they enumerate the whole attack surface.

### Payments

- Stripe webhooks require a valid signature computed with the shared secret; the
  verification error is never echoed, since it can reveal secret-length details.
- Webhook handling is **idempotent**: an already-confirmed payment short-circuits,
  and `stripe_session_id` is unique at the database level, so a replayed event
  cannot double-charge or duplicate a row.
- Amounts are re-read from Stripe and compared with the recorded amount rather
  than trusted from the event body; a mismatch marks the payment failed.
- `success_url` and `cancel_url` must be on the configured frontend origin,
  closing an open redirect through an otherwise genuine Stripe flow.

### Data handling

- **Logs are scrubbed.** The JSON formatter redacts any `extra` field whose key
  matches a password, token, secret, key, or cookie pattern.
- **Sentry** (optional) sends no request bodies and no PII, and scrubs sensitive
  headers and extras before transmission.
- **Metrics** label by route *template*, never by widget id, so `/metrics` exposes
  no tenant identifiers. It should still be restricted to the monitoring network at
  the ingress layer.
- **Lead payload caps**: the public submission endpoint bounds JSON size (16 KiB)
  and key count (100), so an embedded widget cannot be used to stuff the database.
- **Account deletion** cascades to widgets, leads, heal events, deployments, and
  payments — a real erasure, as a GDPR/CCPA request requires.

### Infrastructure

- Containers run as a **non-root** user with no build toolchain in the runtime
  image.
- Compose exposes Postgres and Redis on `127.0.0.1` only.
- CI runs dependency audits (`pip-audit`, `pnpm audit`), CodeQL with
  `security-extended`, a check that no `.env` file is tracked, and a scan of full
  git history for live-looking Stripe and Google credential patterns.
- Production config validation refuses to boot on a placeholder `SECRET_KEY`,
  wildcard CORS, debug mode, or the SSRF bypass.

---

## Known trade-offs

These are conscious decisions, not oversights.

**Tokens are stored in `sessionStorage`.** httpOnly cookies would be stronger
against XSS, but the SPA and API are separate origins, so cookie auth would require
cross-site cookies plus CSRF tokens. `sessionStorage` (not `localStorage`) is scoped
to the tab and cleared when it closes. All access goes through
`src/lib/auth-storage.ts`, so this can be changed in one place if the frontend and
API are ever served from one origin.

**SSE authenticates via a query parameter.** `EventSource` cannot set headers. The
access token is short-lived and the endpoint validates both the token and widget
ownership before streaming, but the URL may appear in proxy logs. Moving to
`fetch`-based streaming would remove this.

**Token revocation fails open.** If Redis is down, a revoked token remains valid
until it expires (≤30 min). Failing closed would turn a cache blip into a total
auth outage. Refresh tokens are additionally checked against `users.is_active` in
the database, so a disabled account cannot be resurrected by a cache outage.

**The frontend route guard is not a security boundary.** `RequireAuth` improves the
experience; every protected endpoint independently requires a valid token, so
bypassing the guard reveals nothing.

**Generated widget code is AI-authored.** It is built and served as a static bundle
on an isolated Vercel origin with no access to MagnetAI credentials or database. It
is not audited line by line, and it is untrusted by design — origin isolation, not
code review, is the control.

---

## Account recovery and MFA

- **Email verification.** Signup emails a single-use link. Only a SHA-256 hash of
  the token is stored, so a database leak yields nothing replayable. (SHA-256 rather
  than Argon2 is correct here: these are full-entropy random values with nothing to
  brute-force, and the lookup must be indexable.) Issuing a new link invalidates the
  previous one, so an older email stops being a live key to the account.
- **Verification gates spend, not access.** Unverified accounts can sign in and read
  their dashboard but cannot call `analyze` or `build`, so a throwaway address cannot
  consume Gemini or Vercel budget. Configurable via
  `MAGAI_REQUIRE_VERIFIED_EMAIL_TO_BUILD`.
- **Password reset** uses the same single-use hashed-token mechanism with a 30-minute
  lifetime. `forgot-password` returns an identical acknowledgement whether or not the
  address is registered, so it cannot be used to enumerate users. Redemption is an
  atomic conditional UPDATE, so two concurrent requests cannot both spend one token.
  Tokens are purpose-scoped: a verification token cannot reset a password.
- **A password change sends a notification email.** If a reset was an account
  takeover, this is how the real owner finds out — the attacker controls the session
  but not the mailbox.
- **TOTP MFA (RFC 6238)** implemented against the standard library, compatible with
  any authenticator app. Enrolment is two-phase: a secret is stored but MFA stays
  disabled until the user proves they can generate a code, so a mis-scanned QR cannot
  lock them out. Verification accepts ±1 time step to absorb clock skew, and compares
  in constant time.
- **Recovery codes** are stored as Argon2 hashes and consumed on use, so a database
  leak yields no usable second factor. Disabling MFA requires a valid current code,
  so a stolen access token cannot strip the second factor.
- **The MFA challenge happens after password verification**, so the `428 mfa_required`
  response cannot reveal which accounts have MFA without valid credentials.

## Generated widget code

Widget code is written by a model and is treated as untrusted:

- **Validated before it is built.** Path traversal, writes outside `src/`,
  unsupported file types, oversized output, and attempts to overwrite the scaffold
  (including the hand-written lead-capture SDK) are all rejected.
- **Forbidden constructs** are refused outright: `eval`, `new Function`,
  `document.write`, `dangerouslySetInnerHTML`, remote dynamic `import()`, Node
  built-ins, and reads of secret-shaped environment variables.
- **Served under its own CSP** — `default-src 'none'`, `script-src 'self'`, and
  `connect-src` limited to this API. Model-generated code cannot load remote scripts
  or exfiltrate to an arbitrary host from a visitor's browser.
- **Origin isolation** is the primary control: each widget is a separate Vercel
  project with no access to MagnetAI cookies, credentials, or database.
- **Design tokens are sanitized** before being written into a stylesheet. Values
  containing braces, semicolons, comment markers, `@import`, or `expression()` are
  dropped rather than escaped, so a token cannot terminate a declaration and inject
  new CSS rules.

## Not yet implemented

Honest gaps, in rough priority order:

- **Audit log** of security-relevant actions (logins, deletions, MFA changes) as
  queryable records rather than only application logs.
- **Per-account API keys** for programmatic access; today automation must use a
  user's JWT.
- **WebAuthn / passkeys** as a phishing-resistant alternative to TOTP.
- **Anomaly detection** on login (new device, new country) to trigger a step-up
  challenge.
- **Breached-password screening** against a service like Have I Been Pwned, in
  addition to the local common-password blocklist.
