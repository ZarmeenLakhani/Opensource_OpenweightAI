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


# The worked example from the design: gym skipping traced to a time-zone gap.
GYM_SCRIPT = [
    ("set_ring", {"node_id": "n0", "ring": "control", "reason": "going to the gym is my own act"}),
    ("ask_why", {"node_id": "n0", "question": "What usually gets in the way on a gym day?"}),
    ("add_cause", {"parent_id": "n0", "text": "Too tired after work", "ring": "influence", "reason": "energy depends on the workday", "actionable": False}),
    ("ask_why", {"node_id": "n1", "question": "Why are you so tired by the end of work?"}),
    ("add_cause", {"parent_id": "n1", "text": "I work late most days", "ring": "influence", "reason": "I set my hours within limits", "actionable": True}),
    ("ask_why", {"node_id": "n2", "question": "What pushes the work late?"}),
    ("add_cause", {"parent_id": "n2", "text": "Meetings pile up in the afternoon", "ring": "influence", "reason": "I can ask to move some", "actionable": True}),
    ("ask_why", {"node_id": "n3", "question": "Who sets those afternoon meetings?"}),
    ("search_history", {"text": "manager schedules meetings"}),
    ("add_cause", {"parent_id": "n3", "text": "My manager schedules them", "ring": "outside", "reason": "their call, not mine", "actionable": False}),
    ("ask_why", {"node_id": "n4", "question": "Why does your manager put them in the afternoon?"}),
    ("add_cause", {"parent_id": "n4", "text": "The team is 8 hours ahead", "ring": "outside", "reason": "geography", "actionable": False}),
    ("finish", {
        "summary": "Gym skipping traces to afternoon meetings that run the day late. The chain leaves your reach at your manager's calendar.",
        "actions": {"n3": "On Monday, ask to move two afternoon meetings to 9am.", "n2": "Block 6 to 7pm on your calendar every weekday."},
        "accept": {"n4": "You do not own your manager's calendar. Focus on the two meetings you can ask about."},
    }),
]

GYM_ANSWERS = [
    "I'm too tired after work",
    "I work late most days",
    "Meetings pile up in the afternoon",
    "My manager schedules them",
    "The team is 8 hours ahead",
]
