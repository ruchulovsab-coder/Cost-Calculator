"""The transition framework encoded as data (not code).

Transcribes assets/transition framework.png — "Operational Establishment & Stabilization":
7 ITIL-aligned phases (Service Strategy → Design → Transition → Operations), milestones M1–M4 +
Go-Live, per-phase objectives/deliverables/entry-exit/risks/dependencies/responsibilities, a
Customer/Nagarro RACI, and per-skill KT→Shadow→Reverse-Shadow→Stabilization activity templates.
Everything downstream (builder, UI, Excel) reads from here, so the methodology stays faithful and
editable in one place."""
from __future__ import annotations

# ── Phases (ordered) ──────────────────────────────────────────────────────────
# milestone marks the GATE at the end of the phase; ongoing = continuous (steady state).
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
    {"key": "steady_state", "name": "Steady State Service Delivery & Continuous Improvement",
     "band": "Service Operations", "default_weeks": 4, "milestone": None, "ongoing": True},
]

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
    "steady_state": {
        "objectives": ["Deliver SLA-based managed services", "Drive continuous improvement"],
        "deliverables": ["SLA-based support (full penalties apply)", "ITIL V4/V3 support documentation",
                         "CSI register"],
        "entry": ["Stabilization exit approved (M4)"],
        "exit": ["Ongoing — governed by the AMS contract"],
        "risks": ["Scope creep", "Continuous-improvement backlog not prioritised"],
        "dependencies": ["Customer governance participation"],
        "customer_resp": ["Participate in service reviews", "Prioritise CSI initiatives"],
        "nagarro_resp": ["Deliver to SLA", "Run helpdesk/SR management & application support"],
    },
}

# ── Per-skill activity templates ({skill} is filled by the builder) ───────────
SKILL_STAGE_TEMPLATES = {
    "knowledge_transition": [
        "Functional knowledge transfer for {skill}",
        "Technical knowledge transfer for {skill}",
        "Documentation review for {skill}",
        "SOP / runbook validation for {skill}",
        "Access provisioning for {skill} tooling",
        "Tool familiarization for {skill}",
    ],
    "shadow": [
        "Observe incumbent handling {skill} incidents & service requests",
        "Analyse {skill} recurring issues and process gaps",
    ],
    "reverse_shadow": [
        "Perform {skill} operations with incumbent review",
        "{skill} production readiness checks",
    ],
    "stabilization": [
        "Independent {skill} operations",
        "Monitor & report {skill} KPIs/SLAs (penalties waived)",
        "Operational handover of {skill}",
    ],
}
SKILL_EXIT_CRITERIA = [
    "All {skill} KT sessions completed and documentation approved",
    "{skill} SOPs/runbooks validated in production-like conditions",
    "No P1/P2 knowledge gaps open for {skill}",
]
SKILL_SIGNOFF_CRITERIA = [
    "Customer sign-off on {skill} production readiness",
    "{skill} steady-state KPIs/SLAs baselined",
]

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
    {"activity": "Steady-state SLA delivery & CSI", "phase": "steady_state",
     "raci": {"Business/Service Owner": "A", "Delivery Mgr / SDM": "R", "L1": "R", "L2": "R",
              "L3": "R", "Architect": "C", "PMO": "C"}},
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
