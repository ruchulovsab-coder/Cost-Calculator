"""Shift Plan / Roster Designer — a read-only, deterministic projection of the final
estimate into a proposal-ready coverage/shift plan. Consumes the estimator output; never
writes back to it and never influences effort/FTE/commercials (no circular dependency).
See docs/roster-designer-approach.md."""
