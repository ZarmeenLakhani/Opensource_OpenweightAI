// LifeGraph tree renderer, hand-sketched. The problem at the top, the paths the person could take as the
// main branches, consequences and actions under each path. The "why" causes sit in a thought cloud that opens
// on click. Shared by the live page (index.html) and the saved page (render.py). Needs sketch.js.
(function () {
  const W = 196, GAP_X = 26, LEVEL_H = 140, PAD = 56, LINE_H = 18, MAX_LINES = 4, CHARS = 22;
  const COLOR = { control: "#2f7d4f", influence: "#b8860b", outside: "#6d6d6d", none: "#999" };
  const BG = { control: "#e3f1e7", influence: "#fbf0cf", outside: "#e9e7e2", none: "#fff" };
  const INK = "#2b2b2b";
  const WHY_ID = "why";
  const state = { collapsed: new Set([WHY_ID]), touched: false };
  const S = () => window.LifeGraphSketch;

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

  function displayNodes(graph) {
    const nodes = graph.nodes.map(n => ({ ...n }));
    const causesOfRoot = nodes.filter(n => n.parent_id === "n0" && n.kind === "cause");
    if (causesOfRoot.length) {
      const count = nodes.filter(n => n.kind === "cause").length;
      nodes.push({ id: WHY_ID, kind: "group", text: `what bothers me (${count})`, parent_id: "n0", ring: null, virtual: true });
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
      pos[id] = { x: x0 + span[id] / 2, y: depth * LEVEL_H, h: lines[id].length * LINE_H + 22 };
      const total = c.reduce((s, k) => s + span[k.id], 0) + GAP_X * Math.max(0, c.length - 1);
      let x = x0 + (span[id] - total) / 2;
      c.forEach(k => { place(k.id, x, depth + 1); x += span[k.id] + GAP_X; });
    }
    measure("n0"); place("n0", 0, 0);
    const ys = Object.values(pos).map(p => p.y + p.h / 2);
    return { pos, lines, bounds: { x: 0, y: -44, w: span["n0"], h: Math.max(...ys) + 54 } };
  }

  function esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

  function ancestors(nodes, id) {
    const byId = Object.fromEntries(nodes.map(n => [n.id, n])); const out = [];
    let cur = byId[id]; while (cur && cur.parent_id) { out.push(cur.parent_id); cur = byId[cur.parent_id]; }
    return out;
  }

  function nodeSvg(n, p, ls, sk, flags) {
    const ring = n.ring || "none", k = n.kind, col = COLOR[ring], seed = n.id + ":" + n.text.length;
    const x = -W / 2, y = -p.h / 2;
    let shapes = "", textFill = INK, weight = 400, style = "normal", size = 15;
    if (k === "problem") {
      shapes = `<path d="${sk.rectFill(x, y, W, p.h, 12)}" fill="${INK}"/>` +
               `<path d="${sk.rect(x, y, W, p.h, 12, seed, 1.6, 2)}" fill="none" stroke="${INK}" stroke-width="2.4"/>`;
      textFill = "#fff"; weight = 700; size = 16;
    } else if (k === "group") {
      shapes = `<path d="${sk.cloudFill(0, 0, W / 2 + 6, p.h / 2 + 10)}" fill="#fff"/>` +
               `<path d="${sk.cloud(0, 0, W / 2 + 6, p.h / 2 + 10, seed)}" fill="none" stroke="#777" stroke-width="1.5" stroke-dasharray="7 5"/>` +
               `<circle cx="${-W / 2 - 2}" cy="${-p.h / 2 - 18}" r="4" fill="none" stroke="#777" stroke-width="1.3"/><circle cx="${-W / 2 - 12}" cy="${-p.h / 2 - 30}" r="2.5" fill="none" stroke="#777" stroke-width="1.3"/>`;
      textFill = "#555"; style = "italic";
    } else if (k === "option") {
      shapes = `<path d="${sk.rectFill(x, y, W, p.h, 8)}" fill="#fff"/>` +
               `<path d="${sk.hachure(x + 3, y + 3, 16, p.h - 6, 5, seed, 0.6)}" fill="none" stroke="${col}" stroke-width="1.6" opacity=".9"/>` +
               `<path d="${sk.rect(x, y, W, p.h, 8, seed, 1.8, 2)}" fill="none" stroke="${INK}" stroke-width="2.6"/>`;
      weight = 700; size = 16;
    } else if (k === "action") {
      shapes = `<path d="${sk.rectFill(x, y, W, p.h, p.h / 2)}" fill="${BG[ring]}"/>` +
               `<path d="${sk.hachure(x, y, W, p.h, 6, seed, 0.7)}" fill="none" stroke="${col}" stroke-width="1.1" opacity=".45"/>` +
               `<path d="${sk.rect(x, y, W, p.h, p.h / 2, seed, 1.5, 2)}" fill="none" stroke="${col}" stroke-width="2.2"/>`;
      textFill = "#163d27"; weight = 700;
    } else if (k === "consequence") {
      shapes = `<path d="${sk.rectFill(x, y, W, p.h, 10)}" fill="#fff" opacity=".7"/>` +
               `<path d="${sk.rect(x, y, W, p.h, 10, seed, 1.4, 1)}" fill="none" stroke="${col}" stroke-width="1.6" stroke-dasharray="6 5"/>`;
      style = "italic"; textFill = "#3a3a3a";
    } else {  // cause
      shapes = `<path d="${sk.rectFill(x, y, W, p.h, 10)}" fill="${BG[ring]}"/>` +
               `<path d="${sk.rect(x, y, W, p.h, 10, seed, 1.5, 2)}" fill="none" stroke="${col}" stroke-width="2"/>`;
    }
    const tspans = ls.map((l, i) => `<tspan x="0" dy="${i ? LINE_H : 0}">${esc((k === "action" && !i ? "→ " : "") + l)}</tspan>`).join("");
    const ty = -((ls.length - 1) * LINE_H) / 2 + 5;
    let extras = "";
    if (flags.lever) {
      extras += `<path class="lever-ring" d="${sk.ellipse(0, 0, W / 2 + 14, p.h / 2 + 12, seed + ":lever", 2.2)}" fill="none" stroke="#c0392b" stroke-width="2"/>` +
                `<text x="${W / 2 + 6}" y="${-p.h / 2 - 14}" font-size="17" fill="#c0392b" font-family="Caveat, cursive" font-weight="700" transform="rotate(-6 ${W / 2} ${-p.h / 2})">lever!</text>`;
    }
    if (flags.collapsedKids) {
      extras += `<g transform="translate(${W / 2 + 2},${-p.h / 2 + 4})"><path d="${sk.ellipse(0, 0, 13, 13, seed + ":b", 1)}" fill="#fff" stroke="${INK}" stroke-width="1.6"/><text text-anchor="middle" y="5" font-size="14" font-weight="700" fill="${INK}">+${flags.collapsedKids}</text></g>`;
    }
    if (n.shifts_when) {
      extras += `<g transform="translate(${x + 12},${y + 11})"><path d="${sk.ellipse(0, 0, 6, 6, seed + ":s", 0.8)}" fill="#fff" stroke="${col}" stroke-width="1.3"/><title>${esc("moves if: " + n.shifts_when)}</title></g>`;
    }
    const focus = flags.focus ? `<path class="focus-ring" d="${sk.rect(x - 6, y - 6, W + 12, p.h + 12, 14, seed + ":f", 2, 1)}" fill="none" stroke="${COLOR[ring === "none" ? "control" : ring]}" stroke-width="2.2"/>` : "";
    return `${focus}${shapes}${extras}<text text-anchor="middle" y="${ty}" fill="${textFill}" font-size="${size}" font-weight="${weight}" font-style="${style}">${tspans}</text>`;
  }

  function render(svg, graph, opts) {
    opts = opts || {};
    const sk = S();
    const nodes = displayNodes(graph);
    if (opts.expandAll && !state.touched) state.collapsed.clear();
    const focusInWhy = opts.focusId && ancestors(nodes, opts.focusId).includes(WHY_ID);
    if (!state.touched && !opts.expandAll && graph.nodes.some(n => n.kind === "option") && !focusInWhy) state.collapsed.add(WHY_ID);
    if (opts.focusId) ancestors(nodes, opts.focusId).forEach(a => state.collapsed.delete(a));
    const hidden = new Set();
    nodes.forEach(n => { if (ancestors(nodes, n.id).some(a => state.collapsed.has(a))) hidden.add(n.id); });
    const visible = nodes.filter(n => !hidden.has(n.id));
    const { pos, lines, bounds } = layout(visible, state.collapsed);
    const minW = opts.minWidth || 960;
    const vw = Math.max(bounds.w + PAD * 2, minW), vx = bounds.x - (vw - bounds.w) / 2;
    svg.setAttribute("viewBox", `${vx} ${bounds.y - PAD / 2} ${vw} ${bounds.h + PAD}`);
    const levers = new Set(graph.levers || []), crossing = new Set((graph.boundary_edges || []).map(e => e[1]));
    const childCount = id => nodes.filter(n => n.parent_id === id).length;

    let edges = "";
    visible.forEach(n => {
      if (!n.parent_id || !pos[n.parent_id]) return;
      const a = pos[n.parent_id], b = pos[n.id];
      const y1 = a.y + a.h / 2 + 2, y2 = b.y - b.h / 2 - 4, ym = (y1 + y2) / 2;
      const red = crossing.has(n.id), isOpt = n.kind === "option", soft = n.kind === "consequence" || n.kind === "group";
      const color = red ? "#c0392b" : isOpt ? INK : "#8a8a8a";
      const seed = n.parent_id + ">" + n.id;
      edges += `<path d="${sk.curve(a.x, y1, a.x, ym, b.x, ym, b.x, y2, seed, isOpt ? 3 : 2)}" fill="none" stroke="${color}" stroke-width="${red ? 2.6 : isOpt ? 2.2 : 1.5}" ${soft ? 'stroke-dasharray="7 5"' : ""}/>`;
      if (!soft) edges += `<path d="${sk.arrow(b.x, y2, Math.PI / 2, seed, isOpt ? 11 : 8)}" fill="none" stroke="${color}" stroke-width="${isOpt ? 2.2 : 1.6}"/>`;
      if (red) edges += `<path d="${sk.cross((a.x + b.x) / 2, ym, seed, 7)}" fill="none" stroke="#c0392b" stroke-width="2.2"/>`;
    });

    let nodesSvg = "";
    visible.forEach(n => {
      const p = pos[n.id];
      const collapsed = state.collapsed.has(n.id), kidsN = childCount(n.id);
      const cls = ["node", `k-${n.kind}`, `r-${n.ring || "none"}`, levers.has(n.id) ? "lever" : "", opts.focusId === n.id ? "focus" : ""].join(" ");
      const title = n.kind === "group" ? "click to open what is behind the problem" : `${n.text}\n${n.kind} · ${n.ring || "?"}${n.ring_reason ? " · " + n.ring_reason : ""}${n.shifts_when ? "\nmoves if: " + n.shifts_when : ""}`;
      const tilt = n.kind === "problem" ? 0 : sk.tilt(n.id, 1.4);
      nodesSvg += `<g class="${cls}" transform="translate(${p.x},${p.y}) rotate(${tilt})" data-id="${n.id}" style="cursor:pointer"><title>${esc(title)}</title>` +
        nodeSvg(n, p, lines[n.id], sk, { lever: levers.has(n.id), focus: opts.focusId === n.id, collapsedKids: collapsed && kidsN ? kidsN : 0 }) + `</g>`;
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
