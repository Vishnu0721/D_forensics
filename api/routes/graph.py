"""Evidence graph JSON for Connections UI."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.db import get_db
from api.schemas import GraphEdge, GraphNode, GraphResponse
from api.serializers import get_case_or_404
from api.services.analysis import graph_for_case

router = APIRouter(prefix="/api/v1/cases/{case_id}/graph", tags=["graph"])

KIND_MAP = {
    "Process": "process",
    "File": "file",
    "IP": "ip",
    "User": "user",
    "Device": "device",
}


MAX_GRAPH_NODES = 250
MAX_GRAPH_EDGES = 500


@router.get("", response_model=GraphResponse)
def get_graph(
    case_id: str,
    view: str = Query(default="simple"),
    db: Session = Depends(get_db),
):
    get_case_or_404(db, case_id)
    if view not in ("simple", "detailed"):
        view = "simple"

    graph = graph_for_case(case_id)
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    if view == "detailed":
        for node_id, data in graph.graph.nodes(data=True):
            ntype = data.get("type") or "other"
            label = data.get("label") or node_id
            subtitle = data.get("subtitle") or ""
            nodes.append(
                GraphNode(
                    id=str(node_id),
                    label=str(label),
                    kind=KIND_MAP.get(ntype, "other"),
                    story=f"{label} — {subtitle}".strip(" —"),
                )
            )
        for i, (u, v, key, data) in enumerate(graph.graph.edges(keys=True, data=True)):
            edges.append(
                GraphEdge(
                    id=f"e-{i}-{key}",
                    source=str(u),
                    target=str(v),
                    relationship=str(key),
                    confidence=data.get("confidence"),
                )
            )
        return GraphResponse(
            view="detailed",
            nodes=nodes[:MAX_GRAPH_NODES],
            edges=edges[:MAX_GRAPH_EDGES],
        )

    # Simple view: collapse processes by name
    id_map: dict[str, str] = {}
    label_nodes: dict[str, GraphNode] = {}
    for node_id, data in graph.graph.nodes(data=True):
        ntype = data.get("type") or "other"
        label = str(data.get("label") or node_id)
        if ntype == "Process":
            simple_id = f"process:{label.lower()}"
            story = f"Programs named {label}"
        else:
            simple_id = str(node_id)
            story = f"{label} ({ntype})"
        id_map[str(node_id)] = simple_id
        if simple_id not in label_nodes:
            label_nodes[simple_id] = GraphNode(
                id=simple_id,
                label=label,
                kind=KIND_MAP.get(ntype, "other"),
                story=story,
            )

    edge_seen: set[tuple[str, str, str]] = set()
    for i, (u, v, key, data) in enumerate(graph.graph.edges(keys=True, data=True)):
        su, sv = id_map.get(str(u), str(u)), id_map.get(str(v), str(v))
        trip = (su, sv, str(key))
        if trip in edge_seen or su == sv:
            continue
        edge_seen.add(trip)
        edges.append(
            GraphEdge(
                id=f"e-{i}-{key}",
                source=su,
                target=sv,
                relationship=str(key),
                confidence=data.get("confidence"),
            )
        )

    node_list = list(label_nodes.values())[:MAX_GRAPH_NODES]
    keep = {n.id for n in node_list}
    trimmed_edges = [e for e in edges if e.source in keep and e.target in keep][:MAX_GRAPH_EDGES]
    return GraphResponse(view="simple", nodes=node_list, edges=trimmed_edges)
