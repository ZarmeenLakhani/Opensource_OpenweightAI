// LifeGraphSketch: hand-drawn SVG primitives. Every shape is drawn twice with a seeded wobble, the way a
// pen goes over a line, so the same node always looks the same across re-renders. No dependencies.
(function () {
  function rng(seed) {
    let s = 2166136261;
    for (const ch of String(seed)) s = Math.imul(s ^ ch.charCodeAt(0), 16777619) >>> 0;
    return () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
  }
  const jit = (r, amp) => (r() * 2 - 1) * amp;
  const f = n => Math.round(n * 10) / 10;

  // One wobbly stroke from a to b: a cubic whose control points drift off the straight line.
  function stroke(r, x1, y1, x2, y2, amp) {
    const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1, nx = -dy / len, ny = dx / len;
    const o1 = jit(r, amp), o2 = jit(r, amp);
    const c1x = x1 + dx * 0.3 + nx * o1, c1y = y1 + dy * 0.3 + ny * o1;
    const c2x = x1 + dx * 0.7 + nx * o2, c2y = y1 + dy * 0.7 + ny * o2;
    return `M${f(x1 + jit(r, amp * 0.5))} ${f(y1 + jit(r, amp * 0.5))} C${f(c1x)} ${f(c1y)}, ${f(c2x)} ${f(c2y)}, ${f(x2 + jit(r, amp * 0.5))} ${f(y2 + jit(r, amp * 0.5))}`;
  }

  function roundedPoints(x, y, w, h, rx) {
    rx = Math.min(rx, w / 2, h / 2);
    const pts = [];
    const corner = (cx, cy, a0) => { for (let i = 0; i <= 3; i++) { const a = a0 + (i * Math.PI) / 6; pts.push([cx + rx * Math.cos(a), cy + rx * Math.sin(a)]); } };
    corner(x + w - rx, y + rx, -Math.PI / 2); corner(x + w - rx, y + h - rx, 0);
    corner(x + rx, y + h - rx, Math.PI / 2); corner(x + rx, y + rx, Math.PI);
    return pts;
  }

  function outline(points, seed, amp, passes) {
    const r = rng(seed); let d = "";
    for (let p = 0; p < (passes || 2); p++) {
      for (let i = 0; i < points.length; i++) {
        const a = points[i], b = points[(i + 1) % points.length];
        const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
        d += stroke(r, a[0], a[1], b[0], b[1], Math.min(amp, len / 6)) + " ";
      }
    }
    return d;
  }

  // Clean (non-wobbly) closed path for fills, so the fill never leaks past the sketched outline.
  function solid(points) {
    return "M" + points.map(p => `${f(p[0])} ${f(p[1])}`).join(" L") + " Z";
  }

  function rect(x, y, w, h, rx, seed, amp, passes) { return outline(roundedPoints(x, y, w, h, rx), seed, amp == null ? 1.4 : amp, passes); }
  function rectFill(x, y, w, h, rx) { return solid(roundedPoints(x, y, w, h, rx)); }

  function ellipsePoints(cx, cy, rx, ry, n, wobble) {
    const pts = [];
    for (let i = 0; i < n; i++) { const a = (i / n) * Math.PI * 2; const k = 1 + (wobble ? wobble(a) : 0); pts.push([cx + rx * k * Math.cos(a), cy + ry * k * Math.sin(a)]); }
    return pts;
  }
  function ellipse(cx, cy, rx, ry, seed, amp) { return outline(ellipsePoints(cx, cy, rx, ry, 24), seed, amp == null ? 1.6 : amp); }
  // A thought cloud: an ellipse with soft bumps.
  function cloud(cx, cy, rx, ry, seed) { return outline(ellipsePoints(cx, cy, rx, ry, 36, a => 0.09 * Math.sin(a * 7) + 0.04 * Math.cos(a * 3)), seed, 1.2, 1); }
  function cloudFill(cx, cy, rx, ry) { return solid(ellipsePoints(cx, cy, rx, ry, 36, a => 0.09 * Math.sin(a * 7) + 0.04 * Math.cos(a * 3))); }

  // Diagonal pen hatching clipped to a rectangle.
  function hachure(x, y, w, h, gap, seed, amp) {
    const r = rng(seed + ":h"); let d = "";
    for (let c = x - (y + h) - gap; c <= x + w - y + gap; c += gap) {
      // line x - y = c; find its segment inside the rect
      const pts = [];
      const yAtX = xx => xx - c, xAtY = yy => yy + c;
      if (yAtX(x) >= y && yAtX(x) <= y + h) pts.push([x, yAtX(x)]);
      if (yAtX(x + w) >= y && yAtX(x + w) <= y + h) pts.push([x + w, yAtX(x + w)]);
      if (xAtY(y) > x && xAtY(y) < x + w) pts.push([xAtY(y), y]);
      if (xAtY(y + h) > x && xAtY(y + h) < x + w) pts.push([xAtY(y + h), y + h]);
      if (pts.length >= 2) d += stroke(r, pts[0][0], pts[0][1], pts[1][0], pts[1][1], amp == null ? 0.8 : amp) + " ";
    }
    return d;
  }

  // A wobbly curve drawn twice, for edges.
  function curve(x1, y1, c1x, c1y, c2x, c2y, x2, y2, seed, amp) {
    const r = rng(seed + ":c"); amp = amp == null ? 2 : amp; let d = "";
    for (let p = 0; p < 2; p++) {
      d += `M${f(x1 + jit(r, 1))} ${f(y1 + jit(r, 1))} C${f(c1x + jit(r, amp * 2))} ${f(c1y + jit(r, amp))}, ${f(c2x + jit(r, amp * 2))} ${f(c2y + jit(r, amp))}, ${f(x2 + jit(r, 1))} ${f(y2 + jit(r, 1))} `;
    }
    return d;
  }

  // Two short pen strokes making an arrowhead pointing along `angle` (radians) at (x, y).
  function arrow(x, y, angle, seed, size) {
    const r = rng(seed + ":a"); size = size || 9; let d = "";
    for (const side of [-1, 1]) {
      const a = angle + Math.PI + side * 0.5;
      d += stroke(r, x, y, x + size * Math.cos(a), y + size * Math.sin(a), 0.8) + " ";
    }
    return d;
  }

  // A small scribbled cross, used where a chain leaves the person's reach.
  function cross(x, y, seed, size) {
    const r = rng(seed + ":x"); size = size || 6;
    return stroke(r, x - size, y - size, x + size, y + size, 1) + " " + stroke(r, x - size, y + size, x + size, y - size, 1);
  }

  // Hand-placed feel: a small, stable rotation per element.
  function tilt(seed, max) { const r = rng(seed + ":t"); return f((r() * 2 - 1) * (max == null ? 1.2 : max)); }

  window.LifeGraphSketch = { rect, rectFill, ellipse, cloud, cloudFill, hachure, curve, arrow, cross, tilt, rng };
})();
