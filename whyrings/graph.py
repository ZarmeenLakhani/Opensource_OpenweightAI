"""The decision graph: nodes are causes, edges are "because" links."""

import json
import re
import time
from pathlib import Path

# Inner to outer, following Covey's circles.
RINGS = ("control", "influence", "outside")


class Graph:
    def __init__(self, problem, session_id=None):
        self.session_id = session_id or time.strftime("%Y%m%d-%H%M%S")
        self.problem = problem
        self.nodes = {}
        self.summary = ""
        self.actions = {}  # node_id -> concrete next action
        self.accept = {}  # node_id -> what to accept and where to redirect energy
        self.finished = False
        self._add("n0", problem, parent_id=None, depth=0)

    def _add(self, node_id, text, parent_id, depth):
        self.nodes[node_id] = {
            "id": node_id,
            "text": text.strip(),
            "parent_id": parent_id,
            "depth": depth,
            "ring": None,
            "ring_reason": "",
            "actionable": False,
            "same_as": None,  # "session_id:node_id" of a matching node from a past session
        }
        return self.nodes[node_id]

    def add_cause(self, parent_id, text, ring, reason="", actionable=False):
        parent = self.nodes[parent_id]
        node = self._add(f"n{len(self.nodes)}", text, parent_id, parent["depth"] + 1)
        self.set_ring(node["id"], ring, reason)
        node["actionable"] = bool(actionable)
        return node

    def set_ring(self, node_id, ring, reason=""):
        if ring not in RINGS:
            raise ValueError(f"ring must be one of {RINGS}, got {ring!r}")
        self.nodes[node_id]["ring"] = ring
        self.nodes[node_id]["ring_reason"] = reason

    def children(self, node_id):
        return [n for n in self.nodes.values() if n["parent_id"] == node_id]

    def unclassified(self):
        return [n["id"] for n in self.nodes.values() if n["ring"] is None]

    def boundary_edges(self):
        """Edges where a "why" chain leaves your reach: a control or influence node caused by an outside node."""
        edges = []
        for node in self.nodes.values():
            parent = self.nodes.get(node["parent_id"]) if node["parent_id"] else None
            if parent and parent["ring"] in ("control", "influence") and node["ring"] == "outside":
                edges.append((parent["id"], node["id"]))
        return edges

    def levers(self):
        """The last reachable node before each boundary crossing: usually the best place to act."""
        return sorted({parent for parent, _ in self.boundary_edges()}, key=lambda i: int(i[1:]))

    def dfs_order(self):
        order, stack = [], ["n0"]
        while stack:
            node_id = stack.pop()
            order.append(node_id)
            stack.extend(reversed([c["id"] for c in self.children(node_id)]))
        return order

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "problem": self.problem,
            "nodes": list(self.nodes.values()),
            "boundary_edges": self.boundary_edges(),
            "levers": self.levers(),
            "summary": self.summary,
            "actions": self.actions,
            "accept": self.accept,
        }

    def save(self, data_dir):
        path = Path(data_dir) / "sessions" / f"{self.session_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path


def _tokens(text):
    stop = {"i", "a", "the", "to", "my", "and", "of", "it", "is", "in", "too", "so", "at", "on", "me", "because"}
    return {t for t in re.findall(r"[a-z']+", text.lower()) if t not in stop and len(t) > 2}


def load_sessions(data_dir):
    folder = Path(data_dir) / "sessions"
    if not folder.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]


def search_history(data_dir, text, exclude_session=None, limit=5):
    """Past nodes that share words with `text`, scored by Jaccard overlap."""
    query = _tokens(text)
    hits = []
    for session in load_sessions(data_dir):
        if session["session_id"] == exclude_session:
            continue
        for node in session["nodes"]:
            words = _tokens(node["text"])
            if not query or not words:
                continue
            score = len(query & words) / len(query | words)
            if score >= 0.2:
                hits.append({
                    "ref": f"{session['session_id']}:{node['id']}",
                    "text": node["text"],
                    "ring": node["ring"],
                    "problem": session["problem"],
                    "score": round(score, 2),
                })
    return sorted(hits, key=lambda h: -h["score"])[:limit]


def recurring_roots(data_dir):
    """Group nodes linked with `same_as` across sessions; the biggest groups are the highest-leverage causes."""
    sessions = load_sessions(data_dir)
    by_ref = {f"{s['session_id']}:{n['id']}": n for s in sessions for n in s["nodes"]}

    def canonical(ref, seen=()):
        node = by_ref.get(ref)
        if node and node["same_as"] and node["same_as"] in by_ref and ref not in seen:
            return canonical(node["same_as"], seen + (ref,))
        return ref

    groups = {}
    for s in sessions:
        for n in s["nodes"]:
            root = canonical(f"{s['session_id']}:{n['id']}")
            group = groups.setdefault(root, {"text": by_ref[root]["text"], "ring": by_ref[root]["ring"], "problems": []})
            if s["problem"] not in group["problems"]:
                group["problems"].append(s["problem"])
    ranked = [g for g in groups.values() if len(g["problems"]) > 1]
    return sorted(ranked, key=lambda g: (-len(g["problems"]), RINGS.index(g["ring"]) if g["ring"] in RINGS else 3))
