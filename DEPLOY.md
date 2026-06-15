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

---

## Notes / tuning

- **Cold start:** first request after idle takes a few seconds (scale-from-zero). Set
  `--min-replicas 1` in the workflow if you want it always warm (you then pay while idle).
- **Region:** `centralindia` chosen for low latency; change `LOCATION` to your preference.
- **Cost:** scale-to-zero ≈ pay only for actual usage (vCPU-seconds + requests).
- **Revoke access instantly:** delete the federated credential
  (`az ad app federated-credential delete`) or the role assignment.
- **Run tests locally:** `pip install -r requirements-dev.txt && pytest`
