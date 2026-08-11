# docs/ — design records

Two kinds of document live here:

- **Reference** — describes the system as it is today. Keep it current.
- **Design record** — captures a decision or a plan at a point in time. These are *not*
  updated as the feature evolves; they are marked with a status line and the release that
  shipped them. Treat the code and `RESTORE.md` as the truth about current behaviour.

| Document | Type | Status |
|---|---|---|
| [architecture.md](architecture.md) | Reference | ✅ **Current** (v1.65) — module map, engine contract, session-state rules, test map |
| [multi-skill-strategy.md](multi-skill-strategy.md) | Design record | ✅ **Shipped** — built out over v1.35–v1.57. Written before implementation; the blueprint, not the current state |
| [multi-skill-parity.md](multi-skill-parity.md) | Design record | ✅ **Shipped** — lifecycle parity delivered in v1.52–v1.54 (What-If in multi remains deferred) |
| [classification-estimation.md](classification-estimation.md) | Design record | ✅ **Shipped in v1.57** — classification-driven workload (P1–P4, AHT, routing) |
| [roster-designer-approach.md](roster-designer-approach.md) | Design record | ✅ **Shipped in v1.60** — Shift Plan P1 (coverage) + P2 (rotational calendar) |
| [transition-strategy-approach.md](transition-strategy-approach.md) | Design record | ✅ **Shipped in v1.61–v1.62**; Transition **Cost** followed in v1.63. P3 (PPTX export) not built |
| [azure-setup-wizard-approach.md](azure-setup-wizard-approach.md) | Design record | ⏸️ **Proposal — not started, decision pending** |

Elsewhere in the repo:

| Document | What it is |
|---|---|
| [../README.md](../README.md) | Product & flow overview — start here for *what the app does* |
| [../HANDOVER.md](../HANDOVER.md) | Ownership, access, environments, open items — start here if you're new |
| [../DEPLOY.md](../DEPLOY.md) | Azure setup, environment variables, staging, CI/CD |
| [../RESTORE.md](../RESTORE.md) | Release changelog v1.0 → v1.65 + rollback instructions |
| [../COSTS.md](../COSTS.md) | Azure cost estimate for light internal use |
| [../UX_PLAN.md](../UX_PLAN.md) | UX / design-system notes |
| [../CLAUDE.md](../CLAUDE.md) | Conventions and guardrails for AI-assisted work in this repo |
