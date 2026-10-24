import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fake_model import GYM_ANSWERS, GYM_SCRIPT, FakeClient
from whyrings.agent import run_agent
from whyrings.graph import Graph, recurring_roots, search_history
from whyrings.render import render_html, save_html
from whyrings.tools import ToolRunner


def answers_in_order(answers):
    queue = list(answers)
    return lambda question: queue.pop(0)


class GraphTests(unittest.TestCase):
    def test_boundary_and_levers(self):
        g = Graph("I keep skipping the gym", session_id="s1")
        g.set_ring("n0", "control")
        g.add_cause("n0", "tired after work", "influence")
        g.add_cause("n1", "work late", "influence")
        g.add_cause("n2", "manager schedules late meetings", "outside")
        g.add_cause("n3", "team is 8 hours ahead", "outside")
        self.assertEqual(g.boundary_edges(), [("n2", "n3")])
        self.assertEqual(g.levers(), ["n2"])

    def test_branching(self):
        g = Graph("p", session_id="s1")
        g.set_ring("n0", "control")
        g.add_cause("n0", "a", "control")
        g.add_cause("n0", "b", "outside")
        self.assertEqual([c["id"] for c in g.children("n0")], ["n1", "n2"])
        self.assertEqual(g.levers(), ["n0"])

    def test_bad_ring_rejected(self):
        g = Graph("p", session_id="s1")
        with self.assertRaises(ValueError):
            g.set_ring("n0", "fate")


class ToolRunnerTests(unittest.TestCase):
    def test_ask_why_requires_classified_nodes(self):
        g = Graph("p", session_id="s1")
        runner = ToolRunner(g, ask_user=lambda q: "x", data_dir=tempfile.mkdtemp())
        self.assertIn("error", runner.run("ask_why", {"node_id": "n0", "question": "why?"}))
        runner.run("set_ring", {"node_id": "n0", "ring": "control", "reason": ""})
        self.assertEqual(runner.run("ask_why", {"node_id": "n0", "question": "why?"})["answer"], "x")

    def test_depth_limit(self):
        g = Graph("p", session_id="s1")
        g.set_ring("n0", "control")
        parent = "n0"
        for i in range(5):
            parent = g.add_cause(parent, f"c{i}", "influence")["id"]
        runner = ToolRunner(g, ask_user=lambda q: "x", data_dir=tempfile.mkdtemp())
        self.assertIn("error", runner.run("ask_why", {"node_id": parent, "question": "why?"}))

    def test_finish_requires_action_per_lever(self):
        g = Graph("p", session_id="s1")
        g.set_ring("n0", "control")
        g.add_cause("n0", "a", "influence")
        g.add_cause("n1", "b", "outside")
        runner = ToolRunner(g, ask_user=lambda q: "x", data_dir=tempfile.mkdtemp())
        res = runner.run("finish", {"summary": "s", "actions": {}, "accept": {}})
        self.assertIn("n1", res["error"])
        res = runner.run("finish", {"summary": "s", "actions": {"n1": "do"}, "accept": {}})
        self.assertTrue(res["ok"])
        self.assertTrue(g.finished)

    def test_unknown_tool(self):
        g = Graph("p", session_id="s1")
        runner = ToolRunner(g, ask_user=lambda q: "x", data_dir=tempfile.mkdtemp())
        self.assertIn("error", runner.run("nope", {}))


class AgentLoopTests(unittest.TestCase):
    def test_full_session_with_scripted_model(self):
        data_dir = tempfile.mkdtemp()
        client = FakeClient(GYM_SCRIPT)
        graph = run_agent(client, "fake", "I keep skipping the gym", answers_in_order(GYM_ANSWERS), data_dir, session_id="gym")
        self.assertTrue(graph.finished)
        self.assertEqual(len(graph.nodes), 6)
        self.assertEqual(graph.levers(), ["n3"])
        self.assertEqual(set(graph.actions), {"n2", "n3"})
        self.assertEqual(client.script, [])
        # Tool results were fed back to the model as tool messages.
        self.assertTrue(any(m["role"] == "tool" for m in client.seen_messages))

        json_path = graph.save(data_dir)
        saved = json.loads(json_path.read_text())
        self.assertEqual(saved["levers"], ["n3"])

        html_path = save_html(graph, data_dir)
        page = html_path.read_text()
        self.assertIn("The team is 8 hours ahead", page)
        self.assertIn("stroke='#d33'", page)

    def test_prose_reply_is_pushed_back_to_tools(self):
        script = list(GYM_SCRIPT)
        client = FakeClient(script)
        original = client.chat.completions.create

        calls = {"n": 0}

        def create(**kw):
            calls["n"] += 1
            if calls["n"] == 1:
                from types import SimpleNamespace
                msg = SimpleNamespace(content="Let me think out loud...", tool_calls=None)
                return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
            return original(**kw)

        client.chat.completions.create = create
        graph = run_agent(client, "fake", "I keep skipping the gym", answers_in_order(GYM_ANSWERS), tempfile.mkdtemp())
        self.assertTrue(graph.finished)


class HistoryTests(unittest.TestCase):
    def test_search_and_recurring_roots(self):
        data_dir = tempfile.mkdtemp()
        g1 = Graph("I keep skipping the gym", session_id="s1")
        g1.set_ring("n0", "control")
        g1.add_cause("n0", "I sleep badly most nights", "control")
        g1.save(data_dir)

        hits = search_history(data_dir, "bad sleep most nights", exclude_session="s2")
        self.assertEqual(hits[0]["ref"], "s1:n1")

        g2 = Graph("I snap at people in the morning", session_id="s2")
        g2.set_ring("n0", "control")
        g2.add_cause("n0", "sleep badly", "control")
        g2.nodes["n1"]["same_as"] = "s1:n1"
        g2.save(data_dir)

        roots = recurring_roots(data_dir)
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0]["text"], "I sleep badly most nights")
        self.assertEqual(len(roots[0]["problems"]), 2)


if __name__ == "__main__":
    unittest.main()
