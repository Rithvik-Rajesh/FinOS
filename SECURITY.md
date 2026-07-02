# FinOS — Security & Privacy Architecture

FinOS stores some of the most sensitive personal data that exists: a complete picture of a
person's income, spending, debts, assets, and goals. The bar is therefore closer to a
fintech app than to a note-taking app. This document defines the threat model, controls,
top risks, and privacy/regulatory posture.

**Reporting a vulnerability:** email `security@<domain>` (set before launch). Do not open
public issues for security reports.

---

## 1. Threat model (who we defend against)

| Adversary | Example goal | Primary defenses |
|---|---|---|
| Opportunistic attacker on the network | Read/modify traffic | TLS 1.2+ everywhere, HSTS, cert pinning on mobile |
| Malicious/compromised client | Access another user's data, forge writes | Server-side authZ on every row, JWT verification, no client-trusted totals |
| Stolen/lost phone | Read local financial DB | OS keystore, encrypted local DB, app lock, no secrets in logs |
| Compromised dependency / supply chain | Inject code, exfiltrate | Pinned deps, SBOM, `pip-audit`/`osv`, minimal deps in `llm/` path |
| Insider / leaked backup | Bulk data theft | Encryption at rest, least-privilege DB roles, encrypted backups, audit log |
| LLM prompt injection (via user data) | Exfiltrate other users' data, cause bad advice | Per-user context isolation, no cross-tenant data in prompts, tool authZ, output filtering |
| Abusive user / bot | Scrape, brute force, cost-bomb the AI | Rate limits, per-user AI budgets, abuse detection |

**Trust boundaries:** (1) device ↔ API, (2) API ↔ Postgres/Redis/MinIO, (3) API ↔ Supabase
Auth, (4) `ai` module ↔ external LLM. Every boundary authenticates and authorizes.

---

## 2. Authentication

- **Provider:** Supabase Auth (GoTrue) — email/OTP, phone OTP (important in India), and
  OAuth (Google/Apple). Password hashing, OTP, and session management are handled by a
  hardened, managed service (see [ADR-003](ARCHITECTURE.md#adr-003--auth-supabase-auth-managed-data-in-our-postgres)).
- **Tokens:** Short-lived **access JWT** (~1h) + **refresh token** (rotating). The API is
  **stateless**: it verifies the JWT signature against Supabase **JWKS** (cached, rotated),
  checks `exp`/`aud`/`iss`, and extracts the user id.
- **User provisioning:** On first valid request, JIT-create a local `users` row keyed by the
  Supabase UUID. Never trust client-supplied user ids.
- **Mobile token storage:** Access/refresh tokens in the OS secure enclave
  (`flutter_secure_storage` → Keychain / Keystore), never in shared prefs or the local DB.
- **App lock:** Optional biometric/PIN gate (local auth) before showing balances; auto-lock
  on background after a timeout.
- **Session controls:** Device registry per user; "sign out all devices" revokes refresh
  tokens. Sensitive actions (export all data, delete account) require re-authentication.

## 3. Authorization

- **Model:** Every domain row carries `user_id`. **Every query is scoped by the
  authenticated user id, server-side.** There is no endpoint that returns data without an
  ownership filter. This is enforced in the repository layer via a mandatory tenant filter,
  not left to individual handlers.
- **Defense in depth:** Consider Postgres **Row-Level Security** policies keyed to a
  `SET app.user_id` per request as a backstop, so a missed filter cannot leak data.
- **No horizontal trust:** IDs are UUIDv7 (non-enumerable) *and* ownership-checked — never
  rely on unguessable IDs alone.
- **Least privilege at the DB:** the app connects with a role that has no DDL/superuser
  rights; migrations run as a separate role.

## 4. Secrets management

- **No secrets in the repo.** `.env.example` documents keys; real values come from the
  environment / a secrets store (Docker secrets, SOPS-encrypted files, or a managed vault).
- **Categories:** DB credentials, Supabase service keys, MinIO keys, LLM API keys, JWT
  verification config, encryption keys.
- **Rotation:** documented rotation runbook; LLM and MinIO keys rotatable without redeploy
  where possible. **The Supabase service-role key never ships to the client.**
- **Mobile:** the app ships with no privileged secrets — only the public Supabase anon key
  and API base URL. All privileged operations happen server-side.

## 5. Data encryption

- **In transit:** TLS 1.2+ end to end; HSTS; modern cipher suites; **certificate pinning**
  in the mobile app against the API and Supabase.
- **At rest (server):** full-disk encryption on the VPS; Postgres data directory on an
  encrypted volume; **encrypted, offsite backups**. Application-level encryption for the most
  sensitive optional fields (e.g. free-text notes, imported bank identifiers) using an
  envelope-encryption scheme so a raw DB dump is not directly readable for those fields.
- **At rest (device):** the local SQLite DB is encrypted (SQLCipher) with a key held in the
  OS keystore, so a stolen phone does not expose the financial database.
- **Object storage:** MinIO server-side encryption enabled; receipts are private objects
  reachable only via short-lived presigned URLs.

## 6. Mobile security

- Encrypted local DB (SQLCipher) + secure token storage (Keychain/Keystore).
- Certificate pinning; reject cleartext traffic.
- Optional biometric app-lock and auto-lock; hide sensitive values in the app switcher.
- No sensitive data in logs, crash reports, or analytics; scrub amounts/PII from telemetry.
- Root/jailbreak awareness (warn, degrade sensitive features) — best-effort, not a hard gate.
- Obfuscate release builds; disable debuggability; verify no secrets in the bundle.
- Respect OS backup exclusion for the encrypted DB and token store.

## 7. API security

- All endpoints require a valid JWT except health/auth callbacks.
- **Strict input validation** via Pydantic on every request; reject unknown fields.
- Output is serialized through response schemas — never dump ORM objects (prevents field
  leakage).
- **Idempotency keys** on writes/sync to make retries safe and to resist duplicate-submit
  abuse.
- Security headers, CORS locked to known origins, request size limits, and
  **structured error responses that never leak internals** (see
  [docs/API.md](docs/API.md#error-handling)).
- Correlation IDs on every request for traceability.

## 8. Rate limiting & abuse control

- **Tiered limits** (Redis-backed, per user + per IP): normal endpoints, auth endpoints
  (tighter, to blunt OTP/credential abuse), and **AI endpoints (tightest)**.
- **Per-user AI budget:** hard monthly cap on tokens/cost; degrade to deterministic-only
  insights when exceeded. This protects both cost and against cost-bombing (see
  [docs/AI.md](docs/AI.md#cost-optimization)).
- Exponential backoff + lockout signaling on repeated auth failures (coordinated with
  Supabase).

## 9. Secure file uploads (receipts)

- **Presigned, direct-to-MinIO uploads** — the API never proxies file bytes.
- Constrain by content-type allowlist (images/PDF), **max size**, and a short URL TTL.
- Store under a per-user prefix; objects are private; downloads via short-lived presigned
  GET only.
- Validate/normalize on the server side asynchronously (verify magic bytes, strip EXIF/GPS
  metadata, re-encode images) before the receipt is considered trusted.
- Never derive server file paths from client-supplied names; generate opaque keys.

## 10. Financial data protection (specific measures)

- Money is integer minor units; no client-trusted aggregates — **all totals recomputed
  server-side**.
- Append-only bias for financial records; edits/deletes are soft and audited.
- Application-level encryption for the most sensitive optional fields.
- Strict data-export controls (re-auth, rate-limited, audited) and full-account deletion.

## 11. Audit logging

- **Append-only `audit_log`** table capturing: actor (user/system/worker), action, entity
  type + id, before/after diff (for sensitive entities), timestamp, request correlation id,
  device/IP. Writes go in the same transaction as the change via the outbox.
- Security-relevant events (login, token revoke, export, delete-account, permission
  failures, AI budget exhaustion) are logged and alertable.
- Audit logs are **not user-editable** and are retained separately from operational data.
- No secrets, no raw tokens, no full PAN/account numbers in logs (mask/truncate).

## 12. Privacy & regulatory

**India — DPDP Act, 2023 (primary regime):**

- **Consent-first**: explicit, purpose-bound consent for processing; separate, revocable
  consent for AI features and for any future SMS/Gmail/Account-Aggregator ingestion.
- **Data minimization**: collect only what a feature needs; the app works without linking
  real bank accounts.
- **Data-principal rights**: in-app **export** (machine-readable) and **delete my account &
  data** (hard delete of PII, with audit tombstones retained as required).
- **Breach readiness**: incident runbook and notification process.
- **Data localization awareness**: keep primary financial data in-region; document
  sub-processors (Supabase, LLM providers) and what leaves the region.

**Regulatory caution — this is a big one:**

- **Not investment advice.** Personalized investment advice is regulated in India (SEBI
  Investment Adviser regulations). FinOS provides **information and planning tools**, not
  recommendations to buy/sell specific securities. The AI assistant must include a
  standing **non-advice disclaimer**, avoid security-specific buy/sell guidance, and frame
  outputs as educational. Legal review before any "what should I invest in" feature.
- **Account Aggregator (RBI framework):** becoming a Financial Information User requires
  going through a licensed TSP/AA and RBI-aligned consent artifacts. Out of scope until a
  dedicated compliance workstream exists.
- **SMS/Gmail ingestion policy risk:** Google Play restricts the `READ_SMS` permission to
  default SMS handlers / narrow use-cases; iOS does not allow reading SMS at all. Gmail
  restricted scopes require Google's security assessment (CASA). Treat these ingestion
  features as **policy-gated, Android-first, opt-in**, and design around **user-forwarded
  or on-device parsing with explicit consent** rather than silent background reading. See
  the product analysis.
- **PCI DSS:** avoided by design — FinOS **never stores card PANs/CVVs** or processes
  payments. Wealth/card *bills* are tracked as amounts, not card numbers.

## 13. Top security risks & mitigations (ranked)

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| 1 | **Broken object-level authorization** (one user reads another's finances) | Critical | Mandatory server-side tenant filter in the repository layer + Postgres RLS backstop + authЗ tests on every endpoint |
| 2 | **Device theft exposes local financial DB** | High | SQLCipher-encrypted local DB, keystore-held key, biometric app-lock, auto-lock |
| 3 | **Token/secret leakage** | High | Keystore token storage, no privileged secrets on device, secrets store + rotation, cert pinning |
| 4 | **LLM prompt injection / data exfiltration** | High | Per-user context isolation, no cross-tenant data in prompts, tool-level authЗ, output filtering, treat model output as untrusted |
| 5 | **Backup/DB dump theft** | High | Encryption at rest, encrypted offsite backups, app-level encryption for most-sensitive fields, least-privilege roles |
| 6 | **AI cost-bombing / abuse** | Medium | Per-user AI budgets, tight AI rate limits, deterministic fallback |
| 7 | **Insecure file uploads** (malware, path abuse, EXIF GPS leak) | Medium | Presigned uploads, type/size limits, opaque keys, server-side re-encode + metadata strip |
| 8 | **Regulatory misstep (advice / SMS / AA)** | Medium→High (legal) | Non-advice framing + disclaimer, opt-in policy-gated ingestion, legal review before integrations |
| 9 | **Supply-chain compromise** | Medium | Pinned deps, SBOM, automated vuln scanning, minimal deps around `llm/` and auth |
| 10 | **Sync replay / duplicate writes** | Medium | Idempotency keys, server-assigned sequence, idempotent handlers |

## 14. Security in the SDLC

- Secrets scanning + dependency vulnerability scanning in CI.
- AuthZ tests are mandatory for every data endpoint (a test that user A cannot touch user
  B's data).
- Threat-model review at each phase boundary (see [MILESTONES.md](MILESTONES.md)).
- Pre-launch: external penetration test of the API and mobile app; privacy/legal review of
  DPDP compliance and the non-advice posture.
