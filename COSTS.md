# Cost & Tool Stack

> Approximate monthly cost for **light internal use** (a handful of users, occasional
> sessions), **Central India** region, standard Azure list prices. Actual cost depends
> on usage and current rates — confirm in **Azure Portal → Cost Management**.
> A new **free Azure account** also includes ~$200 credit for 30 days + 12 months of
> selected free services, which covers most/all of this initially.

## Azure components

| Component | Paid / Free | Free allowance (per month) | Est. cost (light use) | Notes |
|---|---|---|---|---|
| **Container Apps** (Consumption, scale-to-zero) | Free within grant | 180,000 vCPU-sec, 360,000 GiB-sec, 2M requests | **~$0** | Idle = 0 replicas = no compute charge. Light interactive use stays inside the free grant. |
| **Container Registry (ACR Basic)** | **Paid** | none (no free tier) | **~$5/mo** (~₹400) | Fixed daily charge (~$0.17/day). Stores the app image. **This is the main standing cost** — charged even when the app is shut down. |
| **Log Analytics** (logs for Container Apps) | Free within grant | first 5 GB ingested + 31-day retention | **~$0** | A near-idle app ingests very little. |
| **Blob Storage** (rate card + saved calculations + drafts/orphans/approvals) | Paid (tiny) | — (pay per GB + transactions) | **~$0.01** | Data is kilobytes. Effectively free. |
| **Communication Services – Email** | Paid (per email) | — | **~$0** | ~ $0.00027 per email + tiny data. Approval + draft-cleanup emails; negligible at low volume. |
| **Microsoft Entra ID** (sign-in, if enabled) | **Free** | Free tier covers basic auth | **$0** | Not enabled yet; the app uses a self-declared **Nagarro-email gate** (no Azure cost). Free tier is enough if you later require real sign-in. |
| **Bandwidth / egress** | Free within grant | first 100 GB/mo egress free | **~$0** | App responses are small. |

### Bottom line
- **Running lightly: ≈ $5/month (~₹400)**, almost entirely the **ACR Basic** fixed fee.
- Everything else is **~$0** at this usage (within free grants / pay-per-use pennies).
- **Shutting the app down** (Scale → Max replicas 0) saves compute — but compute is already ~$0 when idle, so the bill stays ~$5/mo (ACR) regardless.
- **To reach $0**, you'd delete the resource group (loses Blob data) or move the image to **GitHub Container Registry** (free) instead of ACR — a future optimization.

## Application / tool stack (all free, open-source)

| Layer | Tech | License | Cost |
|---|---|---|---|
| UI / app framework | **Streamlit** | Apache-2.0 | Free |
| Language / runtime | **Python 3.12** | PSF | Free |
| Data | **pandas**, **openpyxl** | BSD / MIT | Free |
| Charts | **plotly** | MIT | Free |
| PDF export | **reportlab** | BSD | Free |
| Azure SDKs | **azure-identity**, **azure-storage-blob**, **azure-communication-email** | MIT | Free (SDKs; the Azure *services* are billed above) |
| Tests | **pytest** | MIT | Free |
| Container base | **python:3.12-slim** (Docker) | PSF/Docker | Free |
| Source control | **GitHub** repo | — | Free |
| CI/CD | **GitHub Actions** | — | Free: 2,000 min/mo (private repos); unlimited for public. Each deploy ≈ 5–8 min. |
| Hosting | **Azure Container Apps** | — | See table above |

## Keeping costs low — checklist
- Leave **scale-to-zero** on (`min-replicas = 0`) — already configured.
- Only the **ACR Basic** (~$5/mo) is unavoidable while the image lives in Azure.
- Watch spend in **Azure Portal → Cost Management → Cost analysis** (filter by resource group `rg-ops-estimator`).
- Set a **Budget + alert** (Cost Management → Budgets) to get emailed if spend exceeds, say, $10/mo.
