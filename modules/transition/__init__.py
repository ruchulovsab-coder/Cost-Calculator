"""Transition Strategy — a read-only, deterministic projection of the estimate into a
proposal-ready, ITIL-aligned transition plan (timeline + phase activities + skill-wise plan +
RACI + deliverables). Consumes the estimator output; never writes back and never influences
effort/FTE/commercials. Encodes the baseline framework in assets/transition framework.png as data
(config/catalog). See docs/transition-strategy-approach.md."""
