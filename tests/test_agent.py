import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fake_model import JOB_ANSWERS, JOB_PROBLEM, JOB_SCRIPT, FakeClient
from lifegraph.agent import run_agent
from lifegraph.graph import Graph, recurring_roots, search_history
from lifegraph.render import save_html
from lifegraph.tools import ToolRunner, apply_user_command


def answers_in_order(answers):
    queue = list(answers)
    return lambda question: queue.pop(0)


def runner_for(graph, answers=("x",)):
    return ToolRunner(graph, ask_user=answers_in_order(list(answers) * 20), data_dir=tempfile.mkdtemp(), notify=lambda _: None)


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

    def test_actions_cannot_be_outside_and_do_not_make_levers(self):
        g = Graph("p", session_id="s1")
        g.set_ring("n0", "control")
        with self.assertRaises(ValueError):
            g.add_action("n0", "do a thing", "outside")
        g.add_consequence("n0", "it rains", "outside")
        self.assertEqual(g.levers(), [])  # only cause chains define levers

    def test_delete_branch_and_ids_stay_unique(self):
        g = Graph("p", session_id="s1")
        g.set_ring("n0", "control")
        g.add_cause("n0", "a", "control")
        g.add_cause("n1", "b", "control")
        g.actions["n2"] = "x"
        removed = g.delete_branch("n1")
        self.assertEqual(removed, ["n1", "n2"])
        self.assertNotIn("n2", g.actions)
        self.assertEqual(g.add_cause("n0", "c", "control")["id"], "n3")
        with self.assertRaises(ValueError):
            g.delete_branch("n0")

    def test_shifts_when_recorded(self):
        g = Graph("p", session_id="s1")
        g.set_ring("n0", "influence", "r", shifts_when="moves to control once savings hit 6 months")
        self.assertIn("savings", g.nodes["n0"]["shifts_when"])
        self.assertIn("moves if", g.outline())

    def test_bad_ring_rejected(self):
        g = Graph("p", session_id="s1")
        with self.assertRaises(ValueError):
            g.set_ring("n0", "fate")


class ToolRunnerTests(unittest.TestCase):
    def test_ask_requires_classified_nodes_and_valid_kind(self):
        g = Graph("p", session_id="s1")
        r = runner_for(g)
        self.assertIn("error", r.run("ask", {"node_id": "n0", "kind": "why", "question": "why?"}))
        r.run("set_ring", {"node_id": "n0", "ring": "control", "reason": ""})
        self.assertIn("error", r.run("ask", {"node_id": "n0", "kind": "guess", "question": "why?"}))
        self.assertEqual(r.run("ask", {"node_id": "n0", "kind": "why", "question": "why?"})["answer"], "x")

    def test_depth_and_question_limits(self):
        g = Graph("p", session_id="s1")
        g.set_ring("n0", "control")
        parent = "n0"
        for i in range(5):
            parent = g.add_cause(parent, f"c{i}", "influence")["id"]
        r = runner_for(g)
        self.assertIn("depth", r.run("ask", {"node_id": parent, "kind": "why", "question": "why?"})["error"])
        for _ in range(12):
            r.run("ask", {"node_id": "n0", "kind": "why", "question": "why?"})
            r.run("add_cause", {"parent_id": "n0", "text": "c", "ring": "control", "reason": "", "actionable": False})
        self.assertIn("call finish", r.run("ask", {"node_id": "n0", "kind": "why", "question": "why?"})["error"])

    def test_root_lever_needs_no_separate_action(self):
        g = Graph("p", session_id="s1")
        g.set_ring("n0", "control")
        g.add_cause("n0", "the weather", "outside")  # n0 is now a lever
        g.add_option("n0", "stay", "control")
        g.add_option("n0", "go", "control")
        r = runner_for(g)
        r.run("ask", {"node_id": "n0", "kind": "what_if", "question": "what if?"})
        r.run("add_consequence", {"parent_id": "n2", "text": "then", "ring": "control", "reason": ""})
        self.assertEqual(g.levers(), ["n0"])
        self.assertTrue(r.run("finish", {"summary": "s", "next_move": "do x", "actions": {}, "accept": {}})["ok"])

    def test_finish_guardrails(self):
        g = Graph("p", session_id="s1")
        g.set_ring("n0", "control")
        g.add_cause("n0", "a", "influence")
        g.add_cause("n1", "b", "outside")
        r = runner_for(g)
        base = {"summary": "s", "accept": {}}
        self.assertIn("next_move", r.run("finish", {**base, "next_move": " ", "actions": {"n1": "do"}})["error"])
        self.assertIn("n1", r.run("finish", {**base, "next_move": "do x", "actions": {}})["error"])
        self.assertIn("what_if", r.run("finish", {**base, "next_move": "do x", "actions": {"n1": "do"}})["error"])
        r.run("ask", {"node_id": "n0", "kind": "what_if", "question": "what if?"})
        r.run("add_consequence", {"parent_id": "n0", "text": "then", "ring": "control", "reason": ""})
        self.assertIn("two paths", r.run("finish", {**base, "next_move": "do x", "actions": {"n1": "do"}})["error"])
        g.add_option("n0", "stay", "control")
        g.add_option("n0", "leave", "control")
        with self.assertRaises(ValueError):
            g.add_option("n0", "fate", "outside")
        bad_accept = {**base, "next_move": "do x", "actions": {"n1": "do"}, "accept": {"n1": "let go"}}
        self.assertIn("outside", r.run("finish", bad_accept)["error"])
        self.assertTrue(r.run("finish", {**base, "next_move": "do x", "actions": {"n1": "do"}})["ok"])
        self.assertEqual(g.next_move, "do x")

    def test_unknown_tool(self):
        self.assertIn("error", runner_for(Graph("p", session_id="s1")).run("nope", {}))

    def test_every_answer_must_be_recorded_before_moving_on(self):
        g = Graph("p", session_id="s1")
        g.set_ring("n0", "control")
        r = runner_for(g, answers=["because of x"])
        res = r.run("ask", {"node_id": "n0", "kind": "why", "question": "why?"})
        self.assertIn("record this answer", res["next"])
        for blocked in (("ask", {"node_id": "n0", "kind": "why", "question": "and?"}),
                        ("add_option", {"parent_id": "n0", "text": "stay", "ring": "control", "reason": ""}),
                        ("finish", {"summary": "s", "next_move": "x", "actions": {}, "accept": {}})):
            err = r.run(*blocked)["error"]
            self.assertIn("not on the map yet", err)
            self.assertIn("because of x", err)
        r.run("add_cause", {"parent_id": "n0", "text": "x", "ring": "control", "reason": "", "actionable": True})
        self.assertNotIn("error", r.run("ask", {"node_id": "n1", "kind": "why", "question": "why x?"}))
        # consequences and actions also count as recording; a /explore (empty answer) leaves nothing pending
        r.run("add_consequence", {"parent_id": "n1", "text": "y", "ring": "control", "reason": ""})
        self.assertIsNone(r.pending)
        r2 = runner_for(g, answers=["/explore n1"])
        r2.run("ask", {"node_id": "n0", "kind": "why", "question": "why?"})
        self.assertIsNone(r2.pending)


class UserEditTests(unittest.TestCase):
    def setUp(self):
        self.g = Graph("p", session_id="s1")
        self.g.set_ring("n0", "control")
        self.g.add_cause("n0", "a", "outside")
        self.g.add_cause("n1", "b", "outside")

    def test_commands(self):
        _, note, _ = apply_user_command(self.g, "/move n1 influence")
        self.assertIn("influence", note)
        self.assertEqual(self.g.nodes["n1"]["ring"], "influence")
        apply_user_command(self.g, "/edit n1 something I can push on")
        self.assertEqual(self.g.nodes["n1"]["text"], "something I can push on")
        apply_user_command(self.g, "/delete n2")
        self.assertNotIn("n2", self.g.nodes)
        _, _, req = apply_user_command(self.g, "/explore n1")
        self.assertIn("n1", req)
        self.assertEqual(len(self.g.user_edits), 4)
        _, note, _ = apply_user_command(self.g, "/move n9 control")
        self.assertIn("Could not", note)
        _, note, _ = apply_user_command(self.g, "/bogus")
        self.assertIn("Unknown", note)

    def test_edits_during_ask_reach_the_model(self):
        r = runner_for(self.g, answers=["/move n1 influence", "/map", "because reasons"])
        res = r.run("ask", {"node_id": "n0", "kind": "why", "question": "why?"})
        self.assertEqual(res["answer"], "because reasons")
        self.assertEqual(res["user_edits"], ["/move n1 influence"])
        self.assertIn("n1 [influence]", res["outline"])
        self.assertEqual(r.questions_asked, 1)

    def test_explore_returns_request_without_answer(self):
        r = runner_for(self.g, answers=["/explore n1"])
        res = r.run("ask", {"node_id": "n0", "kind": "why", "question": "why?"})
        self.assertEqual(res["answer"], "")
        self.assertIn("n1", res["user_request"])


class AgentLoopTests(unittest.TestCase):
    def test_full_session_with_scripted_model(self):
        data_dir = tempfile.mkdtemp()
        client = FakeClient(JOB_SCRIPT)
        graph = run_agent(client, "fake", JOB_PROBLEM, answers_in_order(JOB_ANSWERS), data_dir, session_id="job")
        self.assertTrue(graph.finished)
        self.assertEqual(client.script, [])
        self.assertEqual(client.last_temperature, 0.3)  # the default reaches the model
        self.assertEqual(graph.levers(), ["n3"])
        self.assertIn("two hours", graph.next_move)
        self.assertEqual([o["text"][:4] for o in graph.options()], ["Stay", "Ask ", "Test"])
        by_ring = graph.by_ring(kind="action")
        self.assertEqual([n["text"] for n in by_ring["control"]], ["Build a prototype", "Test customer demand", "Set a savings target"])
        self.assertEqual([n["text"] for n in by_ring["influence"]], ["Negotiate ownership of one project"])
        self.assertEqual(by_ring["outside"], [])
        # consequences hang under the path they were asked about
        self.assertEqual([c["kind"] for c in graph.children("n7")], ["consequence", "action", "action", "action", "consequence"])
        score = graph.score()
        self.assertEqual((score["causes"], score["levers"], score["paths"], score["what_ifs"]), (4, 1, 3, 4))
        self.assertEqual(score["points"], 4 * 10 + 25 + 3 * 15 + 4 * 20 + 50)
        self.assertEqual(score["depth"], 4)
        self.assertTrue(any(m["role"] == "tool" for m in client.seen_messages))

        saved = json.loads(graph.save(data_dir).read_text())
        self.assertEqual(saved["next_move"], graph.next_move)

        page = save_html(graph, data_dir).read_text()
        self.assertIn("your quest", page)
        self.assertIn("two hours this week", page)
        self.assertIn("leaves your reach", page)
        self.assertIn("LifeGraphTree.render", page)  # the tree renderer is inlined, so the file stands alone
        self.assertIn("window.LifeGraphSketch", page)  # and so is the sketch layer it needs
        self.assertIn('"levers": ["n3"]', page)  # the graph JSON is embedded for it

    def test_prose_reply_is_pushed_back_to_tools(self):
        client = FakeClient(JOB_SCRIPT)
        original = client.chat.completions.create
        calls = {"n": 0}

        def create(**kw):
            calls["n"] += 1
            if calls["n"] == 1:
                msg = SimpleNamespace(content="Let me think out loud...", tool_calls=None)
                return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
            return original(**kw)

        client.chat.completions.create = create
        graph = run_agent(client, "fake", JOB_PROBLEM, answers_in_order(JOB_ANSWERS), tempfile.mkdtemp(), temperature=1.1)
        self.assertTrue(graph.finished)
        self.assertEqual(client.last_temperature, 1.1)


class RateLimitTests(unittest.TestCase):
    def test_waits_what_the_server_asks_then_continues(self):
        from lifegraph import agent as agent_module

        client = FakeClient(JOB_SCRIPT)
        original = client.chat.completions.create
        calls = {"n": 0}

        class RateLimitError(Exception):
            status_code = 429

        def create(**kw):
            calls["n"] += 1
            if calls["n"] in (2, 3):  # two limits in a row, then fine
                raise RateLimitError("Error code: 429 - quota exceeded. Please retry in 13.79s.")
            return original(**kw)

        client.chat.completions.create = create
        slept, events = [], []
        real_sleep = agent_module.time.sleep
        agent_module.time.sleep = slept.append
        try:
            graph = run_agent(client, "fake", JOB_PROBLEM, answers_in_order(JOB_ANSWERS), tempfile.mkdtemp(),
                              on_event=lambda k, p: events.append((k, p)))
        finally:
            agent_module.time.sleep = real_sleep
        self.assertTrue(graph.finished)
        self.assertEqual(slept, [14.79, 14.79])  # the server's hint plus a second
        self.assertEqual([p["attempt"] for k, p in events if k == "retry"], [1, 2])

    def test_gives_up_after_the_retry_budget_and_ignores_other_errors(self):
        from lifegraph import agent as agent_module

        self.assertIsNone(agent_module._retry_after(ValueError("bad json")))
        self.assertEqual(agent_module._retry_after(RuntimeError("429 Too Many Requests")), 15.0)
        self.assertEqual(agent_module._retry_after(RuntimeError("429: retry in 90s")), 60.0)  # capped

        client = FakeClient(JOB_SCRIPT)
        client.chat.completions.create = lambda **kw: (_ for _ in ()).throw(RuntimeError("Error code: 429 - retry in 1s"))
        agent_module.time.sleep = lambda s: None
        try:
            with self.assertRaises(RuntimeError):
                run_agent(client, "fake", JOB_PROBLEM, answers_in_order(JOB_ANSWERS), tempfile.mkdtemp())
        finally:
            agent_module.time.sleep = __import__("time").sleep


class ConnectionRetryTests(unittest.TestCase):
    def test_retries_dropped_connections_then_gives_up(self):
        from lifegraph import agent as agent_module

        class APIConnectionError(Exception):
            pass

        client = FakeClient(JOB_SCRIPT)
        original = client.chat.completions.create
        calls = {"n": 0}

        def create(**kw):
            calls["n"] += 1
            if calls["n"] == 3:
                raise APIConnectionError("Connection error.")
            return original(**kw)

        client.chat.completions.create = create
        slept = []
        agent_module.time.sleep = slept.append
        try:
            graph = run_agent(client, "fake", JOB_PROBLEM, answers_in_order(JOB_ANSWERS), tempfile.mkdtemp())
            self.assertTrue(graph.finished)
            self.assertEqual(slept, [5.0])
            client2 = FakeClient(JOB_SCRIPT)
            client2.chat.completions.create = lambda **kw: (_ for _ in ()).throw(APIConnectionError("Connection error."))
            slept.clear()
            with self.assertRaises(APIConnectionError):
                run_agent(client2, "fake", JOB_PROBLEM, answers_in_order(JOB_ANSWERS), tempfile.mkdtemp())
            self.assertEqual(slept, [5.0, 10.0, 20.0])
        finally:
            agent_module.time.sleep = __import__("time").sleep


class WindowTests(unittest.TestCase):
    def test_old_turns_are_replaced_by_the_outline(self):
        from lifegraph.agent import WINDOW, _window

        data_dir = tempfile.mkdtemp()
        client = FakeClient(JOB_SCRIPT)
        sent = []
        original = client.chat.completions.create
        client.chat.completions.create = lambda **kw: (sent.append(kw["messages"]), original(**kw))[1]
        graph = run_agent(client, "fake", JOB_PROBLEM, answers_in_order(JOB_ANSWERS), data_dir)
        self.assertTrue(graph.finished)
        first, last = sent[0], sent[-1]
        self.assertEqual(first[0]["role"], "system")
        self.assertLessEqual(len(last), 2 + 1 + WINDOW)
        self.assertEqual(last[0]["role"], "system")
        self.assertIn("Map so far", last[2]["content"])
        self.assertIn("n3 [influence] I need financial stability", last[2]["content"])
        self.assertEqual(last[3]["role"], "assistant")  # the window never starts inside a tool-call pair
        # short conversations are sent whole
        g = Graph("p", session_id="w")
        r = ToolRunner(g, ask_user=lambda q: "x", data_dir=data_dir, notify=lambda _: None)
        msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "p"}, {"role": "assistant", "content": "a"}]
        self.assertIs(_window(msgs, g, r), msgs)


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
