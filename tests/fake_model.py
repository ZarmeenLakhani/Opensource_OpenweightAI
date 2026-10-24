"""A stand-in for an OpenAI-compatible client that replays a scripted list of tool calls.

Lets the agent loop, tool runner, graph and renderer run end to end with no model server.
"""

import json
from types import SimpleNamespace


class FakeClient:
    def __init__(self, script):
        self.script = list(script)  # each item: (tool_name, args_dict)
        self.seen_messages = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, tools, tool_choice, temperature):
        self.seen_messages = list(messages)
        if not self.script:
            raise AssertionError("script exhausted; the agent kept asking for more turns")
        name, args = self.script.pop(0)
        call = SimpleNamespace(
            id=f"call_{len(self.seen_messages)}",
            function=SimpleNamespace(name=name, arguments=json.dumps(args)),
        )
        message = SimpleNamespace(content="", tool_calls=[call])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


# The career example from the product spec: four whys, one clarify, one what-if, then actions.
JOB_PROBLEM = "I hate my job. I feel like I'm wasting my potential."

JOB_SCRIPT = [
    ("set_ring", {"node_id": "n0", "ring": "influence", "reason": "staying or leaving is my call, but the job itself is not"}),
    ("ask", {"node_id": "n0", "kind": "why", "question": "Why does your job feel like a waste?"}),
    ("add_cause", {"parent_id": "n0", "text": "Executing other people's ideas instead of building something myself", "ring": "influence", "reason": "I could ask for more ownership", "actionable": True}),
    ("ask", {"node_id": "n1", "kind": "why", "question": "Why does that bother you?"}),
    ("add_cause", {"parent_id": "n1", "text": "I want ownership over outcomes, not just deliverables", "ring": "control", "reason": "a value I hold", "actionable": False}),
    ("ask", {"node_id": "n2", "kind": "why", "question": "Why aren't you pursuing ownership?"}),
    ("add_cause", {"parent_id": "n2", "text": "I need financial stability", "ring": "influence", "reason": "I can change my runway, not the need", "actionable": True}),
    ("ask", {"node_id": "n3", "kind": "why", "question": "Why does that keep you stuck?"}),
    ("add_cause", {"parent_id": "n3", "text": "No clear alternative worth the risk", "ring": "control", "reason": "finding one is work I can do", "actionable": True}),
    ("ask", {"node_id": "n4", "kind": "clarify", "question": "What would make a change feel safe enough?"}),
    ("add_cause", {"parent_id": "n4", "text": "No tested idea or evidence of demand yet", "ring": "control", "reason": "testing is mine to do", "actionable": True}),
    ("add_cause", {"parent_id": "n4", "text": "Not enough savings for a transition", "ring": "control", "reason": "a target I can set", "actionable": True, "shifts_when": "becomes a non-issue once savings cover 6 months"}),
    ("ask", {"node_id": "n5", "kind": "what_if", "question": "What if you tested one idea while staying employed?"}),
    ("add_consequence", {"parent_id": "n5", "text": "I'd learn whether anyone wants it without quitting", "ring": "control", "reason": "evidence without risk"}),
    ("add_action", {"parent_id": "n5", "text": "Build a prototype", "ring": "control", "reason": "evenings and weekends"}),
    ("add_action", {"parent_id": "n5", "text": "Test customer demand", "ring": "control", "reason": "interviews cost time, not money"}),
    ("add_action", {"parent_id": "n6", "text": "Set a savings target", "ring": "control", "reason": "a number I choose"}),
    ("add_action", {"parent_id": "n1", "text": "Negotiate ownership of one project", "ring": "influence", "reason": "my manager decides"}),
    ("add_action", {"parent_id": "n4", "text": "Find a cofounder", "ring": "influence", "reason": "depends on who says yes"}),
    ("add_cause", {"parent_id": "n3", "text": "Whether the economy stays stable", "ring": "outside", "reason": "not mine", "actionable": False}),
    ("finish", {
        "summary": "The job itself is not the blocker; the missing piece is evidence that an alternative is worth the risk. Everything needed to get that evidence sits in your control.",
        "next_move": "Spend two hours this week interviewing three potential customers about one idea. No resignation required.",
        "actions": {"n3": "Write down the monthly number that would make a transition safe, by Friday."},
        "accept": {"n13": "You cannot time the economy. Focus on evidence of demand, which you can gather now."},
    }),
]

JOB_ANSWERS = [
    "Because I'm executing other people's ideas instead of building something myself.",
    "Because I want ownership over outcomes, not just deliverables.",
    "Because I need financial stability.",
    "Because I don't have a clear alternative worth the risk.",
    "A tested idea, evidence of demand, and enough savings to make a transition.",
    "I'd find out if anyone wants it without quitting.",
]
