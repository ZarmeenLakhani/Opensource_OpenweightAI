// LifeGraph tree renderer: the problem at the top, the paths the person could take as the main
// branches, consequences and actions under each path. The "why" causes sit behind one click on a
// "what bothers me" node. Shared by the live page (index.html) and the saved page (render.py).
(function () {
  const W = 190, GAP_X = 22, LEVEL_H = 134, PAD = 48, LINE_H = 15, MAX_LINES = 4, CHARS = 24;
  const COLOR = { control: "#1f7a4d", influence: "#b8860b", outside: "#7a7a7a", none: "#bbb" };
  const BG = { control: "#e6f4ec", influence: "#fff4d6", outside: "#ececec", none: "#fafafa" };
  const WHY_ID = "why";
  const state = { collapsed: new Set([WHY_ID]), touched: false };

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

  // Build the display tree: causes directly under n0 are grouped under a virtual "what bothers me" node,
  // so the paths (options) are the visible main branches.
  function displayNodes(graph) {
    const nodes = graph.nodes.map(n => ({ ...n }));
    const causesOfRoot = nodes.filter(n => n.parent_id === "n0" && n.kind === "cause");
    if (causesOfRoot.length) {
      const count = nodes.filter(n => n.kind === "cause").length;
      nodes.push({ id: WHY_ID, kind: "group", text: `What bothers me · ${count}`, parent_id: "n0", ring: null, virtual: true });
      causesOfRoot.forEach(n => { n.parent_id = WHY_ID; });
    }
    return nodes;
  }

  function layout(nodes, collapsed) {
    const order = { group: 0, cause: 1, option: 2, consequence: 3, action: 4 };
    const kids = id => collapsed.has(id) ? [] : nodes.filter(n => n.parent_id === id).sort((a, b) => (order[a.kind] ?? 9) - (order[b.kind] ?? 9));
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
      const total = c.reduce((s, k) => s + span[k.id], 0) + GAP_X * Math.max(0, c.length - 1);
      let x = x0 + (span[id] - total) / 2;
      c.forEach(k => { place(k.id, x, depth + 1); x += span[k.id] + GAP_X; });
    }
    measure("n0"); place("n0", 0, 0);
    const ys = Object.values(pos).map(p => p.y + p.h / 2);
    return { pos, lines, bounds: { x: 0, y: -40, w: span["n0"], h: Math.max(...ys) + 50 } };
  }

  function esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

  function ancestors(nodes, id) {
    const byId = Object.fromEntries(nodes.map(n => [n.id, n])); const out = [];
    let cur = byId[id]; while (cur && cur.parent_id) { out.push(cur.parent_id); cur = byId[cur.parent_id]; }
    return out;
  }

  function render(svg, graph, opts) {
    opts = opts || {};
    const nodes = displayNodes(graph);
    if (opts.expandAll && !state.touched) state.collapsed.clear();
    // Once the paths exist, fold the "why" group away so the paths dominate, unless the person toggled it
    // or the agent is asking about a cause right now.
    const focusInWhy = opts.focusId && ancestors(nodes, opts.focusId).includes(WHY_ID);
    if (!state.touched && !opts.expandAll && graph.nodes.some(n => n.kind === "option") && !focusInWhy) state.collapsed.add(WHY_ID);
    // Keep the node being asked about visible.
    if (opts.focusId) ancestors(nodes, opts.focusId).forEach(a => state.collapsed.delete(a));
    const hidden = new Set();
    nodes.forEach(n => { if (ancestors(nodes, n.id).some(a => state.collapsed.has(a))) hidden.add(n.id); });
    const visible = nodes.filter(n => !hidden.has(n.id));
    const { pos, lines, bounds } = layout(visible, state.collapsed);
    const minW = opts.minWidth || 900;
    const vw = Math.max(bounds.w + PAD * 2, minW), vx = bounds.x - (vw - bounds.w) / 2;
    svg.setAttribute("viewBox", `${vx} ${bounds.y - PAD / 2} ${vw} ${bounds.h + PAD}`);
    const levers = new Set(graph.levers || []), crossing = new Set((graph.boundary_edges || []).map(e => e[1]));
    const childCount = id => nodes.filter(n => n.parent_id === id).length;

    let edges = "";
    visible.forEach(n => {
      if (!n.parent_id || !pos[n.parent_id]) return;
      const a = pos[n.parent_id], b = pos[n.id];
      const y1 = a.y + a.h / 2, y2 = b.y - b.h / 2, ym = (y1 + y2) / 2;
      const red = crossing.has(n.id);
      const dashed = n.kind === "consequence" || n.kind === "group";
      edges += `<path d="M${a.x} ${y1} C${a.x} ${ym}, ${b.x} ${ym}, ${b.x} ${y2}" fill="none" stroke="${red ? "#c0392b" : n.kind === "option" ? "#1d1d1f" : "#c9c9c9"}" stroke-width="${red ? 3 : n.kind === "option" ? 2 : 1.6}" ${dashed ? 'stroke-dasharray="5 4"' : ""}/>`;
    });

    let nodesSvg = "";
    visible.forEach(n => {
      const p = pos[n.id], ring = n.ring || "none", ls = lines[n.id];
      const k = n.kind, isProblem = k === "problem", isAction = k === "action", isCons = k === "consequence", isOpt = k === "option", isGroup = k === "group";
      const fill = isProblem ? "#1d1d1f" : isAction ? COLOR[ring] : isOpt || isGroup ? "#fff" : BG[ring];
      const stroke = isProblem ? "#1d1d1f" : isGroup ? "#9a9a9a" : isOpt ? "#1d1d1f" : COLOR[ring];
      const txt = isProblem || isAction ? "#fff" : isGroup ? "#555" : "#1d1d1f";
      const rx = isAction || isGroup ? p.h / 2 : 10;
      const collapsed = state.collapsed.has(n.id), kidsN = childCount(n.id);
      const cls = ["node", `k-${k}`, `r-${ring}`, levers.has(n.id) ? "lever" : "", opts.focusId === n.id ? "focus" : "", kidsN ? "has-kids" : ""].join(" ");
      const tspans = ls.map((l, i) => `<tspan x="0" dy="${i ? LINE_H : 0}">${esc((isAction && !i ? "→ " : "") + l)}</tspan>`).join("");
      const ty = -((ls.length - 1) * LINE_H) / 2 + 4;
      const title = isGroup ? "click to show what is behind the problem" : `${n.text}\n${k} · ${ring}${n.ring_reason ? " · " + n.ring_reason : ""}${n.shifts_when ? "\nmoves if: " + n.shifts_when : ""}`;
      const sideBar = isOpt ? `<rect x="${-W / 2}" y="${-p.h / 2}" width="6" height="${p.h}" rx="3" fill="${COLOR[ring]}"/>` : "";
      const caption = isOpt ? `<text x="${-W / 2 + 12}" y="${-p.h / 2 - 6}" font-size="10" font-weight="700" fill="#8a8a8a" letter-spacing=".08em">PATH</text>` : "";
      const badge = collapsed && kidsN ? `<g transform="translate(${W / 2 - 2},${-p.h / 2 + 2})"><circle r="10" fill="#1d1d1f"/><text text-anchor="middle" y="3.5" font-size="10" font-weight="700" fill="#fff">+${kidsN}</text></g>` : "";
      nodesSvg += `<g class="${cls}" transform="translate(${p.x},${p.y})" data-id="${n.id}" style="cursor:pointer">
        <title>${esc(title)}</title>
        <rect x="${-W / 2}" y="${-p.h / 2}" width="${W}" height="${p.h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${isCons ? 1.5 : isOpt ? 2.2 : 2}" ${isCons || isGroup ? 'stroke-dasharray="5 4"' : ""}/>
        ${sideBar}${caption}
        <text text-anchor="middle" y="${ty}" fill="${txt}" font-size="${isOpt ? 13 : 12.5}" font-weight="${isProblem || isOpt ? 600 : 400}" font-style="${isCons ? "italic" : "normal"}">${tspans}</text>
        ${levers.has(n.id) ? `<text x="${W / 2 - 4}" y="${-p.h / 2 - 6}" text-anchor="end" font-size="10.5" font-weight="700" fill="#c0392b">LEVER</text>` : ""}
        ${n.shifts_when ? `<circle cx="${-W / 2 + 10}" cy="${-p.h / 2 + 10}" r="5" fill="#fff" stroke="${stroke}" stroke-width="1.5"><title>${esc("moves if: " + n.shifts_when)}</title></circle>` : ""}
        ${badge}
      </g>`;
    });
    svg.innerHTML = `<g class="edges">${edges}</g><g class="nodes">${nodesSvg}</g>`;

    svg.onclick = ev => {
      const g = ev.target.closest && ev.target.closest("g.node");
      if (!g) return;
      const id = g.getAttribute("data-id"), node = nodes.find(n => n.id === id);
      if (childCount(id)) {
        state.touched = true;
        if (state.collapsed.has(id)) state.collapsed.delete(id); else state.collapsed.add(id);
        render(svg, graph, opts);
      }
      if (opts.onNodeClick && node && !node.virtual) opts.onNodeClick(node, ev);
    };
  }

  window.LifeGraphTree = { render, COLOR };
})();
