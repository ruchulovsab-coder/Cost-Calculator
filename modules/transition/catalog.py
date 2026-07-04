"""The transition framework encoded as data (not code).

Transcribes assets/transition framework.png — "Operational Establishment & Stabilization":
6 ITIL-aligned TRANSITION phases (Service Strategy → Design → Transition → Operations), milestones
M1–M4 + Go-Live, per-phase objectives/deliverables/entry-exit/risks/dependencies/responsibilities, a
Customer/Nagarro RACI, and per-skill KT→Shadow→Reverse-Shadow→Stabilization activity templates.
Steady-State Service Delivery & CSI is BAU — it begins AFTER the transition completes (M4), so it is
NOT a transition phase and is not on the Gantt. Everything downstream (builder, UI, Excel) reads from
here, so the methodology stays faithful and editable in one place."""
from __future__ import annotations

# ── Transition phases (ordered) ───────────────────────────────────────────────
# milestone marks the GATE at the end of the phase. Transition ends at Stabilization (M4); the
# engagement then enters Steady-State Service Delivery & CSI (BAU — deliberately NOT a phase here).
PHASES = [
    {"key": "assessment", "name": "Assessment & Discovery", "band": "Service Strategy",
     "default_weeks": 2, "milestone": None},
    {"key": "initiation", "name": "Initiation & Planning", "band": "Service Design",
     "default_weeks": 2, "milestone": "M1"},
    {"key": "knowledge_transition", "name": "Knowledge Transition", "band": "Service Transition",
     "default_weeks": 4, "milestone": "M2"},
    {"key": "shadow", "name": "Shadow Support", "band": "Service Transition",
     "default_weeks": 4, "milestone": "M3"},
    {"key": "reverse_shadow", "name": "Reverse Shadow Support", "band": "Service Transition",
     "default_weeks": 4, "milestone": "Go-Live"},
    {"key": "stabilization", "name": "Stabilization", "band": "Service Operations",
     "default_weeks": 4, "milestone": "M4"},
]

# BAU destination after the transition completes (M4) — shown as a note, not a Gantt phase.
POST_TRANSITION = {"name": "Steady State Service Delivery & Continuous Improvement",
                   "band": "Service Operations"}

MILESTONE_GATES = {
    "M1": "Transition Plan & Scope baselined",
    "M2": "Documentation repository reviewed & Customer approval",
    "M3": "Shadow review & validation & Customer approval",
    "Go-Live": "Sign-off to commence services (Reverse Shadow complete)",
    "M4": "KPIs & SLAs baselined for stabilization (penalties waived)",
}

# The continuous foundation band under all phases (from the framework).
FOUNDATION = "Knowledge Management, Tools & Processes"

# ── Per-phase detail ──────────────────────────────────────────────────────────
PHASE_DETAIL = {
    "assessment": {
        "objectives": ["Baseline the current-state services, scope and landscape",
                       "Assess software/hardware, tools, processes and documentation readiness"],
        "deliverables": ["Baselined Transition Plan & Scope", "Current-state assessment report"],
        "entry": ["Signed contract / SOW", "Nominated stakeholders from both parties"],
        "exit": ["Transition scope baselined and agreed"],
        "risks": ["Incomplete or outdated documentation", "Delayed access to environments/tools"],
        "dependencies": ["Customer provides access to systems, tools and SMEs"],
        "customer_resp": ["Provide landscape information, SMEs and access",
                          "Nominate service/application owners"],
        "nagarro_resp": ["Conduct discovery workshops", "Assess tools, processes and documentation"],
    },
    "initiation": {
        "objectives": ["Establish governance, delivery and communication framework",
                       "Set up transition team and infrastructure"],
        "deliverables": ["Service Delivery Plan", "Detailed Transition Plan", "Governance framework"],
        "entry": ["Assessment complete", "Transition scope baselined"],
        "exit": ["Transition Plan & governance signed off (M1)"],
        "risks": ["Resource ramp-up delays", "Tooling/access provisioning delays"],
        "dependencies": ["Customer approves governance model and access requests"],
        "customer_resp": ["Approve governance & communication plan", "Provision access/tooling"],
        "nagarro_resp": ["Mobilise transition team", "Set up delivery infrastructure & plans"],
    },
    "knowledge_transition": {
        "objectives": ["Transfer functional & technical knowledge for each in-scope service",
                       "Validate documentation, SOPs and runbooks"],
        "deliverables": ["Documentation repository", "Validated SOPs/runbooks", "KT tracker",
                         "Customer approval of KT completeness (M2)"],
        "entry": ["Transition Plan approved", "Access provisioned", "KT schedule agreed"],
        "exit": ["KT sessions complete & documentation approved by Customer"],
        "risks": ["Knowledge gaps / SME unavailability", "Undocumented tribal knowledge"],
        "dependencies": ["Incumbent/vendor & Customer SMEs available for KT sessions"],
        "customer_resp": ["Provide SMEs & incumbent knowledge", "Review & approve documentation"],
        "nagarro_resp": ["Conduct functional/technical KT", "Build & validate documentation repository"],
    },
    "shadow": {
        "objectives": ["Nagarro observes incumbent/vendor delivering live operations",
                       "Analyse incidents, service requests and processes hands-on"],
        "deliverables": ["Shadow observation log", "Gap analysis", "Review & validation report (M3)"],
        "entry": ["KT complete & documentation approved"],
        "exit": ["Shadow review validated & approved by Customer"],
        "risks": ["Limited live incident volume during window", "Incumbent cooperation"],
        "dependencies": ["Incumbent/vendor continues primary support during shadow"],
        "customer_resp": ["Facilitate access to live operations", "Review shadow outcomes"],
        "nagarro_resp": ["Observe & analyse live operations", "Identify and close gaps"],
    },
    "reverse_shadow": {
        "objectives": ["Nagarro performs operations with incumbent/vendor reviewing",
                       "Demonstrate production readiness (no SLAs applicable yet)"],
        "deliverables": ["Production readiness checklist", "Sign-off to commence services (Go-Live)"],
        "entry": ["Shadow validated", "Production readiness criteria agreed"],
        "exit": ["Customer sign-off to commence services (Go-Live)"],
        "risks": ["Readiness gaps surfacing late", "Access/tooling not fully cut over"],
        "dependencies": ["Incumbent/vendor available to review & backstop"],
        "customer_resp": ["Review readiness", "Provide Go-Live sign-off"],
        "nagarro_resp": ["Operate services with review", "Complete production readiness checks"],
    },
    "stabilization": {
        "objectives": ["Operate as an independent team", "Monitor, review & report KPIs and SLAs"],
        "deliverables": ["KPI/SLA baseline report (penalties waived)", "Stabilization exit report (M4)"],
        "entry": ["Go-Live sign-off complete"],
        "exit": ["KPIs/SLAs stable & baselined; ready for steady state"],
        "risks": ["Volume spikes post cut-over", "Hidden defects surfacing"],
        "dependencies": ["Customer confirms KPI/SLA baselines"],
        "customer_resp": ["Review KPI/SLA reports", "Confirm stabilization exit"],
        "nagarro_resp": ["Run independent operations", "Baseline & report KPIs/SLAs"],
    },
}

# ── Per-skill activity templates ({skill} is filled by the builder) ───────────
# Each skill's stage plan = a COMMON operational-process backbone (PROCESS_STAGE_ACTIVITIES,
# woven into every stage so every skill covers the same ITIL processes) + a TECHNICAL layer
# (FAMILY_STAGE_TEMPLATES per technology family, or this generic set for unmapped skills).
STAGE_KEYS = ("knowledge_transition", "shadow", "reverse_shadow", "stabilization")

# Generic technical layer — fallback when a skill name maps to no known family.
SKILL_STAGE_TEMPLATES = {
    "knowledge_transition": [
        "Functional & technical knowledge transfer for {skill}",
        "Review {skill} documentation, SOPs and runbooks",
        "Inventory {skill} components and configuration baselines",
    ],
    "shadow": [
        "Analyse recurring {skill} technical issues and process gaps",
    ],
    "reverse_shadow": [
        "{skill} production readiness checks and validation",
    ],
    "stabilization": [
        "Operational handover of {skill} technical runbooks and known errors",
    ],
}

# ── Operational process framework (ITIL) — the SAME set is covered for every skill ────
# Reference list (labels shown for documentation/tests); the actual activities are woven
# into the stages via PROCESS_STAGE_ACTIVITIES below.
OPERATIONAL_PROCESS_AREAS = [
    ("processes", "Service processes & workflows"),
    ("incident", "Incident Management"),
    ("mim", "Major Incident Management"),
    ("problem", "Problem Management"),
    ("change", "Change Management"),
    ("request", "Service Request Fulfilment"),
    ("access", "Access Management"),
    ("monitoring", "Monitoring & Event Management"),
    ("patching", "Patching & Maintenance"),
    ("escalation", "Escalation & Communication"),
    ("cmdb", "Configuration / Asset (CMDB)"),
    ("reporting", "Reporting & Governance"),
]

# Common operational-process backbone, woven into each stage (understand → observe → perform
# → own). {skill}-templated so it reads domain-specific for each team's KT.
PROCESS_STAGE_ACTIVITIES = {
    "knowledge_transition": [
        "Understand the customer's {skill} service processes & workflows (as-is operating model, roles, hand-offs)",
        "Understand {skill} incident management — categories, priorities, SLAs and the customer's incident landscape",
        "Understand {skill} major incident management (MIM) — triggers, bridge/war-room, roles and communications",
        "Understand {skill} problem management — RCA approach and known-error database",
        "Understand {skill} change management — RFC/CAB, approvals and change/maintenance windows",
        "Understand {skill} service request catalogue and fulfilment workflow",
        "Understand {skill} access management — joiners/movers/leavers and privileged-access approvals",
        "Understand {skill} monitoring & event management — tooling, alerts and event-to-incident flow",
        "Understand {skill} patching & maintenance process — cycle, approvals and rollback",
        "Understand {skill} escalation & communication protocols — functional/hierarchical paths and contacts",
        "Understand {skill} configuration/asset data (CMDB) — records, ownership and update process",
        "Understand {skill} reporting & governance — KPIs/SLAs, cadence and review forums",
    ],
    "shadow": [
        "Observe incumbent handling {skill} incidents, service requests and access requests",
        "Observe a {skill} major incident (or MIM dry-run) — bridge, escalation and stakeholder comms",
        "Observe {skill} change execution and a patch/maintenance cycle in a live window",
        "Observe {skill} problem management / RCA and the resulting CMDB & known-error updates",
        "Observe {skill} monitoring/event triage and reporting/governance forums",
    ],
    "reverse_shadow": [
        "Perform {skill} incident, service-request and change handling with incumbent review",
        "Lead/participate in a {skill} major incident with review — exercise escalation & communication",
        "Execute a {skill} patch/maintenance cycle and access-management requests with review",
        "Perform {skill} problem RCA, update the CMDB and produce a service report",
    ],
    "stabilization": [
        "Independently run {skill} incident, problem, change, request, access and patching processes",
        "Own {skill} MIM, escalation & communication; run monitoring/event management end-to-end",
        "Maintain {skill} CMDB/asset accuracy; deliver reporting & governance to the agreed cadence",
        "Monitor & report {skill} KPIs/SLAs (penalties waived) and drive early continuous improvement",
    ],
}
# ── Acceptance gates (Exit + Sign-off) — the contractual moments where responsibility ─
# shifts. Detailed, {skill}-templated; every criterion must be demonstrably satisfied,
# all open items owned & agreed, and residual risk accepted by BOTH parties before the
# gate is passed. Rendered per skill in the tab + a dedicated Excel "Acceptance & Sign-off"
# sheet with a fillable open-items/risk register and a named sign-off block (templates —
# the tool is a proposal artifact, so status/names are completed during the real transition).
SKILL_EXIT_CRITERIA = [   # KT/Shadow completion gate (aligns to M2/M3)
    "All {skill} KT & Shadow activities completed; documentation, SOPs and runbooks reviewed and approved",
    "{skill} SOPs/runbooks validated in production-like conditions",
    "No open P1/P2 {skill} knowledge gaps",
    "All open {skill} items captured in the register below — each with a named owner, "
    "target date and remediation plan — and explicitly agreed by both parties",
    "Access, environments and tooling required for the next phase confirmed available",
]
SKILL_SIGNOFF_CRITERIA = [   # Go-Live / Reverse-Shadow sign-off gate
    "{skill} production readiness demonstrated in Reverse-Shadow (Nagarro operating, incumbent reviewing)",
    "{skill} steady-state KPIs/SLAs agreed and baselined (penalties waived through Stabilization)",
    "Residual {skill} risks documented and rated with mitigation, and formally ACCEPTED BY BOTH PARTIES "
    "(customer risk-acceptance recorded) — no unaccepted open risk remains",
    "All {skill} open items either closed or carried with an agreed owner, target date and both-party sign-off",
    "Operational ownership of {skill} formally transferred to Nagarro",
    "Go / Conditional-Go / No-Go decision recorded with named sign-off from both parties",
]

# Family-specific critical readiness check that MUST pass at sign-off (generic fallback below).
GENERIC_CRITICAL_CHECK = "Production readiness — backup/restore and failover (where applicable) — validated for {skill}"
FAMILY_CRITICAL_CHECK = {
    "compute":    "Backup/restore drill and host failover validated for {skill}",
    "network":    "Configuration-backup restore and failover validated for {skill}",
    "database":   "Restore drill and HA/DR failover validated for {skill}",
    "storage":    "Backup restore and replication failover validated for {skill}",
    "cloud":      "DR/backup restore and guardrail/security-baseline checks validated for {skill}",
    "platform":   "Pipeline rollback and DR restore validated for {skill}",
    "security":   "Detection playbook execution and control-coverage validated for {skill}",
    "monitoring": "Alert-coverage and runbook execution validated for {skill}",
}

# Fillable open-items / residual-risk register (headers only — completed during transition).
OPEN_ITEMS_RISK_COLUMNS = [
    "#", "Open Item / Residual Risk", "Type (Item / Risk)", "Severity", "Owner",
    "Party (Customer / Nagarro)", "Target date", "Mitigation / Plan",
    "Agreed by both parties (Y/N)", "Status",
]
# Named sign-off block (signatures/dates completed at the gate).
SIGNOFF_SIGNATORIES = [
    ("Customer", "Business / Service Owner"),
    ("Customer", "Application / Infrastructure Owner"),
    ("Nagarro", "Transition Manager"),
    ("Nagarro", "Delivery Manager / SDM"),
]
SIGNOFF_DECISION = ("Decision:  [ ] Go     [ ] Conditional-Go (with agreed open items)     [ ] No-Go")

# ── Family-aware TECHNICAL layer ──────────────────────────────────────────────
# The builder merges the common PROCESS_STAGE_ACTIVITIES backbone (same ITIL processes
# for every skill) with the technology-specific technical activities below. A skill's
# free-text name maps to a family via config.SKILL_CANONICAL_KEYWORDS + SKILL_TOKEN_TO_FAMILY
# (same classification as the AI Team Optimizer); unmapped names use SKILL_STAGE_TEMPLATES.
SKILL_TOKEN_TO_FAMILY = {
    "cloud": "cloud", "devops": "platform",
    "vmware": "compute", "windows": "compute", "linux": "compute",
    "network": "network", "security": "security", "monitoring": "monitoring",
    "database": "database", "storage": "storage",
}
FAMILY_LABELS = {
    "compute": "Compute (servers / VMs / OS)", "network": "Network",
    "database": "Database", "storage": "Storage & Backup", "cloud": "Cloud",
    "platform": "Platform / DevOps", "security": "Security", "monitoring": "Monitoring",
}
FAMILY_STAGE_TEMPLATES = {
    "compute": {
        "knowledge_transition": [
            "Technical KT for {skill}: OS builds, server/VM roles, dependencies and hardening baselines",
            "Validate {skill} backup, restore and DR runbooks",
            "Inventory the {skill} estate (hosts/VMs) and configuration baselines",
        ],
        "shadow": ["Analyse recurring {skill} technical issues (capacity, performance, patch failures)"],
        "reverse_shadow": ["{skill} production readiness: backup/restore drill and host failover check"],
        "stabilization": ["Operational handover of {skill} technical runbooks and known errors"],
    },
    "network": {
        "knowledge_transition": [
            "Technical KT for {skill}: topology, routing and firewall rule-base",
            "Review {skill} device inventory, firmware levels and configuration backups",
            "Validate {skill} config-backup and rollback procedures",
        ],
        "shadow": ["Analyse recurring {skill} technical issues (link flaps, rule conflicts, capacity)"],
        "reverse_shadow": ["{skill} production readiness: config-backup restore and failover validation"],
        "stabilization": ["Operational handover of {skill} device configs and known-error database"],
    },
    "database": {
        "knowledge_transition": [
            "Technical KT for {skill}: instances, schemas and HA/replication topology",
            "Validate {skill} backup, restore, PITR and DR runbooks",
            "Review {skill} performance baselines and scheduled jobs",
        ],
        "shadow": ["Analyse recurring {skill} technical issues (blocking, capacity, failed jobs)"],
        "reverse_shadow": ["{skill} production readiness: restore drill and HA/DR failover validation"],
        "stabilization": ["Operational handover of {skill} runbooks; track RPO/RTO adherence"],
    },
    "storage": {
        "knowledge_transition": [
            "Technical KT for {skill}: arrays, LUNs/shares and replication",
            "Validate {skill} backup schedules, retention and restore runbooks",
            "Review {skill} capacity and firmware baselines",
        ],
        "shadow": ["Analyse recurring {skill} technical issues (capacity, failed backups, latency)"],
        "reverse_shadow": ["{skill} production readiness: restore drill and replication failover check"],
        "stabilization": ["Operational handover of {skill} runbooks; track capacity & backup success"],
    },
    "cloud": {
        "knowledge_transition": [
            "Technical KT for {skill}: accounts/subscriptions and landing-zone architecture",
            "Review {skill} IaC repos, tagging and guardrails",
            "Validate {skill} backup/DR and resiliency setup",
        ],
        "shadow": ["Analyse recurring {skill} technical issues (cost spikes, quota limits, config drift)"],
        "reverse_shadow": ["{skill} production readiness: DR/backup validation and guardrail checks"],
        "stabilization": ["Own {skill} cost & guardrail governance; hand over IaC and runbooks"],
    },
    "platform": {
        "knowledge_transition": [
            "Technical KT for {skill}: CI/CD pipelines, IaC and container/K8s platform",
            "Review {skill} release, rollback and secrets/artifact management",
            "Validate {skill} platform SLOs and on-call runbooks",
        ],
        "shadow": ["Analyse recurring {skill} technical issues (build/deploy failures, drift, SLO breaches)"],
        "reverse_shadow": ["{skill} production readiness: pipeline, rollback and DR validation"],
        "stabilization": ["Operational handover of {skill} pipelines and runbooks; track SLOs"],
    },
    "security": {
        "knowledge_transition": [
            "Technical KT for {skill}: SIEM, security controls, IAM and policies",
            "Review {skill} detection use-cases and response playbooks",
            "Validate {skill} vulnerability/patch-compliance posture",
        ],
        "shadow": ["Analyse recurring {skill} technical issues (false positives, tuning, open findings)"],
        "reverse_shadow": ["{skill} production readiness: playbook execution and control-coverage validation"],
        "stabilization": ["Own {skill} detection tuning & compliance; track MTTD/MTTR"],
    },
    "monitoring": {
        "knowledge_transition": [
            "Technical KT for {skill}: monitoring tooling, dashboards and alert rules",
            "Review {skill} alert catalogue, thresholds and runbook mapping",
            "Validate {skill} event correlation and notification workflows",
        ],
        "shadow": ["Analyse recurring {skill} technical issues (alert noise, missed alerts, coverage gaps)"],
        "reverse_shadow": ["{skill} production readiness: alert-coverage and runbook validation"],
        "stabilization": ["Own {skill} alert tuning; track alert-to-noise and coverage"],
    },
}

# ── RACI ──────────────────────────────────────────────────────────────────────
ROLES_CUSTOMER = ["Business/Service Owner", "Application Owner", "Infrastructure",
                  "Security", "Network", "SMEs", "Customer PM"]
ROLES_NAGARRO = ["Transition Mgr", "Delivery Mgr / SDM", "Nagarro PM", "Technical Lead",
                 "L1", "L2", "L3", "Architect", "PMO"]
ALL_ROLES = ROLES_CUSTOMER + ROLES_NAGARRO

# Each activity → {role: R|A|C|I}. Exactly one Accountable (A) per activity (enforced/tested).
# Roles omitted are not involved. Kept representative for a first cut; extend as needed.
RACI = [
    {"activity": "Discovery workshops & scope baselining", "phase": "assessment",
     "raci": {"Business/Service Owner": "A", "SMEs": "C", "Transition Mgr": "R",
              "Delivery Mgr / SDM": "C", "Architect": "R", "PMO": "I"}},
    {"activity": "Environment / tooling access provisioning", "phase": "assessment",
     "raci": {"Infrastructure": "R", "Security": "C", "Network": "C", "Customer PM": "A",
              "Transition Mgr": "C", "Technical Lead": "I"}},
    {"activity": "Governance & Transition Plan sign-off (M1)", "phase": "initiation",
     "raci": {"Business/Service Owner": "A", "Customer PM": "C", "Transition Mgr": "R",
              "Delivery Mgr / SDM": "C", "PMO": "R", "Nagarro PM": "R"}},
    {"activity": "Functional & technical knowledge transfer", "phase": "knowledge_transition",
     "raci": {"SMEs": "R", "Application Owner": "C", "Transition Mgr": "A", "Technical Lead": "R",
              "L2": "R", "L3": "R", "Architect": "C"}},
    {"activity": "Documentation review & approval (M2)", "phase": "knowledge_transition",
     "raci": {"Application Owner": "A", "SMEs": "C", "Technical Lead": "R", "L3": "C",
              "Transition Mgr": "R", "PMO": "I"}},
    {"activity": "Shadow observation & gap analysis (M3)", "phase": "shadow",
     "raci": {"SMEs": "C", "Transition Mgr": "A", "Technical Lead": "R", "L1": "R", "L2": "R",
              "L3": "C", "Delivery Mgr / SDM": "I"}},
    {"activity": "Reverse-shadow operations & readiness", "phase": "reverse_shadow",
     "raci": {"Business/Service Owner": "I", "Transition Mgr": "C", "Delivery Mgr / SDM": "A",
              "Technical Lead": "R", "L1": "R", "L2": "R", "L3": "R", "Architect": "C"}},
    {"activity": "Go-Live sign-off to commence services", "phase": "reverse_shadow",
     "raci": {"Business/Service Owner": "A", "Customer PM": "C",
              "Delivery Mgr / SDM": "R", "Transition Mgr": "R", "PMO": "I"}},
    {"activity": "KPI/SLA baselining & stabilization exit (M4)", "phase": "stabilization",
     "raci": {"Business/Service Owner": "A", "Customer PM": "C", "Delivery Mgr / SDM": "R",
              "PMO": "C", "L2": "I", "L3": "I"}},
]

# ── Best-practice artifacts (enterprise RFP extras; lightweight) ───────────────
BEST_PRACTICE_ARTIFACTS = [
    "Transition governance & communication cadence (SteerCo / weekly / daily standups)",
    "Risk, Assumptions, Issues & Dependencies (RAID) register",
    "Access & tooling provisioning checklist",
    "KT tracker with per-session sign-off",
    "Production readiness / Go/No-Go checklist per milestone",
    "Stabilization KPI/SLA baseline & exit report",
]
