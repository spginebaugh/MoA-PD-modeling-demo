"""Graph composition entry points.

The old curated scenario builder was intentionally removed. Graphs are now
composed from pathway JSON through services.pathway.
"""

from __future__ import annotations

from services.domain import MoAGraph, PathwayId
from services.pathway import GraphComposeRequest, compose_graph, load_pathway


def graph_from_configuration(pathway_id: PathwayId | str, configuration: str) -> MoAGraph:
    return compose_graph(GraphComposeRequest(pathway_id=PathwayId(str(pathway_id)), configuration=configuration))


def graph_from_pathway(pathway_id: PathwayId | str) -> MoAGraph:
    pathway = load_pathway(pathway_id)
    return compose_graph(GraphComposeRequest(pathway_id=pathway.pathway_id))
