# Handover — Ops Effort Estimation Tool

> **Read this first.** It is the "you now own this" document: what exists, what access you
> need, how it is operated, and what is unfinished. Everything here is deliberately
> *non-secret* — resource and account **names** only, no keys, no connection strings, no
> subscription/tenant/client GUIDs. Those are transferred out-of-band.

**Handover baseline:** version **1.65**, branch `testing` @ `da3804b`, 208 tests passing.
**Prepared:** 2026-08-11.

---

## 1. What you are taking over

A Streamlit app (~16.4k lines of Python, 208 pytest tests) that produces AMS effort/cost
estimates and the surrounding proposal artifacts. It is deployed to Azure Container Apps by
a push-to-deploy GitHub Actions pipeline. Read **[README.md](README.md)** for what it does
functionally, and **[docs/architecture.md](docs/architecture.md)** for how it is built.

There is **no database** — all persistence is JSON blobs in one Azure Storage container.
There is **no login** — the `@nagarro.com` email gate is self-declared and is *not* a
security boundary (see §6.4).

---

## 2. Access & ownership transfer checklist

This is the part that actually blocks a handover. Code is in git; access is not.

| # | System | What it is | Currently held by | Action for you |
|---|---|---|---|---|
| 1 | **Azure subscription** | Hosts everything. Currently a **personal** account (`rjabhi77@gmail.com`), documented in DEPLOY.md. | Abhishek Chaurasia (personal) | ⚠️ **Biggest risk.** Either get co-owner access or complete the migration to the Nagarro subscription (§6.1). |
| 2 | **Resource group** | `AB-ms-cost-estimator` (region `centralindia`) | as above | Confirm you can see it in the Portal. |
| 3 | **Container Apps** | `nagarro-ops-estimator` (prod), `nagarro-ops-estimator-test` (staging), environment `env-ops-estimator` (VNet-integrated) | as above | Get Contributor on the RG. |
| 4 | **Container Registry** | ACR named `acr<first-12-of-subscription-id>`, Basic SKU, admin-enabled | as above | No action unless the subscription changes. |
| 5 | **Storage account** | `nagarroopsratecard` — holds the rate card **and** all estimates/drafts/approvals/shares/feedback | as above | Get **Storage Blob Data Contributor**. Without it you cannot inspect or repair data. |
| 6 | **The real rate card** | `genus_rate_card.xlsx` — **gitignored**, lives only in Blob | Blob only | Download a copy and keep it somewhere safe. It is not in git and not recoverable from git. |
| 7 | **GitHub repository** | `ruchulovsab-coder/Cost-Calculator` — a **personal** GitHub account | `ruchulovsab-coder` | ⚠️ Get admin/transfer. Repo Variables live here and CI cannot run without them. |
| 8 | **App registration (OIDC)** | `github-cost-calculator-oidc` with federated credentials `github-main` and `github-testing` | Entra ID on the personal tenant | You need rights to add a federated credential per new branch (§6.5). |
| 9 | **Azure Communication Services** | Sends approval / share / cleanup emails | as above | Optional — the app degrades to copyable links without it. |
| 10 | **Groq API key** | Optional LLM for Chat mode and optimizer narration | GitHub Secret | Optional — chat/narration disable cleanly without it. |

> **Rule of thumb:** items 1, 5, 6 and 7 are the ones that make the app unrecoverable if
> lost. Everything else can be rebuilt from `DEPLOY.md`.

---

## 3. Environment map

| Branch | Deploys to | Container App | Estimates container | `APP_BASE_URL` |
|---|---|---|---|---|
| `main` | **Production** | `nagarro-ops-estimator` | `estimates` | repo Variable |
| `testing` | **Staging** | `nagarro-ops-estimator-test` | `estimates-test` | auto-set to its own FQDN |
| any other branch | staging app (same `-test` target) | — | — | — |

One workflow (`.github/workflows/azure-deploy.yml`) drives both; the deploy job derives its
target from `GITHUB_REF_NAME` (`main` → prod, anything else → `<name>-test`). Deploys are
serialized per branch via `concurrency` so two quick pushes cannot collide on Azure.
Both apps scale to zero.

**Blob layout** (inside the estimates container):

```
<slug>__v<n>.json          saved estimate versions
__drafts__/<slug>.json     per-user autosaved work in progress
__orphans__/…              abandoned drafts awaiting token-gated deletion
__approvals__/<slug>__v<n>.json
__shares__/<slug>__v<n>.json
__feedback__/…             captured user feedback
```

## 4. Configuration reference

All non-secret configuration is a **GitHub repository Variable**; secrets are GitHub
Secrets. The deploy job injects them as Container App environment variables.

| Name | Where | Required? | Purpose |
|---|---|---|---|
| `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` | Variables | **Yes** | OIDC login. Identifiers, not credentials. |
| `RATECARD_ACCOUNT_URL` / `RATECARD_CONTAINER` / `RATECARD_BLOB` | Variables | No | Auto-load the rate card from Blob instead of manual upload. |
| `ESTIMATES_ACCOUNT_URL` / `ESTIMATES_CONTAINER` | Variables | No | Enables saved versions, drafts, approvals, shares, feedback. Without it, all of those silently disable. |
| `APP_BASE_URL` | Variable | No (but needed for emails) | Absolute base for approval/share/cleanup links. Without it the app refuses to send a dead relative link and shows a copyable one instead. |
| `ACS_ENDPOINT` + `ACS_SENDER` | Variables | No | Email via managed identity. |
| `ACS_CONNECTION_STRING` | **Secret** | No | Alternative to `ACS_ENDPOINT`. |
| `GROQ_API_KEY` | **Secret** (or Variable) | No | Chat mode + optional optimizer narration. |
| `GROQ_MODEL` | Variable | No | Defaults to `llama-3.3-70b-versatile` in code. |

**Resource tags are mandatory.** The corporate subscription policy denies resources/RGs
missing four tags; the workflow applies `Owner`, `Project`, `Purpose`, `Criticality` on
every create. Do not remove them.

---

## 5. How this project is operated

**Release flow** — the loop that has been used for every version:

1. Implement on **`testing`**.
2. `pytest` must pass (CI blocks deploy on test failure).
3. Commit + push → **staging redeploys automatically**.
4. **Verify on the staging URL** — the Streamlit UI is not testable locally in a
   meaningful way (see §6.6); staging is where behaviour is confirmed.
5. Promote: merge `testing` → `main`, push (production redeploys), tag `vX.Y`.
6. Record the release in `RESTORE.md` and bump `APP_VERSION` in `config/settings.py`.

`main` and `testing` are kept **content-identical** after each promotion.

**Every release is an annotated tag = a restore point.** A tag push does *not* deploy —
only a branch push does. Rollback: `git reset --hard vX.Y` (or safer, `git revert`) on
`main` + push. Full instructions in **[RESTORE.md](RESTORE.md)**.

**Commit style:** `feat|fix|refactor|chore|docs(scope): summary`.

### Guardrails — do not break these

These were deliberate decisions, not accidents:

1. **The engine is pure.** `compute_full_model` / `compute_multi_skill_model` take state and
   return a model — no Streamlit, no I/O. Everything (UI, exports, tests) calls them, so
   displayed and exported numbers cannot drift.
2. **Excel must equal the engine.** The formula workbooks are recalc-verified against the
   engine to the rupee. If you change the calculation, change the workbook formulas too.
3. **Recommenders are deterministic rules, never an LLM.** Estimates must be reproducible
   and defensible in front of a client. LLM is optional narration only.
4. **Single mode and Chat mode stay untouched** unless explicitly in scope.
5. **Changes are additive; saved estimates self-heal on load** (migration pattern) — an
   estimate saved by an older version must still open.
6. **Any new session key that must survive a save/share/resume MUST be registered in
   `session_manager._get_initial_state()`.** `serialize_inputs()` only persists keys that
   exist there. This exact omission caused two separate P0 bugs (transition config blank
   after reopen in v1.64; roster reset to defaults in v1.65). See docs/architecture.md.

---

## 6. Open items & landmines

Ordered by how likely they are to bite you.

### 6.1 ⚠️ Azure migration is paused, and prod runs on a personal account
The tool is hosted on a personal Azure subscription. Migration to the Nagarro **"AMS DevOps"**
subscription was started and **paused at Phase 0** on a landing-zone policy (the platform
requires private-only storage), awaiting platform-team guidance. The deploy workflow was
already repointed to the migrated resource group `AB-ms-cost-estimator` (commit `da3804b`),
and the Container Apps environment referenced there is VNet-integrated. **Verify which
environment production is actually serving from before you trust any URL** — take the FQDN
from the deploy job's `App URL:` output.

### 6.2 ⚠️ `DEMO_SEED_DATA = True` in production
`config/settings.py` seeds a representative 4-skill demo scenario into empty fields on every
session (Monitoring, Cloud Operations, DevOps, Linux Administration), and pre-fills workload
on every newly added skill. It was a demo/testing aid.
**Turn it off before any real client use:** set `DEMO_SEED_DATA = False`.
Full removal = delete the flag, `modules/demo_seed.py`, and the `seed_demo_data()` call in
`main.py`.

### 6.3 ⚠️ `testing` is 2 commits ahead of `main` — production is missing a real fix
Not yet promoted to production:
- `3182ee8` **fix(rates): grade eligibility mapping** — L1=2.1, L2=2.2/2.3, L3=3.1/3.2/3.3,
  Architect=4.1, SDM=DELIVERY-ITIL. **Production is pricing off the older mapping.**
- `da3804b` chore(ci): repoint deploy workflow to the migrated RG + required tags.

Decide deliberately whether to promote these. Neither has been verified on staging by a human.

### 6.4 The email gate is not authentication
Anyone who can reach the URL can use the app; the `@nagarro.com` address is self-declared.
Token links (approval / share / orphan) intentionally bypass it so external recipients can
open them. If the tool ever carries commercially sensitive client data, enable Container Apps
Authentication (Microsoft Entra ID) — DEPLOY.md Step 7.

### 6.5 OIDC federated credentials are per-branch
A push on a branch with no matching federated credential fails Azure login with
`AADSTS700213`. Only `main` and `testing` are configured. Add one per new long-lived branch
(DEPLOY.md → Staging site), or just keep using `testing`.

### 6.6 The UI cannot be verified locally
Practice on this project has been: **do not rely on running the app locally** — verify on the
deployed staging app after pushing. `pytest` covers the engine and pure logic; Streamlit UI
behaviour is confirmed on staging. Budget for that loop.

### 6.7 Smaller items
- `assets/Transition_Framewark.png` is **untracked** in the working tree — commit it or
  delete it (note the spelling; `assets/transition framework.png` also exists).
- A "park a skill" include/exclude toggle was requested and **not built** — today a skill can
  only be deleted.
- The Shift Plan (tab 10) sits **after** the approval gate (tab 8), so a late roster edit is
  outside the approved snapshot. Accepted as an appendix; revisit if it becomes an issue.
- Several old feature branches (~25) are stale and could be pruned.

---

## 7. What was planned next

From the working backlog, in the order that had been agreed:

1. **Multi-component patching** — generalize `skill.patching` from servers-only to a
   component list (firewalls/routers for Network, VMs for Compute, instances for DB…),
   suggested by skill family, with neutral migration of existing `{num_servers}` data.
2. **Transition P3 — PPTX export** of the transition strategy.
3. **Transition P5b** — commercial treatment (recurring / one-time / absorb) for the
   multi-skill transition cost, mirroring what single mode already does.
4. **Severity/priority deepening** — fuller ITIL/SLA/presence-based staffing on top of the
   shipped P1–P4 classification. **Parked deliberately** — agree the taxonomy up front.
5. **Chat mode Phase 2** — conversational estimation on Azure OpenAI (blocked: the AOAI
   resource was never created; Chat currently runs on Groq).
6. **Azure setup wizard** — self-service provisioning UI. Design captured, **decision pending**.
7. **RFP response creator** — separate module: read an RFP → generate questions +
   Scope/Out-of-scope/Assumptions/Dependencies/Estimation → PPTX from a base template.
   Discussed, not started.
8. Deferred: what-if drivers in multi mode, a generic recommendation framework,
   allocate-mode volumes, per-skill transition.

---

## 8. Your first week

1. Get access items 1, 5, 6, 7 from §2. Nothing else matters until you have them.
2. `pip install -r requirements-dev.txt && pytest` — expect **208 passing**.
3. Read `docs/architecture.md`, then open `modules/calculations/engine.py` and follow
   `compute_multi_skill_model` end to end. That function is the product.
4. Open the staging app and build one estimate through all 10 multi-skill tabs. Download the
   Excel workbook and change an input in it — that round-trip is the tool's core promise.
5. Skim the top of `RESTORE.md` (v1.60 → v1.65). Recent history explains most of the code.
6. Make one trivial change on `testing`, push, watch it deploy to staging. Confirm the loop
   works for you before you need it under pressure.
7. Decide on §6.2 (demo seed) and §6.3 (unpromoted commits).

## 9. Troubleshooting

| Symptom | Likely cause |
|---|---|
| Cloud saves / drafts / approvals panel says "not configured" | `ESTIMATES_ACCOUNT_URL` unset, **or** the app's managed identity lacks Storage Blob Data Contributor on the container. A newly created staging app gets a **new** identity with no roles. |
| Rate card doesn't auto-load | Same identity issue, or `RATECARD_*` Variables unset. Falls back to manual upload. |
| Approval/share email not sent, link shown instead | `ACS_*` unset, or `APP_BASE_URL` unset (the app refuses to email a relative link). |
| Deploy fails at Azure login, `AADSTS700213` | No federated credential for that branch (§6.5). |
| Deploy fails on resource creation with a policy error | Missing required tags, or the private-storage landing-zone policy (§6.1). |
| Transition/roster tabs blank after reopening a saved estimate | A session key is missing from `_get_initial_state()` (guardrail §5.6). |
| Transition shows more skills than selected | Zero-workload skills leaking through — `split_skills_by_workload` should exclude them. |
| First load is slow | Scale-to-zero cold start. Expected. |

---

## 10. Document map

| File | What it is | Maintain it? |
|---|---|---|
| `README.md` | Product & flow overview | Yes — on user-visible change |
| `HANDOVER.md` | This file | Yes — on ownership/open-item change |
| `docs/architecture.md` | Module map, contracts, test map | Yes — on structural change |
| `DEPLOY.md` | Azure setup, env vars, CI/CD | Yes — when infra changes |
| `RESTORE.md` | Release changelog + rollback | Yes — one entry per release |
| `docs/*.md` | Per-feature design records | Add a status line when a feature ships |
| `COSTS.md` | Azure cost estimate | Occasionally |
| `UX_PLAN.md` | UX/design-system notes | Occasionally |
| `CLAUDE.md` | Conventions for AI-assisted work | Yes — keep guardrails current |
