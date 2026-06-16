# Restoring to a Stable Version

This repository is tagged at each stable release. A git tag is an immutable pointer
to that exact snapshot, so you can always return to it no matter what changes later.

## Stable versions (latest first)
- **`v1.1`** — adds Step 2 per-role buffer % (default 20%) + the missing L3 Hrs column,
  and loads the rate card from **Azure Blob Storage** (managed identity) instead of a
  local upload. Builds on v1.0.
- **`v1.0`** — first production-ready release.

> In the commands below, replace `v1.0` with the version you want (e.g. `v1.1`).

## What `v1.0` contains
- Full Streamlit app: 9-step Ops effort/cost/pricing flow
- Per-server patching model + auto-derived activities (Scheduled Maintenance, RCA,
  Problem Management, Documentation & KB)
- Multi-location rate cards + multi-currency reporting (default India / INR)
- Excel + PDF export, in-session scenario comparison, what-if sliders,
  Raw/Rounded FTE toggle
- Single pure pipeline `engine.compute_full_model` (no display/export drift)
- Cross-step input persistence fix (no silent reset to defaults on Step 8)
- 39 passing tests
- Azure deploy: GitHub Actions OIDC → Container Apps (scale-to-zero)

> Tip: `git show v1.0` shows the tagged commit; `git tag -n` lists tags with messages.

---

## First, make sure you have the tag locally
```bash
git fetch --tags
git tag                 # should list: v1.0
```

## Option A — Just look at v1.0 (read-only, non-destructive)
```bash
git checkout v1.0       # detached HEAD — browse the exact files
git checkout main       # go back to the latest
```

## Option B — Branch off v1.0 (recommended for testing a rollback)
```bash
git checkout -b restore-v1 v1.0
# experiment / run / compare here; main is untouched
```

## Option C — Bring v1.0 files back as a NEW commit (safe rollback, keeps history)
Best when you want `main` to behave like v1.0 again **without** rewriting history:
```bash
git checkout main
git checkout v1.0 -- .          # overwrite working tree with v1.0 contents
git commit -m "Revert to stable v1.0"
git push                        # this also redeploys v1.0 to Azure
```

## Option D — Hard reset main to v1.0 (DESTRUCTIVE — discards newer commits)
Only if you truly want to erase everything after v1.0:
```bash
git checkout main
git reset --hard v1.0
git push --force origin main    # rewrites remote history; also redeploys v1.0
```

---

## Redeploying v1.0 to Azure
Deployment runs automatically on push to `main`, so **Option C or D pushes v1.0 and
redeploys it**. To deploy v1.0 *without* changing `main`, use Option B then run the
workflow from the `restore-v1` branch (GitHub → Actions → Run workflow → pick the branch).

---

## (Maintainers) how this tag was created / how to cut the next one
```bash
# create + push an annotated tag
git tag -a v1.0 -m "Stable Version 1"
git push origin v1.0

# next stable releases
git tag -a v1.1 -m "Stable Version 1.1"
git push origin v1.1
```
Optionally turn a tag into a downloadable GitHub Release:
GitHub repo → **Releases** → **Draft a new release** → choose tag `v1.0` → Publish.
