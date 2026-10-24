"""Render a session as a standalone HTML page: the decision graph on the left, three distinct regions on the right."""

import html
import json
from pathlib import Path

from .graph import RINGS

LABEL = {"control": "Control", "influence": "Influence", "outside": "Outside my control"}
GLYPH = {"problem": "!", "cause": "?", "action": "→", "consequence": "⇝"}


def _tree(graph):
    levers = set(graph.levers())
    boundary = {child for _, child in graph.boundary_edges()}
    rows = []
    for node_id in graph.dfs_order():
        n = graph.nodes[node_id]
        classes = [f"ring-{n['ring'] or 'none'}", f"kind-{n['kind']}"]
        if node_id in levers:
            classes.append("lever")
        if node_id in boundary:
            classes.append("crossing")
        shift = f"<small>moves if: {html.escape(n['shifts_when'])}</small>" if n["shifts_when"] else ""
        rows.append(
            f"<div class='{' '.join(classes)}' style='margin-left:{n['depth'] * 22}px'>"
            f"<span class='glyph'>{GLYPH[n['kind']]}</span>"
            f"<span class='badge'>{n['ring'] or '?'}</span> {html.escape(n['text'])} {shift}"
            f"{' <b class=tag>lever</b>' if node_id in levers else ''}"
            f"{' <b class=tag-out>leaves your reach</b>' if node_id in boundary else ''}</div>"
        )
    return "".join(rows)


def _region(graph, ring):
    nodes = graph.by_ring()[ring]
    actions = [n for n in nodes if n["kind"] == "action"]
    causes = [n for n in nodes if n["kind"] in ("cause", "problem")]
    cons = [n for n in nodes if n["kind"] == "consequence"]

    def items(lst):
        return "".join(f"<li>{html.escape(n['text'])}</li>" for n in lst) or "<li class='muted'>nothing here</li>"

    body = ""
    if ring != "outside":
        body += f"<h4>You could</h4><ul>{items(actions)}</ul>"
    body += f"<h4>{'What sits here' if ring == 'outside' else 'Why it matters'}</h4><ul>{items(causes)}</ul>"
    if cons:
        body += f"<h4>If you went down that path</h4><ul>{items(cons)}</ul>"
    return f"<section class='region {ring}'><h3>{LABEL[ring]}</h3>{body}</section>"


def render_html(graph):
    accept = "".join(f"<li><b>{html.escape(graph.nodes[k]['text'])}</b>: {html.escape(v)}</li>" for k, v in graph.accept.items())
    lever_actions = "".join(f"<li><b>{html.escape(graph.nodes[k]['text'])}</b>: {html.escape(v)}</li>" for k, v in graph.actions.items())
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>LifeGraph</title>
<style>
:root{{--control:#1f7a4d;--influence:#b07d10;--outside:#6b6b6b;--control-bg:#e8f5ee;--influence-bg:#fff6df;--outside-bg:#f0f0f0}}
body{{font-family:system-ui;max-width:1200px;margin:24px auto;padding:0 16px;color:#1a1a1a;background:#fff}}
h1{{font-size:22px;margin-bottom:4px}} .sub{{color:#555;margin-top:0}}
.next{{border:2px solid var(--control);background:var(--control-bg);padding:14px 18px;border-radius:10px;margin:18px 0}}
.next h2{{margin:0 0 6px;font-size:15px;text-transform:uppercase;letter-spacing:.05em;color:var(--control)}}
.cols{{display:grid;grid-template-columns:1.1fr 1fr;gap:28px}} @media(max-width:860px){{.cols{{grid-template-columns:1fr}}}}
.tree div{{padding:4px 0;font-size:14px}} .glyph{{display:inline-block;width:14px;color:#888}}
.badge{{font-size:11px;padding:1px 6px;border-radius:8px;color:#fff;background:#999;vertical-align:middle}}
.ring-control .badge{{background:var(--control)}} .ring-influence .badge{{background:var(--influence)}} .ring-outside .badge{{background:var(--outside)}}
.kind-action{{color:var(--control)}} .kind-consequence{{font-style:italic;color:#444}}
.lever{{font-weight:600}} .tag{{font-size:11px;color:#c0392b;font-weight:600}} .tag-out{{font-size:11px;color:#c0392b;font-weight:400}}
.crossing{{border-left:3px solid #c0392b;padding-left:6px}} small{{color:#777;margin-left:6px}}
.regions{{display:grid;gap:12px}}
.region{{border-radius:10px;padding:12px 16px;border:1px solid #ddd}} .region h3{{margin:0 0 6px;font-size:14px;text-transform:uppercase;letter-spacing:.05em}}
.region h4{{margin:10px 0 2px;font-size:12px;color:#666;font-weight:600}} .region ul{{margin:0;padding-left:18px}} .region li{{margin:2px 0}}
.region.control{{background:var(--control-bg)}} .region.control h3{{color:var(--control)}}
.region.influence{{background:var(--influence-bg)}} .region.influence h3{{color:var(--influence)}}
.region.outside{{background:var(--outside-bg)}} .region.outside h3{{color:var(--outside)}}
.muted{{color:#999;list-style:none;margin-left:-18px}} details{{margin-top:24px}} pre{{font-size:11px;overflow:auto}}
</style></head><body>
<h1>{html.escape(graph.problem)}</h1><p class='sub'>{html.escape(graph.summary)}</p>
<div class='next'><h2>Your next move</h2>{html.escape(graph.next_move) or '<i>not set</i>'}</div>
<div class='cols'>
<div><h3>How we got here</h3><div class='tree'>{_tree(graph)}</div>
<p class='sub'><b class='tag'>leaves your reach</b> marks where a chain crosses out of your control; the bold node just above it is a lever.</p>
{f"<h3>At the levers</h3><ul>{lever_actions}</ul>" if lever_actions else ""}
{f"<h3>Let go of</h3><ul>{accept}</ul>" if accept else ""}</div>
<div class='regions'>{''.join(_region(graph, ring) for ring in RINGS)}</div>
</div>
<details><summary>Raw graph</summary><pre>{html.escape(json.dumps(graph.to_dict(), indent=2))}</pre></details>
</body></html>"""


def save_html(graph, data_dir):
    path = Path(data_dir) / "sessions" / f"{graph.session_id}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(graph))
    return path
