# Azure Setup Wizard — Approach & Decision Record

> Status: **DRAFT / not started.** Captured 2026-06-30 from a design discussion.
> Decision is **pending** the open questions at the bottom. No code written yet.

## Goal
Give the operator a **web UI (wizard)** that takes all the inputs needed to deploy this
application to a **fresh Azure subscription** and:
- provisions the Azure cloud components **automatically**,
- **guides the user to create the required secrets in GitHub** (so no secrets are
  hardcoded or stored by the tool),
- then **pushes/deploys the application** onto the freshly-provisioned cloud,
- ending with a working app URL.

The deploy button on the form should **enable only once all required inputs are valid**.

## Current state (today)
- App deploys via **GitHub Actions** (`.github/workflows/azure-deploy.yml`) to **Azure
  Container Apps** using **GitHub OIDC** (federated identity — no stored Azure password).
- The workflow already creates: resource group, **ACR** (Basic, admin-enabled), Container
  Apps **environment** + **app**, and assigns a **system-assigned managed identity**.
- **Manual / one-time today** (the gap to automate): the OIDC app registration + federated
  credential, the GitHub Variables/Secrets, the **storage account + blob containers**, the
  managed-identity → **Storage Blob Data role** assignment, and **ACS email** setup.

## Resource inventory the running app needs
| Resource | Purpose |
|---|---|
| Resource group | container for everything |
| Azure Container Registry (or a public registry) | stores the built image |
| Container Apps environment + app (scale-to-zero) | runs the Streamlit app on port 8000 |
| System-assigned managed identity + `Storage Blob Data Contributor` | app → Blob, no secrets |
| Storage account + blob containers | rate card, drafts, estimates, approvals, orphans |
| Azure Communication Services (Email) — optional | approval emails |
| GitHub OIDC app registration + federated credential | CI deploy with no stored secrets |
| GitHub Actions Variables/Secrets | IDs + config the workflow injects |
| Groq API key (external, free) — optional | "chat to estimate" |

App env vars consumed: `RATECARD_ACCOUNT_URL/CONTAINER/BLOB`, `ESTIMATES_ACCOUNT_URL/CONTAINER`,
`APP_BASE_URL`, `ACS_ENDPOINT/SENDER/CONNECTION_STRING`, `GROQ_API_KEY/MODEL`,
`AZURE_CLIENT_ID/TENANT_ID/SUBSCRIPTION_ID`.

## Chosen direction: custom web Setup Wizard
A small **Streamlit wizard** (same stack as the product), run **once, locally or in Azure
Cloud Shell** (it can't run in the not-yet-existing target cloud).

### Division of labor (the key design decision)
- **Wizard** (runs locally, signs into Azure via **device-code** auth): create resource group,
  storage + blob containers, optional ACS email, the **OIDC app registration + federated
  credential**, and the role grants. Uses the **Azure SDK for Python** (no `az` install needed).
- **User** (guided by the wizard): paste the shown **Variables** (AZURE_* IDs, storage URLs)
  and **Secrets** (ACS connection string, Groq key) into GitHub → Settings → Secrets. The
  wizard never stores or hardcodes a secret.
- **GitHub Actions** (existing pipeline): build the image, push it, create/refresh the
  Container App, inject env vars, and (proposed enhancement) **auto-assign the app's Blob
  role** so today's one manual step disappears.

Net: **wizard = provisioning + guidance; GitHub Actions = build + deploy; user = creates the
secrets.** Matches "no secrets hardcoded, rest automatic."

### Wizard screens
1. **Prerequisites** — needs: Azure subscription where you're Owner, a fork of the repo, ~10 min.
2. **Sign in to Azure** — device-code login; pick subscription + region + naming prefix;
   **verify permissions** up front (create resources? register an app?).
3. **Choose options** — Email (ACS managed domain) on/off; Chat (Groq) on/off (+ free-key link).
4. **Review & Deploy** — Deploy button disabled until all inputs valid; show what's created + cost.
5. **Provisioning** — live progress; idempotent (safe to re-run).
6. **Create your GitHub secrets** — checklist of Variables/Secrets with copy buttons + settings
   URL; "I've added them" confirm.
7. **Deploy the app** — trigger the pipeline; link the Actions run; show the final app URL.
8. **Done** — URL, summary, teardown button.

### Security model
- No stored secrets: Azure auth is an in-memory device-code token; ACS conn string / Groq key
  are shown once for the user to paste into GitHub Secrets; deploy uses OIDC (only non-secret
  IDs in GitHub). Nothing sensitive lands in the repo.

## Alternatives considered
- **"Deploy to Azure" button → Azure Portal form (`createUiDefinition.json`) + Bicep/ARM +
  public image.** Native validated form + Deploy button, no hosting/tooling/CI needed for a
  fresh stand-up. Lower effort / very robust, BUT can't create the GitHub OIDC trust or set
  GitHub variables (not needed if using a public image), and needs a **public app image**
  published from CI. Strong option if the wizard's GitHub-CI wiring isn't required.
- **Pure idempotent bash script** (`az` + `gh`) run in Cloud Shell. Simplest to write; not a
  "front-end with a button," so it doesn't match the stated UX.

## What we'd build (custom-wizard path)
- `setup/wizard.py` (Streamlit wizard) + `setup/provision.py` (Azure SDK orchestration:
  resource/storage/appcontainers/communication + Microsoft Graph for OIDC) + `setup/requirements.txt`
- deploy-workflow enhancement: auto-assign the app's Blob role
- rewritten `DEPLOY.md`: run the wizard → add shown secrets → done
- companion teardown (delete RG + app registration)
- no secrets committed

## Risks / realities
1. **Permissions** — app registration + role assignment need **Owner + app-registration
   rights**. Personal/trial subscription: fine. **Nagarro org tenant**: app registration may be
   admin-blocked → wizard must detect and fall back to printed manual-OIDC steps. *Biggest
   "fully automatic?" factor.*
2. **Runs locally / Cloud Shell**, not in the cloud (chicken-and-egg). Cloud Shell is smoothest.
3. **Can't test live Azure SDK calls without a real subscription** — first run iterated
   together; build verbose + idempotent + dry-run + teardown.
4. **ACS custom email domain** isn't automatable (needs DNS) — managed domain only, or skip.
5. **Cost (free reality):** Container Apps scale-to-zero ≈ free; Storage ≈ pennies; **ACR
   Basic ≈ $5/mo** (avoidable via public registry); ACS email pay-per-send (small free allowance).

## OPEN QUESTIONS — to decide before building
1. **Tenant/permissions:** personal/trial (full auto) vs Nagarro org (needs admin / manual-OIDC
   fallback) vs unsure (wizard probes & adapts).
2. **GitHub wiring:** guide-only (user pastes secrets — recommended, no GitHub token) vs
   auto-set via a short-lived GitHub PAT vs offer both.
3. **Is GitHub even needed?** Alternative: the wizard builds + deploys the image itself (e.g.
   ACR Build, no GitHub) so there's no GitHub step at all — vs keep GitHub Actions as the
   build/deploy engine.
4. **Where it runs:** local vs Azure Cloud Shell (recommended).
5. **Registry:** keep ACR (~$5/mo) vs switch to a free public registry (ghcr.io).
6. **Scope:** throwaway helper just for you vs a polished reusable tool for others.
7. **Final UX choice:** custom Streamlit wizard vs the "Deploy to Azure" portal-button approach.

## Next step
Decide the open questions above, then build the chosen path (default leaning: custom Streamlit
wizard, guide-only GitHub, runs in Cloud Shell, public registry to stay ~free).
