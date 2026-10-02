"""Deterministic synthetic application estate. All names, costs and links are invented."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

UNITS = ["Network Access", "Consumer", "Enterprise", "Shared Platform"]
FAMILIES = ["billing", "crm", "order_mgmt", "provisioning", "reporting", "identity",
            "field_ops", "data_platform", "middleware", "payments"]
LINK_TYPES = ["api", "db_link", "middleware", "file_feed"]
REWIRE_EFFORT = {"api": 2, "db_link": 5, "middleware": 4, "file_feed": 1}


@dataclass
class App:
    app_id: str
    name: str
    family: str
    unit: str
    annual_licence: int       # currency units / year (illustrative)
    annual_run: int           # hosting + support
    users: int
    criticality: int          # 1 (low) .. 4 (business critical)
    regulated_data: bool
    decom_effort: int         # effort points
    renewal_wave: int         # must retire by this wave to avoid next licence year
    role: str                 # "survivor" | "retire" | "keep"
    survivor_id: str | None = None

    @property
    def annual_saving(self) -> int:
        return self.annual_licence + self.annual_run


@dataclass
class Edge:
    consumer: str   # consumer depends on provider
    provider: str
    link_type: str
    rewire_effort: int


@dataclass
class Estate:
    apps: dict[str, App] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def retire_candidates(self) -> list[App]:
        return [a for a in self.apps.values() if a.role == "retire"]

    def dependents_of(self, provider_id: str) -> list[Edge]:
        return [e for e in self.edges if e.provider == provider_id]


def generate_estate(n_apps: int = 200, seed: int = 7, cycle_pairs: int = 3) -> Estate:
    rng = random.Random(seed)
    est = Estate()
    survivors: dict[str, str] = {}
    for i, fam in enumerate(FAMILIES):
        aid = f"APP-{i + 1:03d}"
        est.apps[aid] = App(
            aid, f"{fam.title()} Core", fam, "Shared Platform",
            rng.randint(300, 600) * 1000, rng.randint(200, 400) * 1000,
            rng.randint(2000, 9000), 4, fam in ("billing", "payments", "identity"),
            0, 99, "survivor")
        survivors[fam] = aid
    for i in range(len(FAMILIES), n_apps):
        aid = f"APP-{i + 1:03d}"
        fam = rng.choice(FAMILIES)
        is_retire = rng.random() < 0.45
        crit = rng.choices([1, 2, 3, 4], weights=[3, 4, 3, 1])[0]
        est.apps[aid] = App(
            aid, f"{fam.title()} {rng.choice(['Alpha', 'Beta', 'Delta', 'Sigma', 'Omega', 'Nova'])}-{i + 1}",
            fam, rng.choice(UNITS[:3]),
            rng.randint(40, 420) * 1000, rng.randint(30, 260) * 1000,
            rng.randint(20, 3000), crit, rng.random() < 0.18,
            rng.randint(3, 14), rng.randint(2, 9),
            "retire" if is_retire else "keep",
            survivors[fam] if is_retire else None)
    ids = list(est.apps)
    seen: set[tuple[str, str]] = set()
    for cid in ids:
        for _ in range(rng.choice([0, 1, 1, 2, 3])):
            pid = rng.choice(ids)
            if pid == cid or (cid, pid) in seen:
                continue
            seen.add((cid, pid))
            lt = rng.choice(LINK_TYPES)
            est.edges.append(Edge(cid, pid, lt, REWIRE_EFFORT[lt]))
    # inject mutual-dependency cycles among retire candidates (cut-over groups)
    rc = [a.app_id for a in est.retire_candidates()]
    rng.shuffle(rc)
    for k in range(cycle_pairs):
        a, b = rc[2 * k], rc[2 * k + 1]
        for c, p in ((a, b), (b, a)):
            if (c, p) not in seen:
                seen.add((c, p))
                est.edges.append(Edge(c, p, "db_link", REWIRE_EFFORT["db_link"]))
    return est
