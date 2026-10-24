"""Render a finished session as one standalone HTML file: the tree map, the next move, and what to let go of."""

import html
import json
from pathlib import Path

TREE_JS = Path(__file__).parent / "web" / "tree.js"


def render_html(graph):
    data = json.dumps(graph.to_dict()).replace("</", "<\\/")
    accept = "".join(f"<li>{html.escape(v)}</li>" for v in graph.accept.values())
    levers = "".join(f"<li>{html.escape(v)}</li>" for v in graph.actions.values())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>LifeGraph</title>
<style>
:root{{--control:#1f7a4d;--influence:#b8860b;--outside:#7a7a7a;--ink:#1d1d1f;--muted:#6e6e73;--line:#e5e5e7}}
body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:#f7f7f8}}
header{{padding:18px 24px 10px;background:#fff;border-bottom:1px solid var(--line)}}
header h1{{font-size:20px;margin:0 0 4px;letter-spacing:-.01em}}
header p{{margin:0;color:var(--muted);font-size:14px}}
.legend{{display:flex;gap:14px;font-size:12px;color:var(--muted);margin-top:10px}}
.legend i{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}}
.legend .red{{width:14px;height:3px;border-radius:2px;background:#c0392b;vertical-align:2px}}
.next{{margin:18px 24px;display:grid;grid-template-columns:auto 1fr;gap:14px;align-items:center;border:2px solid var(--control);background:#e6f4ec;padding:12px 16px;border-radius:12px}}
.next b{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--control)}}
.next span{{font-size:17px;font-weight:600}}
svg{{display:block;width:100%;height:70vh}}
.lever rect{{stroke:#c0392b;stroke-width:3;filter:drop-shadow(0 0 6px rgba(192,57,43,.35))}}
.foot{{display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:0 24px 32px;font-size:14px}}
.foot h3{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 6px}}
.foot ul{{margin:0;padding-left:18px}} .foot li{{margin:3px 0}}
details{{padding:0 24px 24px;font-size:12px;color:var(--muted)}} pre{{white-space:pre-wrap;font-size:11px}}
</style></head><body>
<header><h1>{html.escape(graph.problem)}</h1><p>{html.escape(graph.summary)}</p>
<div class="legend"><span><i style="background:#e6f4ec;border:2px solid var(--control)"></i>control</span><span><i style="background:#fff4d6;border:2px solid var(--influence)"></i>influence</span><span><i style="background:#ececec;border:2px solid var(--outside)"></i>outside my control</span><span><i style="background:var(--control);border-radius:5px;width:16px"></i>action</span><span><i class="red"></i>leaves your reach</span></div></header>
<div class="next"><b>Your next move</b><span>{html.escape(graph.next_move) or "<i>not set</i>"}</span></div>
<svg id="map" preserveAspectRatio="xMidYMin meet"></svg>
<div class="foot">
<div><h3>At the lever</h3><ul>{levers or "<li>none</li>"}</ul></div>
<div><h3>Let go of</h3><ul>{accept or "<li>nothing outside your reach on the main chain</li>"}</ul></div>
</div>
<details><summary>Raw graph</summary><pre>{html.escape(json.dumps(graph.to_dict(), indent=2))}</pre></details>
<script>{TREE_JS.read_text()}</script>
<script>LifeGraphTree.render(document.getElementById("map"), {data});</script>
</body></html>"""


def save_html(graph, data_dir):
    path = Path(data_dir) / "sessions" / f"{graph.session_id}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(graph))
    return path
