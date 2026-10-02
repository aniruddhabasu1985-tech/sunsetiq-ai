"""Dependency graph helpers. Edge direction: consumer -> provider (consumer depends on provider)."""
from __future__ import annotations

import networkx as nx

from .data_gen import Estate


def build_graph(estate: Estate) -> nx.DiGraph:
    g = nx.DiGraph()
    for a in estate.apps.values():
        g.add_node(a.app_id)
    for e in estate.edges:
        g.add_edge(e.consumer, e.provider, link_type=e.link_type, rewire_effort=e.rewire_effort)
    return g


def direct_dependents(g: nx.DiGraph, app_id: str) -> list[str]:
    """Apps that depend on app_id (their edge points at app_id)."""
    return list(g.predecessors(app_id))


def transitive_dependents(g: nx.DiGraph, app_id: str) -> set[str]:
    """Blast radius: everything that directly or indirectly depends on app_id."""
    return nx.ancestors(g, app_id)


def cutover_groups(estate: Estate, g: nx.DiGraph) -> list[frozenset[str]]:
    """Strongly connected components among retire candidates.

    Apps that depend on each other cannot be retired one-by-one; they retire as one cut-over group.
    """
    retire = {a.app_id for a in estate.retire_candidates()}
    sub = g.subgraph(retire)
    return [frozenset(c) for c in nx.strongly_connected_components(sub)]
