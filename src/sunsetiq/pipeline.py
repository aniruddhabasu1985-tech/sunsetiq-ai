"""LangGraph orchestration: map -> score -> sequence -> govern -> report.

Deterministic code does the planning and the policy; models are used only for language tasks
(draft change requests, status packs) and are chosen per task by the Jev router."""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from .audit import AuditLog
from .data_gen import Estate, generate_estate
from .evidence import make_evidence
from .graph import build_graph, cutover_groups
from .jev_layer import JevRouter, MockJevClient, RouteRequest
from .llm import LLMClient, MockLLMClient
from .policy import evaluate_decommission
from .readiness import score_all
from .sequencer import FREEZE_WAVES, measure, plan_governed, plan_naive


class State(TypedDict, total=False):
    estate: Estate
    g: Any
    groups: list
    readiness: dict
    plans: dict
    metrics: dict
    decisions: list
    drafts: list
    ai_cost_usd: float
    audit: AuditLog


def build_pipeline(router: JevRouter, llm: LLMClient, jev) -> Any:
    def map_dependencies(s: State) -> State:
        g = build_graph(s["estate"])
        s["audit"].append("dependency_mapper", "mapped", nodes=g.number_of_nodes(), edges=g.number_of_edges())
        return {"g": g, "groups": cutover_groups(s["estate"], g)}

    def score_readiness(s: State) -> State:
        r = score_all(s["estate"], s["g"])
        s["audit"].append("readiness_scorer", "scored", apps=len(r))
        return {"readiness": r}

    def sequence(s: State) -> State:
        est = s["estate"]
        plans = {"naive": plan_naive(est), "governed": plan_governed(est)}
        metrics = {k: measure(est, p) for k, p in plans.items()}
        s["audit"].append("sequencer", "planned", governed_waves=plans["governed"].waves_used)
        return {"plans": plans, "metrics": metrics}

    def govern(s: State) -> State:
        est, out = s["estate"], []
        for t in s["plans"]["governed"].tasks:
            if t.kind != "decommission":
                continue
            for aid in t.apps:
                ev = make_evidence(aid)
                out.append(evaluate_decommission(est.apps[aid], s["readiness"][aid], t.done_wave,
                                                 FREEZE_WAVES, ev.text, jev, s["audit"]))
        return {"decisions": out}

    def report(s: State) -> State:
        est, drafts, cost = s["estate"], [], 0.0
        for d in s["decisions"]:
            if d.status != "APPROVAL_PACK_READY":
                continue
            app = est.apps[d.app_id]
            rd = router.route(RouteRequest(f"cr-{d.app_id}", "draft_change_request",
                                           f"Draft change request to retire {app.name}. regulated={app.regulated_data}",
                                           session_id=f"cr-{d.app_id}", regulated=app.regulated_data))
            drafts.append(llm.complete("draft_change_request", f"Retire {app.name}", rd.model.slug, rd.effort))
            cost += rd.est_cost
        for aid, rd_ in s["readiness"].items():
            app = est.apps[aid]
            deps = len(s["g"].pred[aid]) if hasattr(s["g"], "pred") else 0
            rd = router.route(RouteRequest(f"si-{aid}", "summarise_impact",
                                           f"Summarise impact of retiring {app.name}: {deps} direct dependents, "
                                           f"readiness {rd_.band}.", session_id=f"impact-{aid}", regulated=app.regulated_data))
            drafts.append(llm.complete("summarise_impact", f"Impact {app.name}", rd.model.slug, rd.effort))
            cost += rd.est_cost
        for w in range(1, s["plans"]["governed"].waves_used + 1):
            rd = router.route(RouteRequest(f"sp-{w}", "draft_status_pack",
                                           f"Wave {w} programme status: summarise progress and risks.",
                                           session_id="status-packs"))
            drafts.append(llm.complete("draft_status_pack", f"Wave {w} status", rd.model.slug, rd.effort))
            cost += rd.est_cost
        s["audit"].append("status_writer", "drafted", n=len(drafts), est_cost=round(cost, 4))
        return {"drafts": drafts, "ai_cost_usd": cost}

    g = StateGraph(State)
    for name, fn in [("map", map_dependencies), ("score", score_readiness), ("sequence", sequence),
                     ("govern", govern), ("report", report)]:
        g.add_node(name, fn)
    g.set_entry_point("map")
    for a, b in [("map", "score"), ("score", "sequence"), ("sequence", "govern"), ("govern", "report")]:
        g.add_edge(a, b)
    g.add_edge("report", END)
    return g.compile()


def run(seed: int = 7, jev=None, router: JevRouter | None = None, llm: LLMClient | None = None) -> State:
    audit = AuditLog()
    jev = jev if jev is not None else MockJevClient()
    router = router or JevRouter(jev, audit=audit)
    app = build_pipeline(router, llm or MockLLMClient(), jev)
    return app.invoke({"estate": generate_estate(seed=seed), "audit": audit})
