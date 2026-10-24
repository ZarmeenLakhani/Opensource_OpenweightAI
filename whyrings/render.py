"""Render a graph as a standalone HTML page: three concentric rings, nodes placed by ring, edges by cause."""

import html
import json
import math
from pathlib import Path

from .graph import RINGS

RADIUS = {"control": 110, "influence": 230, "outside": 350}
COLOR = {"control": "#2f7d4f", "influence": "#b8860b", "outside": "#8a8a8a"}


def _positions(graph):
    positions = {}
    by_ring = {ring: [] for ring in RINGS}
    for node_id in graph.dfs_order():
        by_ring[graph.nodes[node_id]["ring"] or "outside"].append(node_id)
    for ring, ids in by_ring.items():
        for i, node_id in enumerate(ids):
            angle = -math.pi / 2 + (2 * math.pi * i / max(len(ids), 1))
            r = RADIUS[ring] - 50
            positions[node_id] = (400 + r * math.cos(angle), 400 + r * math.sin(angle))
    return positions


def render_html(graph):
    pos = _positions(graph)
    levers = set(graph.levers())
    boundary = set(graph.boundary_edges())
    parts = [
        f"<svg viewBox='0 0 800 800' width='800' height='800' font-family='system-ui' font-size='12'>",
        f"<circle cx='400' cy='400' r='{RADIUS['outside']}' fill='#f3f3f3' stroke='#ccc'/>",
        f"<circle cx='400' cy='400' r='{RADIUS['influence']}' fill='#fff7e0' stroke='#ccc'/>",
        f"<circle cx='400' cy='400' r='{RADIUS['control']}' fill='#e6f4ea' stroke='#ccc'/>",
        "<text x='400' y='60' text-anchor='middle' fill='#777'>OUTSIDE</text>",
        "<text x='400' y='185' text-anchor='middle' fill='#777'>INFLUENCE</text>",
        "<text x='400' y='310' text-anchor='middle' fill='#777'>CONTROL</text>",
    ]
    for node in graph.nodes.values():
        if node["parent_id"]:
            (x1, y1), (x2, y2) = pos[node["parent_id"]], pos[node["id"]]
            crossing = (node["parent_id"], node["id"]) in boundary
            stroke = "#d33" if crossing else "#999"
            width = 3 if crossing else 1.5
            parts.append(f"<line x1='{x1:.0f}' y1='{y1:.0f}' x2='{x2:.0f}' y2='{y2:.0f}' stroke='{stroke}' stroke-width='{width}'/>")
    for node in graph.nodes.values():
        x, y = pos[node["id"]]
        fill = COLOR[node["ring"] or "outside"]
        ring_stroke = "#d33" if node["id"] in levers else "#fff"
        label = html.escape(node["text"][:38] + ("…" if len(node["text"]) > 38 else ""))
        parts.append(f"<circle cx='{x:.0f}' cy='{y:.0f}' r='9' fill='{fill}' stroke='{ring_stroke}' stroke-width='3'><title>{html.escape(node['text'])}</title></circle>")
        parts.append(f"<text x='{x + 12:.0f}' y='{y + 4:.0f}'>{label}</text>")
    parts.append("</svg>")

    actions = "".join(f"<li><b>{html.escape(graph.nodes[k]['text'])}</b>: {html.escape(v)}</li>" for k, v in graph.actions.items())
    accept = "".join(f"<li><b>{html.escape(graph.nodes[k]['text'])}</b>: {html.escape(v)}</li>" for k, v in graph.accept.items())
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Why Rings</title>
<style>body{{font-family:system-ui;max-width:1100px;margin:24px auto;display:grid;grid-template-columns:800px 1fr;gap:24px}}
h1{{font-size:20px}} li{{margin-bottom:8px}}</style></head><body>
<div>{''.join(parts)}</div>
<div><h1>{html.escape(graph.problem)}</h1><p>{html.escape(graph.summary)}</p>
<p>Red edges are where a chain leaves your reach. Red-outlined nodes are levers: the last thing you can act on before that crossing.</p>
<h2>Do this week</h2><ul>{actions or '<li>No actions recorded.</li>'}</ul>
<h2>Let go of</h2><ul>{accept or '<li>Nothing outside your reach on the main chain.</li>'}</ul>
<details><summary>Raw graph</summary><pre>{html.escape(json.dumps(graph.to_dict(), indent=2))}</pre></details></div>
</body></html>"""


def save_html(graph, data_dir):
    path = Path(data_dir) / "sessions" / f"{graph.session_id}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(graph))
    return path
