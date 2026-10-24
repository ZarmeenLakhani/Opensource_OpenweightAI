"""Tool schemas the model sees, the Python behind them, and the commands the person can type to edit the map."""

import json

from .graph import RINGS, search_history

ASK_KINDS = ("why", "clarify", "what_if")
MAX_DEPTH = 5
MAX_QUESTIONS = 12

_ring_prop = {"type": "string", "enum": list(RINGS)}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_ring",
            "description": "Place a node in a region, or move it. Required for n0 before any ask.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string"},
                    "ring": _ring_prop,
                    "reason": {"type": "string", "description": "One short clause on why this region."},
                    "shifts_when": {
                        "type": "string",
                        "description": "Optional: the condition under which this would move to another region.",
                    },
                },
                "required": ["node_id", "ring", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask",
            "description": "Ask the person one question about one node. Returns their answer, plus any edits they made to the map.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "The node you are probing."},
                    "kind": {"type": "string", "enum": list(ASK_KINDS)},
                    "question": {"type": "string", "description": "One short question in plain words."},
                },
                "required": ["node_id", "kind", "question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_cause",
            "description": "Record one cause under a node and place it in a region.",
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_id": {"type": "string"},
                    "text": {"type": "string", "description": "The cause, as a concrete situation or behaviour."},
                    "ring": _ring_prop,
                    "reason": {"type": "string"},
                    "actionable": {"type": "boolean", "description": "True if the person could do something specific about it this week."},
                    "shifts_when": {"type": "string", "description": "Optional: condition under which it would move region."},
                },
                "required": ["parent_id", "text", "ring", "reason", "actionable"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_action",
            "description": "Record something concrete the person could do, under the cause it addresses. control or influence only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_id": {"type": "string"},
                    "text": {"type": "string"},
                    "ring": {"type": "string", "enum": ["control", "influence"]},
                    "reason": {"type": "string"},
                },
                "required": ["parent_id", "text", "ring", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_option",
            "description": "Record a path the person could take (stay, change within, leave), under n0. control or influence only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_id": {"type": "string"},
                    "text": {"type": "string", "description": "The path, phrased concretely for this person."},
                    "ring": {"type": "string", "enum": ["control", "influence"]},
                    "reason": {"type": "string"},
                },
                "required": ["parent_id", "text", "ring", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_consequence",
            "description": "Record what the person said a path or what-if would lead to, under the option or node the question was about.",
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_id": {"type": "string"},
                    "text": {"type": "string"},
                    "ring": _ring_prop,
                    "reason": {"type": "string"},
                },
                "required": ["parent_id", "text", "ring", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_history",
            "description": "Find nodes from past sessions that look like this text.",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "link_past",
            "description": "Mark a node in this session as the same thing as a node from a past session.",
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
            "description": "End the session with a summary, the one next move, actions for lever nodes, and what to accept.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "next_move": {"type": "string", "description": "One small concrete step for this week, with a when and a size."},
                    "actions": {
                        "type": "object",
                        "description": "node_id -> one concrete action, for every lever node.",
                        "additionalProperties": {"type": "string"},
                    },
                    "accept": {
                        "type": "object",
                        "description": "node_id of an outside node -> what to let go of and where to refocus.",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["summary", "next_move", "actions", "accept"],
            },
        },
    },
]

USER_COMMANDS = """You can edit the map instead of answering:
  /map                      show the map so far
  /move n3 influence        put a node in control, influence or outside
  /edit n2 <new wording>    correct how the agent phrased something
  /delete n4                remove a branch you don't agree with
  /explore n1               ask the agent to follow a different node next
  /help                     show this list"""


def apply_user_command(graph, text):
    """Apply a /command to the graph. Returns (handled, note, request)."""
    parts = text.strip().split(maxsplit=2)
    cmd = parts[0].lower()
    try:
        if cmd == "/help":
            return True, USER_COMMANDS, None
        if cmd == "/map":
            return True, graph.outline(), None
        if cmd == "/move" and len(parts) == 3:
            node_id, ring = parts[1], parts[2].strip().lower()
            graph.set_ring(node_id, ring, reason="moved by the person")
            graph.user_edits.append({"op": "move", "node_id": node_id, "ring": ring})
            return True, f"Moved {node_id} to {ring}.", None
        if cmd == "/edit" and len(parts) == 3:
            graph.rename(parts[1], parts[2])
            graph.user_edits.append({"op": "edit", "node_id": parts[1], "text": parts[2]})
            return True, f"Reworded {parts[1]}.", None
        if cmd == "/delete" and len(parts) >= 2:
            removed = graph.delete_branch(parts[1])
            graph.user_edits.append({"op": "delete", "node_ids": removed})
            return True, f"Removed {', '.join(removed)}.", None
        if cmd == "/explore" and len(parts) >= 2:
            if parts[1] not in graph.nodes:
                return True, f"No node {parts[1]}.", None
            graph.user_edits.append({"op": "explore", "node_id": parts[1]})
            return True, f"Okay, the agent will follow {parts[1]} next.", f"probe {parts[1]} next instead of the current node"
    except (KeyError, ValueError) as exc:
        return True, f"Could not do that: {exc}", None
    return True, f"Unknown command. {USER_COMMANDS}", None


class ToolRunner:
    """Executes tool calls against a Graph. `ask_user(question) -> str` is how a question reaches the person.

    `notify(text)` shows the person the result of a /command; defaults to print.
    """

    def __init__(self, graph, ask_user, data_dir, notify=print):
        self.graph = graph
        self.ask_user = ask_user
        self.data_dir = data_dir
        self.notify = notify
        self.questions_asked = 0
        self.what_ifs_asked = 0

    def run(self, name, args):
        handler = getattr(self, f"_{name}", None)
        if handler is None:
            return {"error": f"unknown tool {name}"}
        try:
            return handler(**args)
        except (KeyError, ValueError, TypeError) as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    def _set_ring(self, node_id, ring, reason="", shifts_when=""):
        self.graph.set_ring(node_id, ring, reason, shifts_when)
        return {"ok": True, "node": self.graph.nodes[node_id]}

    def _ask(self, node_id, kind, question):
        if node_id not in self.graph.nodes:
            return {"error": f"no node {node_id}"}
        if kind not in ASK_KINDS:
            return {"error": f"kind must be one of {ASK_KINDS}"}
        if self.graph.unclassified():
            return {"error": f"classify these nodes first with set_ring: {self.graph.unclassified()}"}
        if kind == "why" and self.graph.nodes[node_id]["depth"] >= MAX_DEPTH:
            return {"error": f"{node_id} is at depth {MAX_DEPTH}; no more why on this branch (what_if and clarify are fine)"}
        if self.questions_asked >= MAX_QUESTIONS:
            return {"error": f"{MAX_QUESTIONS} questions asked; call finish"}

        self.questions_asked += 1
        if kind == "what_if":
            self.what_ifs_asked += 1

        edits, request = [], None
        prompt = question
        while True:
            answer = self.ask_user(prompt)
            if not answer.startswith("/"):
                break
            _, note, req = apply_user_command(self.graph, answer)
            self.notify(note)
            if answer.split()[0].lower() not in ("/help", "/map"):
                edits.append(answer)
            if req:
                request = req
                answer = ""
                break
            prompt = question  # ask the same question again after an edit

        result = {"answer": answer, "questions_asked": self.questions_asked}
        if edits:
            result["user_edits"] = edits
            result["outline"] = self.graph.outline()
        if request:
            result["user_request"] = request
        return result

    def _add_cause(self, parent_id, text, ring, reason="", actionable=False, shifts_when=""):
        node = self.graph.add_cause(parent_id, text, ring, reason, actionable, shifts_when)
        hint = ""
        if ring == "outside" and self.graph.nodes[parent_id]["ring"] != "outside":
            hint = f"{parent_id} is now a lever: the last reachable node before this chain leaves the person's control."
        return {"ok": True, "node": node, "hint": hint}

    def _add_action(self, parent_id, text, ring, reason=""):
        return {"ok": True, "node": self.graph.add_action(parent_id, text, ring, reason)}

    def _add_option(self, parent_id, text, ring, reason=""):
        return {"ok": True, "node": self.graph.add_option(parent_id, text, ring, reason)}

    def _add_consequence(self, parent_id, text, ring, reason=""):
        return {"ok": True, "node": self.graph.add_consequence(parent_id, text, ring, reason)}

    def _search_history(self, text):
        return {"matches": search_history(self.data_dir, text, exclude_session=self.graph.session_id)}

    def _link_past(self, node_id, past_ref):
        self.graph.nodes[node_id]["same_as"] = past_ref
        return {"ok": True}

    def _finish(self, summary, next_move, actions, accept):
        if not next_move.strip():
            return {"error": "next_move must be one concrete step"}
        missing = [lever for lever in self.graph.levers() if lever not in actions]
        if missing:
            return {"error": f"actions is missing these lever nodes: {missing}"}
        if self.what_ifs_asked == 0 and self.questions_asked < MAX_QUESTIONS:
            return {"error": "ask at least one what_if before finishing"}
        if len(self.graph.options()) < 2 and self.questions_asked < MAX_QUESTIONS:
            return {"error": "lay out at least two paths with add_option before finishing"}
        not_outside = [k for k in accept if k in self.graph.nodes and self.graph.nodes[k]["ring"] != "outside"]
        if not_outside:
            return {"error": f"accept is only for outside nodes; these are not: {not_outside}"}
        self.graph.summary = summary
        self.graph.next_move = next_move.strip()
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
