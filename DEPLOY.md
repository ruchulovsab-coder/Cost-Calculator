# Deploying to Azure (Container Apps, scale-to-zero) — secure, no shared credentials

This app deploys via **GitHub Actions using OIDC federated identity**. There are
**no secrets** stored in the repo and nothing is shared with anyone: GitHub gets a
short-lived token at deploy time that Azure validates against a trust *you* create.

- **Host:** Azure Container Apps, **min-replicas = 0** (runs only on request; ~no cost when idle)
- **Auth:** Microsoft Entra ID sign-in (step 7)
- **Identity used:** GitHub `@ruchulovsab-coder` / Azure `ruchulovsab@gmail.com`
- **Repo trusted:** `ruchulovsab-coder/Cost-Calculator` (branch `main`)

You only do the one-time setup below **once**. After that, every `git push` to `main`
deploys automatically.

---

## One-time setup (run in Azure Cloud Shell — Bash)

Open **https://shell.azure.com**, choose **Bash**. You're already signed in there as
`ruchulovsab@gmail.com`, so no passwords are typed and nothing leaves Azure.

> Requires that your account can create app registrations and role assignments. If a
> command returns an authorization error, your Azure admin needs to run these (or grant
> you Owner on the subscription / "Application Developer" in Entra ID).

```bash
# ---- settings ----
REPO="ruchulovsab-coder/Cost-Calculator"
RG="rg-ops-estimator"
LOCATION="centralindia"        # change if you prefer another region
APP_DISPLAY="github-cost-calculator-oidc"

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

# 1) Resource group that will hold everything
az group create -n "$RG" -l "$LOCATION"

# 2) App registration + service principal (the identity GitHub will assume)
APP_ID=$(az ad app create --display-name "$APP_DISPLAY" --query appId -o tsv)
az ad sp create --id "$APP_ID"

# 3) Federated credential: trust GitHub Actions on this repo's main branch
cat > fic.json <<EOF
{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:${REPO}:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}
EOF
az ad app federated-credential create --id "$APP_ID" --parameters fic.json

# (optional) also allow manual "Run workflow" from the Actions tab:
cat > fic-dispatch.json <<EOF
{
  "name": "github-workflow-dispatch",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:${REPO}:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}
EOF

# 4) Give that identity Contributor — scoped ONLY to this resource group
az role assignment create \
  --assignee "$APP_ID" \
  --role Contributor \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RG}"

# 5) Print the three NON-secret IDs to paste into GitHub
echo "----------------------------------------------------"
echo "AZURE_CLIENT_ID       = $APP_ID"
echo "AZURE_TENANT_ID       = $TENANT_ID"
echo "AZURE_SUBSCRIPTION_ID = $SUBSCRIPTION_ID"
echo "----------------------------------------------------"
```

## 6) Add the three IDs to GitHub (as Variables, not Secrets)

GitHub repo → **Settings → Secrets and variables → Actions → Variables tab →
New repository variable**, add all three:

| Name | Value |
|------|-------|
| `AZURE_CLIENT_ID` | from step 5 |
| `AZURE_TENANT_ID` | from step 5 |
| `AZURE_SUBSCRIPTION_ID` | from step 5 |

These are identifiers, not credentials — useless without the trust you created.

## Deploy

```bash
git push            # to main  -> triggers .github/workflows/azure-deploy.yml
```

…or GitHub → **Actions → Deploy to Azure Container Apps → Run workflow**.

The job prints the app URL at the end (also: Azure Portal → Container Apps →
`nagarro-ops-estimator` → Application Url).

## 7) Require Nagarro / Entra ID sign-in (after the first deploy)

Easiest via Portal: **Container App → Settings → Authentication → Add identity
provider → Microsoft → Entra ID** → *create new app registration* → set
"Restrict access: Require authentication" → unauthenticated requests → **Return HTTP 302
(login)**. Save. Now only signed-in accounts can open the tool.

---

## Notes / tuning

- **Cold start:** first request after idle takes a few seconds (scale-from-zero). Set
  `--min-replicas 1` in the workflow if you want it always warm (you then pay while idle).
- **Region:** `centralindia` chosen for low latency; change `LOCATION` to your preference.
- **Cost:** scale-to-zero ≈ pay only for actual usage (vCPU-seconds + requests).
- **Revoke access instantly:** delete the federated credential
  (`az ad app federated-credential delete`) or the role assignment.
- **Run tests locally:** `pip install -r requirements-dev.txt && pytest`
