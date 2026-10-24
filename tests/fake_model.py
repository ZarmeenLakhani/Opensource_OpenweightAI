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


# The career example: a few probes into what bothers the person, then three paths with a what-if each.
JOB_PROBLEM = "I hate my job. I feel like I'm wasting my potential."

JOB_SCRIPT = [
    ("set_ring", {"node_id": "n0", "ring": "influence", "reason": "staying or leaving is my call, but the job itself is not"}),
    # what bothers me
    ("ask", {"node_id": "n0", "kind": "why", "question": "What exactly feels like a waste?"}),
    ("add_cause", {"parent_id": "n0", "text": "Executing other people's ideas instead of building something myself", "ring": "influence", "reason": "I could ask for more ownership", "actionable": True}),  # n1
    ("ask", {"node_id": "n1", "kind": "clarify", "question": "What would you want instead?"}),
    ("add_cause", {"parent_id": "n1", "text": "Ownership over outcomes, not just deliverables", "ring": "control", "reason": "a value I hold", "actionable": False}),  # n2
    ("ask", {"node_id": "n2", "kind": "why", "question": "What has stopped you going after that?"}),
    ("add_cause", {"parent_id": "n2", "text": "I need financial stability", "ring": "influence", "reason": "I can change my runway, not the need", "actionable": True, "shifts_when": "becomes a non-issue once savings cover 6 months"}),  # n3
    ("add_cause", {"parent_id": "n3", "text": "Whether the economy stays stable", "ring": "outside", "reason": "not mine", "actionable": False}),  # n4
    # the paths
    ("add_option", {"parent_id": "n0", "text": "Stay another year and change nothing", "ring": "control", "reason": "my choice"}),  # n5
    ("add_option", {"parent_id": "n0", "text": "Ask to own one project end to end", "ring": "influence", "reason": "my manager decides"}),  # n6
    ("add_option", {"parent_id": "n0", "text": "Test one idea on the side", "ring": "control", "reason": "evenings are mine"}),  # n7
    # what each path leads to
    ("ask", {"node_id": "n5", "kind": "what_if", "question": "What happens if you stay as is for another year?"}),
    ("add_consequence", {"parent_id": "n5", "text": "Salary stays, resentment grows, nothing learned", "ring": "control", "reason": "a result of my choice"}),  # n8
    ("ask", {"node_id": "n6", "kind": "what_if", "question": "What if you asked to own one project end to end?"}),
    ("add_consequence", {"parent_id": "n6", "text": "I'd know within a month whether ownership is possible here", "ring": "influence", "reason": "their answer"}),  # n9
    ("add_action", {"parent_id": "n6", "text": "Negotiate ownership of one project", "ring": "influence", "reason": "my manager decides"}),  # n10
    ("ask", {"node_id": "n7", "kind": "what_if", "question": "What if you tested one idea while staying employed?"}),
    ("add_consequence", {"parent_id": "n7", "text": "I'd learn whether anyone wants it without quitting", "ring": "control", "reason": "evidence without risk"}),  # n11
    ("add_action", {"parent_id": "n7", "text": "Build a prototype", "ring": "control", "reason": "evenings and weekends"}),  # n12
    ("add_action", {"parent_id": "n7", "text": "Test customer demand", "ring": "control", "reason": "interviews cost time, not money"}),  # n13
    ("add_action", {"parent_id": "n7", "text": "Set a savings target", "ring": "control", "reason": "a number I choose"}),  # n14
    ("ask", {"node_id": "n7", "kind": "what_if", "question": "And if the first idea fails?"}),
    ("add_consequence", {"parent_id": "n7", "text": "Still employed, with evidence and a second idea", "ring": "control", "reason": "nothing lost"}),  # n15
    ("finish", {
        "summary": "The job itself is not the blocker; the missing piece is evidence that an alternative is worth the risk. Testing on the side gets that evidence without giving anything up.",
        "next_move": "Spend two hours this week interviewing three potential customers about one idea. No resignation required.",
        "actions": {"n3": "Write down the monthly number that would make a transition safe, by Friday."},
        "accept": {"n4": "You cannot time the economy. Focus on evidence of demand, which you can gather now."},
    }),
]

JOB_ANSWERS = [
    "I'm executing other people's ideas instead of building something myself.",
    "Ownership over outcomes, not just deliverables.",
    "I need financial stability.",
    "I'd keep the salary but feel more and more stuck.",
    "My manager might say yes. I'd find out fast.",
    "I'd find out if anyone wants it without quitting.",
    "I'd still have the job, and I'd have learned something.",
]
