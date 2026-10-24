"""Render a finished session as one standalone HTML file: the sketched tree, the quest, what to let go of."""

import html
import json
from pathlib import Path

WEB = Path(__file__).parent / "web"


def render_html(graph):
    data = json.dumps(graph.to_dict()).replace("</", "<\\/")
    accept = "".join(f"<li>{html.escape(v)}</li>" for v in graph.accept.values())
    levers = "".join(f"<li>{html.escape(v)}</li>" for v in graph.actions.values())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>LifeGraph</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Patrick+Hand&family=Caveat:wght@700&display=swap">
<style>
:root{{--control:#2f7d4f;--influence:#b8860b;--outside:#6d6d6d;--ink:#2b2b2b;--muted:#6f6a60;--paper:#fbf7ee;--red:#c0392b}}
body{{margin:0;font-family:"Patrick Hand","Segoe Print","Bradley Hand",cursive;font-size:17px;color:var(--ink);background:var(--paper);background-image:radial-gradient(#d8d0bf 1px,transparent 1.2px);background-size:24px 24px}}
header{{padding:18px 24px 12px;border-bottom:2px solid var(--ink)}}
h1{{font-family:"Caveat",cursive;font-size:36px;margin:0;line-height:1}}
header p{{margin:6px 0 0;color:var(--muted);font-size:18px}}
.legend{{display:flex;gap:16px;font-size:15px;color:var(--muted);margin-top:10px}}
.legend i{{display:inline-block;width:14px;height:12px;border:2px solid var(--ink);border-radius:60% 40% 55% 45%/50% 60% 40% 50%;margin-right:5px;vertical-align:-2px;background:#fff}}
.legend .red{{width:16px;height:0;border:0;border-top:3px solid var(--red);border-radius:0;vertical-align:2px}}
.next{{position:relative;margin:22px 24px;display:grid;grid-template-columns:auto 1fr;gap:16px;align-items:center;background:#fff3a3;padding:16px 20px;transform:rotate(-.8deg);box-shadow:3px 5px 0 rgba(43,43,43,.15);max-width:900px}}
.next::before{{content:"";position:absolute;top:-10px;left:50%;width:70px;height:20px;margin-left:-35px;background:rgba(255,255,255,.55);border:1px solid rgba(0,0,0,.08);transform:rotate(-2deg)}}
.next b{{font-family:"Caveat",cursive;font-size:20px;color:#6b5600;line-height:1}}
.next span{{font-size:21px;line-height:1.25}}
svg{{display:block;width:100%;height:72vh}} svg text{{font-family:"Patrick Hand","Segoe Print",cursive}}
.lever-ring{{stroke-dasharray:4 3}}
.foot{{display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:0 24px 32px;font-size:17px}}
.foot h3{{font-family:"Caveat",cursive;font-size:24px;margin:0 0 4px}}
.foot ul{{margin:0;padding-left:18px}} .foot li{{margin:3px 0}}
details{{padding:0 24px 24px;font-size:13px;color:var(--muted)}} pre{{white-space:pre-wrap;font-size:11px;font-family:ui-monospace,monospace}}
</style></head><body>
<header><h1>{html.escape(graph.problem)}</h1><p>{html.escape(graph.summary)}</p>
<div class="legend"><span><i style="border-width:2.5px"></i>path</span><span><i style="background:#e3f1e7;border-color:var(--control)"></i>control</span><span><i style="background:#fbf0cf;border-color:var(--influence)"></i>influence</span><span><i style="background:#e9e7e2;border-color:var(--outside)"></i>outside my control</span><span><i style="background:repeating-linear-gradient(-45deg,var(--control) 0 1.5px,#e3f1e7 1.5px 5px);border-color:var(--control);border-radius:8px"></i>action</span><span><i class="red"></i>leaves your reach</span></div></header>
<div class="next"><b>your quest<br>this week</b><span>{html.escape(graph.next_move) or "<i>not set</i>"}</span></div>
<svg id="map" preserveAspectRatio="xMidYMin meet"></svg>
<div class="foot">
<div><h3>at the lever</h3><ul>{levers or "<li>none</li>"}</ul></div>
<div><h3>let go of</h3><ul>{accept or "<li>nothing outside your reach on the main chain</li>"}</ul></div>
</div>
<details><summary>raw graph</summary><pre>{html.escape(json.dumps(graph.to_dict(), indent=2))}</pre></details>
<script>{(WEB / "sketch.js").read_text()}</script>
<script>{(WEB / "tree.js").read_text()}</script>
<script>LifeGraphTree.render(document.getElementById("map"), {data}, {{expandAll: true}});</script>
</body></html>"""


def save_html(graph, data_dir):
    path = Path(data_dir) / "sessions" / f"{graph.session_id}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(graph))
    return path
