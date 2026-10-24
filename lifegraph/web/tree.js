// LifeGraph tree renderer: lays out the decision graph as a top-down tree inside an <svg>.
// Shared by the live page (index.html) and the saved standalone page (render.py).
(function () {
  const W = 190, GAP_X = 20, LEVEL_H = 132, PAD = 48, LINE_H = 15, MAX_LINES = 4, CHARS = 24;
  const COLOR = { control: "#1f7a4d", influence: "#b8860b", outside: "#7a7a7a", none: "#bbb" };
  const BG = { control: "#e6f4ec", influence: "#fff4d6", outside: "#ececec", none: "#fafafa" };

  function wrap(text) {
    const words = String(text).split(/\s+/), lines = [];
    let line = "";
    for (const w of words) {
      if ((line + " " + w).trim().length > CHARS && line) { lines.push(line); line = w; } else line = (line + " " + w).trim();
    }
    if (line) lines.push(line);
    if (lines.length > MAX_LINES) { lines.length = MAX_LINES; lines[MAX_LINES - 1] = lines[MAX_LINES - 1].replace(/.{2}$/, "") + "…"; }
    return lines;
  }

  function layout(graph) {
    const nodes = graph.nodes, kids = id => nodes.filter(n => n.parent_id === id);
    const span = {}, pos = {}, lines = {};
    nodes.forEach(n => { lines[n.id] = wrap(n.text); });
    function measure(id) {
      const c = kids(id);
      if (!c.length) return (span[id] = W);
      let s = 0; c.forEach(k => { s += measure(k.id) + GAP_X; });
      return (span[id] = Math.max(W, s - GAP_X));
    }
    function place(id, x0, depth) {
      const c = kids(id);
      pos[id] = { x: x0 + span[id] / 2, y: depth * LEVEL_H, h: lines[id].length * LINE_H + 20 };
      let total = c.reduce((s, k) => s + span[k.id], 0) + GAP_X * Math.max(0, c.length - 1);
      let x = x0 + (span[id] - total) / 2;
      c.forEach(k => { place(k.id, x, depth + 1); x += span[k.id] + GAP_X; });
    }
    if (!nodes.length) return { pos, lines, bounds: { x: 0, y: 0, w: W, h: 60 } };
    measure("n0"); place("n0", 0, 0);
    const ys = Object.values(pos).map(p => p.y + p.h / 2);
    return { pos, lines, bounds: { x: 0, y: -40, w: span["n0"], h: Math.max(...ys) + 50 } };
  }

  function esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

  function render(svg, graph, opts) {
    opts = opts || {};
    const { pos, lines, bounds } = layout(graph);
    const minW = opts.minWidth || 900;
    const vw = Math.max(bounds.w + PAD * 2, minW), vx = bounds.x - (vw - bounds.w) / 2;
    svg.setAttribute("viewBox", `${vx} ${bounds.y - PAD / 2} ${vw} ${bounds.h + PAD}`);
    const levers = new Set(graph.levers || []), crossing = new Set((graph.boundary_edges || []).map(e => e[1]));
    const byId = Object.fromEntries(graph.nodes.map(n => [n.id, n]));

    let edges = "";
    graph.nodes.forEach(n => {
      if (!n.parent_id || !pos[n.parent_id]) return;
      const a = pos[n.parent_id], b = pos[n.id];
      const y1 = a.y + a.h / 2, y2 = b.y - b.h / 2, ym = (y1 + y2) / 2;
      const red = crossing.has(n.id);
      edges += `<path d="M${a.x} ${y1} C${a.x} ${ym}, ${b.x} ${ym}, ${b.x} ${y2}" fill="none" stroke="${red ? "#c0392b" : "#c9c9c9"}" stroke-width="${red ? 3 : 1.6}" ${n.kind === "consequence" ? 'stroke-dasharray="5 4"' : ""}/>`;
    });

    let nodesSvg = "";
    graph.nodes.forEach(n => {
      const p = pos[n.id], ring = n.ring || "none", ls = lines[n.id];
      const isProblem = n.kind === "problem", isAction = n.kind === "action", isCons = n.kind === "consequence";
      const fill = isProblem ? "#1d1d1f" : isAction ? COLOR[ring] : BG[ring];
      const stroke = isProblem ? "#1d1d1f" : COLOR[ring];
      const txt = isProblem || isAction ? "#fff" : "#1d1d1f";
      const rx = isAction ? p.h / 2 : 10;
      const cls = ["node", `k-${n.kind}`, `r-${ring}`, levers.has(n.id) ? "lever" : "", opts.focusId === n.id ? "focus" : ""].join(" ");
      const tspans = ls.map((l, i) => `<tspan x="0" dy="${i ? LINE_H : 0}">${esc((isAction && !i ? "→ " : "") + l)}</tspan>`).join("");
      const ty = -((ls.length - 1) * LINE_H) / 2 + 4;
      const title = `${n.text}\n${n.kind} · ${ring}${n.ring_reason ? " · " + n.ring_reason : ""}${n.shifts_when ? "\nmoves if: " + n.shifts_when : ""}`;
      nodesSvg += `<g class="${cls}" transform="translate(${p.x},${p.y})" data-id="${n.id}">
        <title>${esc(title)}</title>
        <rect x="${-W / 2}" y="${-p.h / 2}" width="${W}" height="${p.h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${isCons ? 1.5 : 2}" ${isCons ? 'stroke-dasharray="5 4"' : ""}/>
        <text text-anchor="middle" y="${ty}" fill="${txt}" font-size="12.5" font-weight="${isProblem ? 600 : 400}" font-style="${isCons ? "italic" : "normal"}">${tspans}</text>
        ${levers.has(n.id) ? `<text x="${W / 2 - 4}" y="${-p.h / 2 - 6}" text-anchor="end" font-size="10.5" font-weight="700" fill="#c0392b">LEVER</text>` : ""}
        ${n.shifts_when ? `<circle cx="${-W / 2 + 10}" cy="${-p.h / 2 + 10}" r="5" fill="#fff" stroke="${stroke}" stroke-width="1.5"><title>${esc("moves if: " + n.shifts_when)}</title></circle>` : ""}
      </g>`;
    });
    svg.innerHTML = `<g class="edges">${edges}</g><g class="nodes">${nodesSvg}</g>`;
  }

  window.LifeGraphTree = { render, COLOR };
})();
