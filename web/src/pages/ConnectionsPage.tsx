import { useEffect, useMemo, useRef, useState } from "react";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { useParams } from "react-router-dom";
import { getGraph, type GraphEdge, type GraphNode, type GraphView } from "../api";
import { useTheme } from "../theme/ThemeProvider";

type LinkFilter = "all" | "network" | "execution" | "attention";

const LINK_FILTERS: { value: LinkFilter; label: string }[] = [
  { value: "all", label: "All links" },
  { value: "network", label: "Network only" },
  { value: "execution", label: "Execution only" },
  { value: "attention", label: "Needs attention" },
];

const KIND_COLOR: Record<string, string> = {
  process: "var(--df-node-process)",
  file: "var(--df-node-file)",
  ip: "var(--df-node-ip)",
  user: "var(--df-node-user)",
  device: "var(--df-node-device)",
  other: "var(--df-node-other)",
};

function cssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function edgeMatches(edge: GraphEdge, filter: LinkFilter, attentionIds: Set<string>): boolean {
  const rel = (edge.relationship || "").toUpperCase();
  if (filter === "all") return true;
  if (filter === "network") return rel.includes("CONNECT") || rel.includes("EXFIL");
  if (filter === "execution") return rel.includes("EXECUT") || rel.includes("DOWNLOAD");
  if (filter === "attention") {
    return attentionIds.has(edge.source) || attentionIds.has(edge.target);
  }
  return true;
}

export function ConnectionsPage() {
  const { caseId } = useParams();
  const { theme } = useTheme();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);

  const [view, setView] = useState<GraphView>("simple");
  const [linkFilter, setLinkFilter] = useState<LinkFilter>("all");
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSelected(null);
    getGraph(caseId, view)
      .then((data) => {
        if (cancelled) return;
        setNodes(data.nodes);
        setEdges(data.edges);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, view]);

  const attentionIds = useMemo(() => {
    const ids = new Set<string>();
    for (const e of edges) {
      const rel = (e.relationship || "").toUpperCase();
      if (rel.includes("CONNECT") || rel.includes("EXFIL") || rel.includes("EXECUT")) {
        ids.add(e.source);
        ids.add(e.target);
      }
    }
    return ids;
  }, [edges]);

  const filteredEdges = useMemo(
    () => edges.filter((e) => edgeMatches(e, linkFilter, attentionIds)),
    [edges, linkFilter, attentionIds],
  );

  const visibleNodeIds = useMemo(() => {
    if (linkFilter === "all") return new Set(nodes.map((n) => n.id));
    const ids = new Set<string>();
    for (const e of filteredEdges) {
      ids.add(e.source);
      ids.add(e.target);
    }
    return ids;
  }, [nodes, filteredEdges, linkFilter]);

  useEffect(() => {
    if (!containerRef.current) return;

    const visibleNodes = nodes.filter((n) => visibleNodeIds.has(n.id));
    const elements: ElementDefinition[] = [
      ...visibleNodes.map((n) => ({
        data: {
          id: n.id,
          label: n.label,
          kind: n.kind,
          story: n.story,
        },
      })),
      ...filteredEdges.map((e) => ({
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.relationship,
        },
      })),
    ];

    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": cssVar("--df-node-other", "#64748b"),
            color: cssVar("--df-text", "#0f1f33"),
            "font-size": "11px",
            "text-valign": "bottom",
            "text-margin-y": 6,
            "text-wrap": "wrap",
            "text-max-width": "90px",
            width: 28,
            height: 28,
            "border-width": 2,
            "border-color": cssVar("--df-surface", "#fff"),
          },
        },
        {
          selector: 'node[kind = "process"]',
          style: { "background-color": cssVar("--df-node-process", "#1a56db") },
        },
        {
          selector: 'node[kind = "file"]',
          style: { "background-color": cssVar("--df-node-file", "#0f7a45") },
        },
        {
          selector: 'node[kind = "ip"]',
          style: { "background-color": cssVar("--df-node-ip", "#7c3aed") },
        },
        {
          selector: 'node[kind = "user"]',
          style: { "background-color": cssVar("--df-node-user", "#0e7490") },
        },
        {
          selector: 'node[kind = "device"]',
          style: { "background-color": cssVar("--df-node-device", "#b45309") },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": cssVar("--df-border-strong", "#8aa0bf"),
            "target-arrow-color": cssVar("--df-border-strong", "#8aa0bf"),
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": "9px",
            color: cssVar("--df-text-muted", "#5a6f8a"),
            "text-rotation": "autorotate",
            "text-margin-y": -8,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 3,
            "border-color": cssVar("--df-accent", "#1a56db"),
          },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        padding: 24,
        nodeRepulsion: () => 6000,
        idealEdgeLength: () => 100,
      },
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
    });

    cy.on("tap", "node", (evt) => {
      const d = evt.target.data();
      setSelected({
        id: d.id,
        label: d.label,
        kind: d.kind,
        story: d.story || `${d.label} (${d.kind})`,
      });
    });

    cy.on("tap", (evt) => {
      if (evt.target === cy) setSelected(null);
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [nodes, filteredEdges, visibleNodeIds, theme]);

  if (!caseId) return null;

  return (
    <div className="connections-page">
      <section className="panel">
        <header className="connections-header">
          <div>
            <h1>Connections</h1>
            <p className="muted">
              How programs, files, and network destinations relate. Blue = program, green = file,
              purple = internet address.
            </p>
          </div>
          <div className="view-toggle" role="group" aria-label="Graph detail">
            <button
              type="button"
              className={view === "simple" ? "filter-chip filter-chip--active" : "filter-chip"}
              onClick={() => setView("simple")}
            >
              Simple
            </button>
            <button
              type="button"
              className={view === "detailed" ? "filter-chip filter-chip--active" : "filter-chip"}
              onClick={() => setView("detailed")}
            >
              Detailed
            </button>
          </div>
        </header>

        <div className="filter-bar" role="tablist" aria-label="Link filters">
          {LINK_FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              role="tab"
              aria-selected={linkFilter === f.value}
              className={
                linkFilter === f.value ? "filter-chip filter-chip--active" : "filter-chip"
              }
              onClick={() => setLinkFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>

        {error && <p className="error">{error}</p>}
        {loading && <p className="muted">Loading graph…</p>}

        {!loading && !error && nodes.length === 0 && (
          <div className="empty">
            <p>No connections yet.</p>
            <p className="muted">Import and analyze evidence to build the relationship graph.</p>
          </div>
        )}

        <div className="graph-split">
          <div className="graph-canvas-wrap">
            <div ref={containerRef} className="graph-canvas" aria-label="Evidence graph" />
          </div>
          <aside className="graph-story panel panel--nested">
            <h2>Node story</h2>
            {selected ? (
              <>
                <p className="drawer__headline">{selected.label}</p>
                <span className="badge" style={{ background: "var(--df-accent-soft)" }}>
                  {selected.kind}
                </span>
                <p className="muted" style={{ marginTop: "0.75rem" }}>
                  {selected.story}
                </p>
                <p className="muted hint">
                  Color key:{" "}
                  <span style={{ color: KIND_COLOR.process }}>process</span>,{" "}
                  <span style={{ color: KIND_COLOR.file }}>file</span>,{" "}
                  <span style={{ color: KIND_COLOR.ip }}>ip</span>
                </p>
              </>
            ) : (
              <p className="muted">Click a node to read a short plain-language story.</p>
            )}
            <p className="muted" style={{ marginTop: "1rem" }}>
              Showing {filteredEdges.length} link{filteredEdges.length === 1 ? "" : "s"} ·{" "}
              {visibleNodeIds.size} node{visibleNodeIds.size === 1 ? "" : "s"}
            </p>
          </aside>
        </div>
      </section>
    </div>
  );
}
