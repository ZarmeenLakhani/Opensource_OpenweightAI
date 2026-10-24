"""The decision graph: nodes are causes, actions or consequences; edges are "because" / "could do" / "would lead to" links."""

import json
import re
import time
from pathlib import Path

# Not nested: three distinct regions a node can sit in.
RINGS = ("control", "influence", "outside")
KINDS = ("problem", "cause", "action", "consequence")


class Graph:
    def __init__(self, problem, session_id=None):
        self.session_id = session_id or time.strftime("%Y%m%d-%H%M%S")
        self.problem = problem
        self.nodes = {}
        self._next = 0
        self.summary = ""
        self.next_move = ""  # the one smallest useful action
        self.actions = {}  # node_id -> concrete action for that node (levers, usually)
        self.accept = {}  # node_id -> what to let go of and where to refocus
        self.user_edits = []  # log of map changes the person made
        self.finished = False
        self.add_node(None, problem, kind="problem")

    def add_node(self, parent_id, text, kind, ring=None, reason="", actionable=False, shifts_when=""):
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
        if parent_id is not None and parent_id not in self.nodes:
            raise KeyError(parent_id)
        node_id = f"n{self._next}"
        self._next += 1
        depth = 0 if parent_id is None else self.nodes[parent_id]["depth"] + 1
        self.nodes[node_id] = {
            "id": node_id,
            "text": text.strip(),
            "kind": kind,
            "parent_id": parent_id,
            "depth": depth,
            "ring": None,
            "ring_reason": "",
            "shifts_when": "",  # condition under which this would move to another ring
            "actionable": bool(actionable),
            "same_as": None,  # "session_id:node_id" of a matching node from a past session
        }
        if ring is not None:
            self.set_ring(node_id, ring, reason, shifts_when)
        return self.nodes[node_id]

    def add_cause(self, parent_id, text, ring, reason="", actionable=False, shifts_when=""):
        return self.add_node(parent_id, text, "cause", ring, reason, actionable, shifts_when)

    def add_action(self, parent_id, text, ring, reason=""):
        if ring == "outside":
            raise ValueError("an action is something the person can do; it cannot sit in 'outside'")
        return self.add_node(parent_id, text, "action", ring, reason, actionable=True)

    def add_consequence(self, parent_id, text, ring, reason=""):
        return self.add_node(parent_id, text, "consequence", ring, reason)

    def set_ring(self, node_id, ring, reason="", shifts_when=""):
        if ring not in RINGS:
            raise ValueError(f"ring must be one of {RINGS}, got {ring!r}")
        node = self.nodes[node_id]
        node["ring"] = ring
        if reason:
            node["ring_reason"] = reason
        if shifts_when:
            node["shifts_when"] = shifts_when

    def rename(self, node_id, text):
        self.nodes[node_id]["text"] = text.strip()

    def delete_branch(self, node_id):
        if node_id == "n0":
            raise ValueError("cannot delete the problem itself")
        removed = []
        stack = [node_id]
        while stack:
            current = stack.pop()
            stack.extend(c["id"] for c in self.children(current))
            removed.append(current)
            del self.nodes[current]
        for store in (self.actions, self.accept):
            for rid in removed:
                store.pop(rid, None)
        return removed

    def children(self, node_id):
        return [n for n in self.nodes.values() if n["parent_id"] == node_id]

    def unclassified(self):
        return [n["id"] for n in self.nodes.values() if n["ring"] is None]

    def boundary_edges(self):
        """Edges where a cause chain leaves the person's reach: a reachable node explained by an outside one."""
        edges = []
        for node in self.nodes.values():
            if node["kind"] != "cause":
                continue
            parent = self.nodes.get(node["parent_id"]) if node["parent_id"] else None
            if parent and parent["ring"] in ("control", "influence") and node["ring"] == "outside":
                edges.append((parent["id"], node["id"]))
        return edges

    def levers(self):
        """The last reachable node before each boundary crossing: usually the best place to act."""
        return sorted({parent for parent, _ in self.boundary_edges()}, key=lambda i: int(i[1:]))

    def by_ring(self, kind=None):
        out = {ring: [] for ring in RINGS}
        for node_id in self.dfs_order():
            node = self.nodes[node_id]
            if node["ring"] and (kind is None or node["kind"] == kind):
                out[node["ring"]].append(node)
        return out

    def dfs_order(self):
        order, stack = [], ["n0"]
        while stack:
            node_id = stack.pop()
            order.append(node_id)
            stack.extend(reversed([c["id"] for c in self.children(node_id)]))
        return order

    def outline(self):
        """Plain-text tree, used by the CLI and sent to the model after the person edits the map."""
        levers = set(self.levers())
        lines = []
        for node_id in self.dfs_order():
            n = self.nodes[node_id]
            glyph = {"problem": "!", "cause": "?", "action": ">", "consequence": "~"}[n["kind"]]
            mark = "  <- lever" if node_id in levers else ""
            shift = f"  (moves if: {n['shifts_when']})" if n["shifts_when"] else ""
            lines.append(f"{'  ' * n['depth']}{glyph} {node_id} [{n['ring'] or '?'}] {n['text']}{shift}{mark}")
        return "\n".join(lines)

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "problem": self.problem,
            "nodes": list(self.nodes.values()),
            "boundary_edges": self.boundary_edges(),
            "levers": self.levers(),
            "summary": self.summary,
            "next_move": self.next_move,
            "actions": self.actions,
            "accept": self.accept,
            "user_edits": self.user_edits,
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
                    "kind": node.get("kind", "cause"),
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
