"""A small local web UI: `python -m lifegraph serve` then open http://localhost:8000.

Standard library only. Each session runs the agent loop in a thread; questions and answers
cross between the loop and the browser through two queues.
"""

import json
import queue
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .agent import run_agent
from .graph import Graph, load_sessions, mark_quest_done, recurring_roots, totals
from .render import render_html, save_html

WEB_DIR = Path(__file__).parent / "web"


class Session:
    def __init__(self, problem, client, model, data_dir):
        self.graph = Graph(problem)
        self.id = self.graph.session_id
        self.status = "thinking"  # thinking | asking | done | error
        self.question = None
        self.transcript = []  # {"role": "agent"|"you"|"note", "text": ...}
        self.events = []  # tool calls, for the "what the agent is doing" panel
        self.error = None
        self.html_path = None
        self._questions = queue.Queue()
        self._answers = queue.Queue()
        self._thread = threading.Thread(
            target=self._run, args=(client, model, data_dir), daemon=True, name=f"lifegraph-{self.id}"
        )
        self._thread.start()

    def _ask_user(self, question):
        self.question = question
        self.status = "asking"
        if not self.transcript or self.transcript[-1] != {"role": "agent", "text": question}:
            self.transcript.append({"role": "agent", "text": question})
        answer = self._answers.get()
        self.transcript.append({"role": "you", "text": answer})
        self.status = "thinking"
        self.question = None
        return answer

    def _notify(self, text):
        self.transcript.append({"role": "note", "text": text})

    def _on_event(self, kind, payload):
        if kind == "call":
            self.events.append(payload)
        elif kind == "result" and "error" in payload.get("result", {}):
            self.events.append({"error": payload["result"]["error"]})

    def _run(self, client, model, data_dir):
        try:
            run_agent(
                client, model, self.graph.problem, self._ask_user, data_dir,
                on_event=self._on_event, graph=self.graph, notify=self._notify,
            )
            self.graph.save(data_dir)
            self.html_path = save_html(self.graph, data_dir)
            self.status = "done"
        except Exception as exc:  # surfaced to the page rather than killing the thread silently
            self.error = f"{type(exc).__name__}: {exc}"
            self.status = "error"

    def answer(self, text):
        if self.status != "asking":
            return False
        self._answers.put(text)
        return True

    def state(self):
        try:
            graph = self.graph.to_dict()
        except RuntimeError:  # dict changed size while iterating: the agent is mid-write, try next poll
            graph = None
        return {
            "id": self.id,
            "status": self.status,
            "question": self.question,
            "transcript": self.transcript,
            "events": self.events[-30:],
            "error": self.error,
            "graph": graph,
        }


class App:
    def __init__(self, client, model, data_dir):
        self.client = client
        self.model = model
        self.data_dir = data_dir
        self.sessions = {}

    def start(self, problem):
        session = Session(problem, self.client, self.model, self.data_dir)
        self.sessions[session.id] = session
        return session


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # keep the terminal quiet
            pass

        def _send(self, status, body, content_type="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json_body(self):
            length = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            if url.path in ("/", "/index.html"):
                return self._send(HTTPStatus.OK, (WEB_DIR / "index.html").read_bytes(), "text/html")
            if url.path == "/tree.js":
                return self._send(HTTPStatus.OK, (WEB_DIR / "tree.js").read_bytes(), "text/javascript")
            if url.path == "/api/state":
                session = app.sessions.get(q.get("session", [""])[0])
                if not session:
                    return self._send(HTTPStatus.NOT_FOUND, {"error": "no such session"})
                return self._send(HTTPStatus.OK, session.state())
            if url.path == "/api/sessions":
                past = [{"id": s["session_id"], "problem": s["problem"], "next_move": s.get("next_move", ""),
                         "points": s.get("score", {}).get("points", 0), "done": bool(s.get("completed_at"))}
                        for s in load_sessions(app.data_dir)]
                return self._send(HTTPStatus.OK, {"sessions": past[::-1], "roots": recurring_roots(app.data_dir), "totals": totals(app.data_dir)})
            if url.path.startswith("/session/"):
                session_id = url.path[len("/session/"):].removesuffix(".html")
                live = app.sessions.get(session_id)
                if live:
                    return self._send(HTTPStatus.OK, render_html(live.graph).encode(), "text/html")
                path = Path(app.data_dir) / "sessions" / f"{session_id}.html"
                if path.exists():
                    return self._send(HTTPStatus.OK, path.read_bytes(), "text/html")
            return self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self):
            url = urlparse(self.path)
            body = self._json_body()
            if url.path == "/api/start":
                problem = (body.get("problem") or "").strip()
                if not problem:
                    return self._send(HTTPStatus.BAD_REQUEST, {"error": "problem is empty"})
                session = app.start(problem)
                return self._send(HTTPStatus.OK, {"session": session.id})
            if url.path == "/api/answer":
                session = app.sessions.get(body.get("session", ""))
                if not session:
                    return self._send(HTTPStatus.NOT_FOUND, {"error": "no such session"})
                if not session.answer((body.get("answer") or "").strip()):
                    return self._send(HTTPStatus.CONFLICT, {"error": "the agent is not waiting for an answer"})
                return self._send(HTTPStatus.OK, {"ok": True})
            if url.path == "/api/quest_done":
                session_id = body.get("session", "")
                live = app.sessions.get(session_id)
                if live and live.status == "done" and not live.graph.completed_at:
                    live.graph.completed_at = time.strftime("%Y-%m-%dT%H:%M:%S")
                    live.graph.save(app.data_dir)
                    return self._send(HTTPStatus.OK, {"ok": True, "score": live.graph.score(), "totals": totals(app.data_dir)})
                updated = mark_quest_done(app.data_dir, session_id)
                if not updated:
                    return self._send(HTTPStatus.NOT_FOUND, {"error": "no such finished session"})
                return self._send(HTTPStatus.OK, {"ok": True, "score": updated["score"], "totals": totals(app.data_dir)})
            return self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

    return Handler


def serve(client, model, data_dir, host="127.0.0.1", port=8000):
    app = App(client, model, data_dir)
    server = ThreadingHTTPServer((host, port), make_handler(app))
    print(f"LifeGraph running at http://{host}:{port}  (model: {model}, sessions saved in {data_dir}/sessions)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return app
