# Deploying to Azure (Container Apps, scale-to-zero) — secure, no shared credentials

Deploys via **GitHub Actions using OIDC federated identity** — **no secrets** stored,
nothing shared. GitHub gets a short-lived token at deploy time that Azure validates
against a trust *you* create. Do the one-time setup once; afterwards every `git push`
to `main` deploys automatically.

- **Host:** Azure Container Apps, **min-replicas = 0** (runs only on request)
- **Azure login:** `rjabhi77@gmail.com` (your Azure account / subscription owner)
- **GitHub repo trusted:** `ruchulovsab-coder/Cost-Calculator` (branch `main`)

Use these **direct links** instead of hunting through menus.

---

## STEP 1 — Open Cloud Shell
Go to **https://shell.azure.com** → sign in as `rjabhi77@gmail.com` → choose **Bash**.
If asked about storage, pick **"No storage account required"** (or create one — either is fine).

## STEP 2 — Confirm a subscription exists
```bash
az account show --query id -o tsv
```
Prints a GUID = good. Blank/error = subscription not ready yet.

## STEP 3 — Register features (wait for DONE, ~2 min)
```bash
az provider register -n Microsoft.App --wait
az provider register -n Microsoft.OperationalInsights --wait
az provider register -n Microsoft.ContainerRegistry --wait
echo "DONE"
```

## STEP 4 — Create identity + trust (paste the whole block)
> Needs rights to create app registrations + role assignments. On a personal free
> Azure account you're Owner, so this works. On a corporate tenant an admin may need to run it.

```bash
REPO="ruchulovsab-coder/Cost-Calculator"
RG="rg-ops-estimator"
LOCATION="centralindia"

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

az group create -n "$RG" -l "$LOCATION"
APP_ID=$(az ad app create --display-name "github-cost-calculator-oidc" --query appId -o tsv)
az ad sp create --id "$APP_ID"

cat > fic.json <<EOF
{ "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:${REPO}:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"] }
EOF
az ad app federated-credential create --id "$APP_ID" --parameters fic.json

az role assignment create --assignee "$APP_ID" --role Contributor \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RG}"

echo "================ COPY THESE THREE ================"
echo "AZURE_CLIENT_ID=$APP_ID"
echo "AZURE_TENANT_ID=$TENANT_ID"
echo "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"
echo "================================================="
```

## STEP 5 — Paste the 3 IDs into GitHub (Variables, not Secrets)
Direct link: **https://github.com/ruchulovsab-coder/Cost-Calculator/settings/variables/actions**
Click **New repository variable** and add each (value = the part after `=`):

| Name | Value |
|------|-------|
| `AZURE_CLIENT_ID` | from Step 4 |
| `AZURE_TENANT_ID` | from Step 4 |
| `AZURE_SUBSCRIPTION_ID` | from Step 4 |

These are identifiers, not credentials — useless without the trust you created.

## STEP 6 — Run the deployment
Direct link: **https://github.com/ruchulovsab-coder/Cost-Calculator/actions**
→ click **"Deploy to Azure Container Apps"** → **Run workflow** → green **Run workflow**.
The **test** job runs first, then **deploy** (~5–8 min). The deploy job's last step prints
**`App URL:`** — that's your live app. (Or push to `main` to trigger it.)

## STEP 7 — Require sign-in (after first deploy)
**https://portal.azure.com** → search **Container Apps** → open `nagarro-ops-estimator`
→ left menu **Authentication** → **Add identity provider** → **Microsoft** →
**Create new app registration** → set **Require authentication** → **Add**.

> **Note — this is the real access control.** The app *also* has a built-in
> **Nagarro-email gate** (a `@nagarro.com` address entered on first load) that owns your
> drafts/versions and fills *Prepared By*, but that email is **self-declared, not
> verified** — a *"find my work"* key, **not** a security boundary. Enable Azure
> Authentication above (Microsoft Entra ID) if you need verified sign-in.

---

## STEP 8 (optional) — Central rate card in Azure Blob Storage

Lets the app load the rate card from the cloud (no per-session upload). Access uses
the Container App's **managed identity** — no keys or connection strings in the app.

Run in **Cloud Shell (Bash)** as `rjabhi77@gmail.com`:

```bash
RG=rg-ops-estimator
APP=nagarro-ops-estimator
LOC=centralindia
STORAGE="opsratecard$RANDOM"      # 3-24 lowercase alphanumeric, globally unique
CONTAINER=ratecards
BLOB=genus_rate_card.xlsx

# 1) Private storage account + container
az storage account create -n "$STORAGE" -g "$RG" -l "$LOC" \
  --sku Standard_LRS --kind StorageV2 --allow-blob-public-access false
KEY=$(az storage account keys list -n "$STORAGE" -g "$RG" --query "[0].value" -o tsv)
az storage container create --account-name "$STORAGE" -n "$CONTAINER" --account-key "$KEY"

# 2) Upload your rate card. First click Cloud Shell's "Upload/Download files" button
#    to upload genus_rate_card.xlsx into the shell, then:
az storage blob upload --account-name "$STORAGE" -c "$CONTAINER" -n "$BLOB" \
  -f ./genus_rate_card.xlsx --account-key "$KEY" --overwrite

# 3) Ensure the app has a managed identity, then grant it READ access to the storage
PID=$(az containerapp identity assign -n "$APP" -g "$RG" --system-assigned --query principalId -o tsv)
ACCT_ID=$(az storage account show -n "$STORAGE" -g "$RG" --query id -o tsv)
az role assignment create --assignee "$PID" --role "Storage Blob Data Reader" --scope "$ACCT_ID"

# 4) Print the values to add as GitHub repo Variables
echo "RATECARD_ACCOUNT_URL = https://$STORAGE.blob.core.windows.net"
echo "RATECARD_CONTAINER   = $CONTAINER"
echo "RATECARD_BLOB        = $BLOB"
```

Then add those 3 as **repository Variables** (same page as before):
**https://github.com/ruchulovsab-coder/Cost-Calculator/settings/variables/actions**
→ `RATECARD_ACCOUNT_URL`, `RATECARD_CONTAINER`, `RATECARD_BLOB`.

Re-run the deploy (Actions → Run workflow). The pipeline injects these env vars and
the app auto-loads the rate card from Blob. Update the rate card anytime by uploading
a new blob of the same name (step 2) — no redeploy needed (app re-reads within ~10 min,
or users click **🔄 Reload from cloud**).

> To update the rate card via key-free auth instead, grant yourself
> **Storage Blob Data Contributor** and use `--auth-mode login` on the upload.

---

## STEP 9 (optional) — Saved calculations store (cloud, versioned)

Lets users save named, versioned calculations and reopen them later. Uses the same
storage account, a **separate `estimates` container**, and the app's **managed
identity** with **write** access. Shared team repository.

### Portal
1. Open your **Storage account** → **Containers** → **+ Container** → name `estimates` → **Create**.
2. Open the **estimates** container → **Access Control (IAM)** (left menu inside the container)
   → **+ Add → Add role assignment**.
3. Role: **Storage Blob Data Contributor** → **Next**.
4. **Assign access to: Managed identity** → **+ Select members** → type **Container App**
   → pick **nagarro-ops-estimator** → **Select** → **Review + assign**.
   *(Scoping the role to the `estimates` container keeps the rate-card container read-only.)*
5. Add **two repository Variables** at
   **https://github.com/ruchulovsab-coder/Cost-Calculator/settings/variables/actions**:

   | Name | Value |
   |------|-------|
   | `ESTIMATES_ACCOUNT_URL` | `https://<your-storage-account>.blob.core.windows.net` |
   | `ESTIMATES_CONTAINER` | `estimates` |

6. Re-run the deploy (Actions → Run workflow).

Now the sidebar shows **📁 Saved Calculations** — *Save current calculation* (stores a
new timestamped version under the Step-1 Customer/RFP name) and *Open saved calculation*
(browse projects → versions → load). Until configured, that panel says cloud storage
isn't set up and you use the JSON **Scenarios** instead.

> The **same `estimates` container** also stores the **approval** records
> (`__approvals__/…`), the **drafts** auto-saved per user (`__drafts__/…`) and their
> **orphans** (`__orphans__/…`). One container, one role assignment, covers all of them.

> Equivalent CLI (Cloud Shell): create the container, then
> `az role assignment create --assignee <app-principalId> --role "Storage Blob Data Contributor" --scope <estimates-container-resource-id>`.

---

## STEP 10 (optional) — Approval & draft-cleanup emails (Azure Communication Services)

Powers the **approval workflow** (Step 10) and the **🧹 draft clean-up** deletion links.
Without these the app still works and simply **shows a copyable link** instead of sending
an email.

1. Create an **Azure Communication Services** resource + an **Email Communication
   Service** with a verified sender (an Azure-managed subdomain is simplest). Note the
   sender address, e.g. `DoNotReply@<your-domain>`.
2. Add these **repository Variables** at
   **https://github.com/ruchulovsab-coder/Cost-Calculator/settings/variables/actions**:

   | Name | Value |
   |------|-------|
   | `ACS_ENDPOINT` | `https://<acs-resource>.communication.azure.com` (managed-identity auth) |
   | `ACS_SENDER` | the verified sender address |
   | `APP_BASE_URL` | `https://nagarro-ops-estimator.<...>.azurecontainerapps.io` (your live URL) |

   *Either* grant the Container App's **managed identity** access to the ACS resource and
   use `ACS_ENDPOINT`, *or* skip the identity step and set `ACS_CONNECTION_STRING` as a
   **Secret** instead of `ACS_ENDPOINT`.
3. **`APP_BASE_URL` is required for clickable links.** Without it the app refuses to send
   a dead relative URL and shows the link to copy instead — so set it for both approval
   and cleanup emails to work end to end.
4. Re-run the deploy (Actions → Run workflow).

---

## Staging site (the `testing` branch)

There are two live, independent deployments driven by one workflow:

| Branch | Container App | Purpose |
|--------|---------------|---------|
| `main` | `nagarro-ops-estimator` | **Production** — unchanged behaviour |
| `testing` | `nagarro-ops-estimator-test` | **Staging** — all new development |

- **How it works:** the deploy job derives its target from the pushed branch. `main` →
  production; anything else (i.e. `testing`) → `<name>-test`. Both share the same Container
  Apps environment + ACR, but are separate apps with their own URLs and scale independently
  (both scale-to-zero, so idle staging costs ≈ nothing).
- **Isolation:** staging gets its own `APP_BASE_URL` (its own FQDN, so approval/orphan links
  point to staging, never prod) and its estimates container is suffixed `-test`, so test
  drafts/estimates/approvals never mix with production data.
- **First staging deploy caveat:** the new app's system-assigned identity has **no Storage
  Blob role yet** (that grant needs Owner and is manual — see step 5 above). Until granted,
  staging's cloud drafts + rate-card-from-blob degrade gracefully (disabled); the app still
  runs. Grant `Storage Blob Data Reader`/`Contributor` to the `-test` app's identity to enable
  them, and create the `<container>-test` blob container.
- **Promote to production:** merge `testing` → `main` and push — production redeploys.
- **Dev loop:** push to `testing` → staging redeploys; validate on the `-test` URL first.

---

## Notes / tuning

- **Cold start:** first request after idle takes a few seconds (scale-from-zero). Set
  `--min-replicas 1` in the workflow if you want it always warm (you then pay while idle).
- **Region:** `centralindia` chosen for low latency; change `LOCATION` to your preference.
- **Cost:** scale-to-zero ≈ pay only for actual usage (vCPU-seconds + requests).
- **Revoke access instantly:** delete the federated credential
  (`az ad app federated-credential delete`) or the role assignment.
- **Run tests locally:** `pip install -r requirements-dev.txt && pytest`
