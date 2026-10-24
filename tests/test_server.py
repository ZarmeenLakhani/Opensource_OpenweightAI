import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fake_model import JOB_ANSWERS, JOB_PROBLEM, JOB_SCRIPT, FakeClient
from lifegraph.server import App, make_handler


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp()
        self.app = App(FakeClient(JOB_SCRIPT), "fake", self.data_dir)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def _get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()

    def _post(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def _wait(self, session_id, status, timeout=5):
        deadline = time.time() + timeout
        while time.time() < deadline:
            _, _, raw = self._get(f"/api/state?session={session_id}")
            state = json.loads(raw)
            if state["status"] == status or state["status"] == "error":
                return state
            time.sleep(0.02)
        self.fail(f"session never reached {status}; last state {state['status']}")

    def test_full_session_over_http(self):
        status, ctype, page = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn(b"Explore my decision graph", page)

        status, j = self._post("/api/start", {"problem": JOB_PROBLEM, "temperature": 0.9})
        self.assertEqual(status, 200)
        self.assertEqual(j["temperature"], 0.9)
        sid = j["session"]

        for answer in JOB_ANSWERS:
            state = self._wait(sid, "asking")
            self.assertIsNone(state["error"], state["error"])
            self.assertTrue(state["question"])
            self.assertEqual(self._post("/api/answer", {"session": sid, "answer": answer})[0], 200)

        state = self._wait(sid, "done")
        self.assertEqual(state["status"], "done", state["error"])
        self.assertEqual(state["temperature"], 0.9)
        self.assertEqual(self.app.client.last_temperature, 0.9)  # the per-session value reached the model
        self.assertIn("two hours", state["graph"]["next_move"])
        self.assertEqual(len([m for m in state["transcript"] if m["role"] == "you"]), len(JOB_ANSWERS))
        self.assertTrue(any(e.get("name") == "finish" for e in state["events"]))

        status, ctype, html = self._get(f"/session/{sid}.html")
        self.assertEqual(status, 200)
        self.assertIn(b"Your next move", html)

        _, _, raw = self._get("/api/sessions")
        listing = json.loads(raw)
        self.assertEqual(listing["sessions"][0]["id"], sid)
        self.assertEqual(listing["totals"]["quests_done"], 0)

        before = state["graph"]["score"]["points"]
        status, j = self._post("/api/quest_done", {"session": sid})
        self.assertEqual(status, 200)
        self.assertEqual(j["score"]["points"], before + 100)
        self.assertEqual(j["totals"]["quests_done"], 1)
        self.assertEqual(self._post("/api/quest_done", {"session": sid})[1]["totals"]["points"], before + 100)  # idempotent
        self.assertEqual(self._post("/api/quest_done", {"session": "nope"})[0], 404)

    def test_answer_when_not_asking_is_rejected(self):
        status, j = self._post("/api/answer", {"session": "nope", "answer": "x"})
        self.assertEqual(status, 404)
        status, j = self._post("/api/start", {"problem": "  "})
        self.assertEqual(status, 400)
        status, j = self._post("/api/start", {"problem": "x", "temperature": "hot"})
        self.assertEqual(status, 400)
        status, j = self._post("/api/start", {"problem": "x", "temperature": 7})
        self.assertEqual(j["temperature"], 2.0)  # clamped

    def test_user_command_mid_session(self):
        _, j = self._post("/api/start", {"problem": JOB_PROBLEM})
        sid = j["session"]
        self._wait(sid, "asking")
        self._post("/api/answer", {"session": sid, "answer": "/map"})
        state = self._wait(sid, "asking")
        notes = [m for m in state["transcript"] if m["role"] == "note"]
        self.assertTrue(notes and "n0" in notes[0]["text"])
        # the same question is asked again after a command, not a new one
        self.assertEqual(state["transcript"][0]["text"], state["question"])


if __name__ == "__main__":
    unittest.main()
