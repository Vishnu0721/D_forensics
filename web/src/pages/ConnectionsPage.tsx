import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { getGraph, type GraphNode, type GraphResponse } from "../api";

type GraphFilter = "all" | "network" | "execution" | "findings";

const KIND_LABEL: Record<string, string> = {
  process: "Program",
  file: "File",
  ip: "Internet",
  user: "User",
  device: "Device",
  other: "Other",
};

function themeColors(): Record<string, string> {
  const s = getComputedStyle(document.documentElement);
  const read = (name: string, fallback: string) =>
    s.getPropertyValue(name).trim() || fallback;
  return {
    process: read("--df-node-process", "#1a56db"),
    file: read("--df-node-file", "#0f7a45"),
    ip: read("--df-node-ip", "#9a6400"),
    user: read("--df-node-user", "#5a6f8a"),
    device: read("--df-node-device", "#6b4fbb"),
    other: read("--df-node-other", "#8aa0bf"),
    text: read("--df-text", "#0f1f33"),
    muted: read("--df-text-muted", "#5a6f8a"),
    border: read("--df-border", "#c5d4e8"),
    surface: read("--df-surface", "#ffffff"),
    accent: read("--df-accent", "#1a56db"),
  };
}

export function ConnectionsPage() {
  const { caseId = "" } = useParams();
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [view, setView] = useState<"simple" | "detailed">("simple");
  const [filter, setFilter] = useState<GraphFilter>("all");
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getGraph(caseId, view)
      .then((data) => {
        if (!cancelled) {
          setGraph(data);
          setSelected(null);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load connections");
          setGraph(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, view]);

  useEffect(() => {
    if (!containerRef.current || !graph) return;

    const filtered = applyFilter(graph, filter);
    const elements: ElementDefinition[] = [
      ...filtered.nodes.map((n) => ({
        data: {
          id: n.id,
          label: n.label,
          kind: n.kind,
          story: n.story,
        },
      })),
      ...filtered.edges.map((e) => ({
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

    const colors = themeColors();
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-valign": "bottom",
            "text-margin-y": 6,
            "font-size": 11,
            color: colors.text,
            "background-color": (ele) =>
              colors[ele.data("kind") as string] ?? colors.other,
            width: 28,
            height: 28,
            "border-width": 2,
            "border-color": colors.surface,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": colors.border,
            "target-arrow-color": colors.border,
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 9,
            color: colors.muted,
            "text-rotation": "autorotate",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": colors.accent,
            "border-width": 3,
          },
        },
      ],
      layout: {
        name: filtered.nodes.length > 40 ? "concentric" : "cose",
        animate: false,
        padding: 24,
      } as cytoscape.LayoutOptions,
      userZoomingEnabled: true,
      userPanningEnabled: true,
    });

    cy.on("tap", "node", (evt) => {
      const d = evt.target.data();
      setSelected({
        id: d.id,
        label: d.label,
        kind: d.kind,
        story: d.story || "",
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
  }, [graph, filter]);

  const empty = graph && graph.nodes.length === 0;

  return (
    <div className="connections-page">
      <h1>Connections</h1>
      <p className="lead">Who and what is linked in this investigation.</p>

      <div className="toolbar">
        <div className="btn-row">
          <button
            type="button"
            className={view === "simple" ? "btn btn--primary" : "btn btn--ghost"}
            onClick={() => setView("simple")}
          >
            Simple
          </button>
          <button
            type="button"
            className={view === "detailed" ? "btn btn--primary" : "btn btn--ghost"}
            onClick={() => setView("detailed")}
          >
            Detailed
          </button>
        </div>
        <div className="filter-bar">
          {(
            [
              ["all", "All"],
              ["network", "Network"],
              ["execution", "Programs & files"],
              ["findings", "Needs a look"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={
                filter === id ? "filter-chip filter-chip--active" : "filter-chip"
              }
              onClick={() => setFilter(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <ul className="graph-legend">
        {Object.entries(KIND_LABEL).map(([kind, label]) => (
          <li key={kind}>
            <span
              className="graph-legend__swatch"
              style={{ background: themeColors()[kind] ?? themeColors().other }}
            />
            {label}
          </li>
        ))}
      </ul>

      {loading && <p className="muted">Loading…</p>}
      {error && <p className="status-err">{error}</p>}

      {empty && !loading && (
        <section className="empty-state">
          <h2>No links yet</h2>
          <p className="muted">Run Analyze after importing evidence to build connections.</p>
          <Link className="btn btn--primary" to={`/cases/${caseId}`}>
            Back to overview
          </Link>
        </section>
      )}

      {!empty && !error && graph && (
        <div className="graph-layout">
          <div ref={containerRef} className="graph-canvas" aria-label="Connections graph" />
          <aside className="graph-story panel">
            <h2>Story</h2>
            {selected ? (
              <>
                <p className="graph-story__label">
                  <span
                    className="graph-legend__swatch"
                    style={{
                      background:
                        themeColors()[selected.kind] ?? themeColors().other,
                    }}
                  />
                  {KIND_LABEL[selected.kind] ?? selected.kind}: {selected.label}
                </p>
                <p>{selected.story || "No story for this node yet."}</p>
              </>
            ) : (
              <p className="muted">Click a node to read its story.</p>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

function applyFilter(graph: GraphResponse, filter: GraphFilter): GraphResponse {
  if (filter === "all") return graph;

  const keepNode = (n: GraphNode) => {
    if (filter === "network") return n.kind === "ip" || /net|connect|ip/i.test(n.story);
    if (filter === "execution") return n.kind === "process" || n.kind === "file";
    if (filter === "findings") {
      return /suspicious|look|warn|payload|unusual/i.test(`${n.label} ${n.story}`);
    }
    return true;
  };

  const nodes = graph.nodes.filter(keepNode);
  const ids = new Set(nodes.map((n) => n.id));
  const edges = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
  return { ...graph, nodes, edges };
}
