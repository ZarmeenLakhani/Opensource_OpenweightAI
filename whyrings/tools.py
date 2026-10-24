"""Tool schemas the model sees, and the Python functions behind them."""

import json

from .graph import RINGS, search_history

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_ring",
            "description": "Place a node in a ring. Required for n0 before any ask_why.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string"},
                    "ring": {"type": "string", "enum": list(RINGS)},
                    "reason": {"type": "string", "description": "One short clause on why this ring."},
                },
                "required": ["node_id", "ring", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_why",
            "description": "Ask the person one 'why' question about one node. Returns their answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "The node you are probing."},
                    "question": {"type": "string", "description": "One short question in plain words."},
                },
                "required": ["node_id", "question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_cause",
            "description": "Record one cause under a parent node and place it in a ring.",
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_id": {"type": "string"},
                    "text": {"type": "string", "description": "The cause, as a concrete situation or behaviour."},
                    "ring": {"type": "string", "enum": list(RINGS)},
                    "reason": {"type": "string"},
                    "actionable": {
                        "type": "boolean",
                        "description": "True if the person could do something specific about this cause this week.",
                    },
                },
                "required": ["parent_id", "text", "ring", "reason", "actionable"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_history",
            "description": "Find causes from past sessions that look like this text.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "link_past",
            "description": "Mark a node in this session as the same cause as a node from a past session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string"},
                    "past_ref": {"type": "string", "description": "A ref returned by search_history, like 20261024-1200:n3."},
                },
                "required": ["node_id", "past_ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "End the session with a summary, next actions for lever nodes, and what to accept.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "actions": {
                        "type": "object",
                        "description": "node_id -> one concrete next action with a when.",
                        "additionalProperties": {"type": "string"},
                    },
                    "accept": {
                        "type": "object",
                        "description": "node_id of an outside node -> what to let go of and where to refocus.",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["summary", "actions", "accept"],
            },
        },
    },
]

MAX_DEPTH = 5


class ToolRunner:
    """Executes tool calls against a Graph. `ask_user` is how a question reaches the person."""

    def __init__(self, graph, ask_user, data_dir):
        self.graph = graph
        self.ask_user = ask_user
        self.data_dir = data_dir
        self.questions_asked = 0

    def run(self, name, args):
        handler = getattr(self, f"_{name}", None)
        if handler is None:
            return {"error": f"unknown tool {name}"}
        try:
            return handler(**args)
        except (KeyError, ValueError, TypeError) as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    def _set_ring(self, node_id, ring, reason=""):
        self.graph.set_ring(node_id, ring, reason)
        return {"ok": True, "node": self.graph.nodes[node_id]}

    def _ask_why(self, node_id, question):
        if node_id not in self.graph.nodes:
            return {"error": f"no node {node_id}"}
        if self.graph.unclassified():
            return {"error": f"classify these nodes first with set_ring: {self.graph.unclassified()}"}
        if self.graph.nodes[node_id]["depth"] >= MAX_DEPTH:
            return {"error": f"{node_id} is at depth {MAX_DEPTH}; stop probing this branch"}
        self.questions_asked += 1
        answer = self.ask_user(question)
        return {"answer": answer, "questions_asked": self.questions_asked}

    def _add_cause(self, parent_id, text, ring, reason="", actionable=False):
        node = self.graph.add_cause(parent_id, text, ring, reason, actionable)
        hint = ""
        if ring == "outside" and self.graph.nodes[parent_id]["ring"] != "outside":
            hint = f"{parent_id} is now a lever: the last reachable node before this chain leaves the person's control."
        return {"ok": True, "node": node, "hint": hint}

    def _search_history(self, text):
        return {"matches": search_history(self.data_dir, text, exclude_session=self.graph.session_id)}

    def _link_past(self, node_id, past_ref):
        self.graph.nodes[node_id]["same_as"] = past_ref
        return {"ok": True}

    def _finish(self, summary, actions, accept):
        missing = [lever for lever in self.graph.levers() if lever not in actions]
        if missing:
            return {"error": f"actions is missing these lever nodes: {missing}"}
        self.graph.summary = summary
        self.graph.actions = {k: v for k, v in actions.items() if k in self.graph.nodes}
        self.graph.accept = {k: v for k, v in accept.items() if k in self.graph.nodes}
        self.graph.finished = True
        return {"ok": True}


def parse_args(raw):
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
