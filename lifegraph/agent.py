"""The agent loop: model picks a tool, we run it, result goes back, until finish."""

import json
import re
import time

from .graph import Graph
from .prompts import SYSTEM_PROMPT
from .tools import MAX_QUESTIONS, TOOLS, ToolRunner, parse_args

MAX_STEPS = 60
DEFAULT_TEMPERATURE = 0.3  # low keeps tool calls well-formed; raise it for more varied questions and paths
RATE_LIMIT_RETRIES = 8  # hosted free tiers meter input tokens per minute
CONNECTION_RETRIES = 3  # transient network failures: wait 5s, 10s, 20s
WINDOW = 8  # recent messages sent to the model; everything older is replaced by the map outline


def _connection_wait(exc, attempt):
    name = type(exc).__name__
    if name in ("APIConnectionError", "APITimeoutError") or "connection error" in str(exc).lower():
        return 5.0 * (2 ** attempt)
    return None


def _window(messages, graph, runner):
    """Keep each call small: system prompt, the problem, the current map, then only the last WINDOW messages.

    The outline carries every node id, kind and region, which is all the model needs to keep building.
    Without this, every turn resends the whole history and a session grows past hosted free-tier limits
    and small local context windows.
    """
    head, tail = messages[:2], messages[2:]
    if len(tail) <= WINDOW:
        return messages
    cut = len(tail) - WINDOW
    while cut < len(tail) and tail[cut]["role"] != "assistant":  # never start inside a tool-call / result pair
        cut += 1
    lines = [
        "Earlier turns are summarized here. Map so far (id [region] text; ? cause, | path, > action, ~ consequence, <- lever):",
        graph.outline(),
        f"Questions asked: {runner.questions_asked} of {MAX_QUESTIONS}. What-ifs: {runner.what_ifs_asked}. Paths: {len(graph.options())}.",
    ]
    if runner.pending:
        lines.append(f"Not on the map yet, the last answer about {runner.pending}: \"{runner.last_answer}\". Record it first.")
    return head + [{"role": "user", "content": "\n".join(lines)}] + tail[cut:]


def _retry_after(exc):
    """Seconds to wait if `exc` is a rate limit, else None. Reads the server's own hint when it gives one."""
    status = getattr(exc, "status_code", None)
    text = str(exc)
    if status != 429 and "429" not in text and type(exc).__name__ != "RateLimitError":
        return None
    m = re.search(r"retry in (\d+(?:\.\d+)?)\s*s", text, re.I) or re.search(r"retry[- _]after[^\d]*(\d+(?:\.\d+)?)", text, re.I)
    return min(60.0, float(m.group(1)) + 1.0) if m else 15.0


def _create(client, emit, **kwargs):
    limits = connections = 0
    while True:
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as exc:  # the SDK's own classes; we only need to know whether it is a rate limit or a dropped connection
            wait = _retry_after(exc)
            if wait is not None:
                limits += 1
                if limits > RATE_LIMIT_RETRIES:
                    raise
                emit("retry", {"wait": wait, "attempt": limits, "error": str(exc)[:200]})
                time.sleep(wait)
                continue
            wait = _connection_wait(exc, connections)
            if wait is not None and connections < CONNECTION_RETRIES:
                connections += 1
                emit("retry", {"wait": wait, "attempt": connections, "error": str(exc)[:200]})
                time.sleep(wait)
                continue
            raise
        usage = getattr(response, "usage", None)
        if usage is not None:
            emit("usage", {"prompt_tokens": getattr(usage, "prompt_tokens", None), "completion_tokens": getattr(usage, "completion_tokens", None)})
        return response


def run_agent(client, model, problem, ask_user, data_dir, on_event=None, session_id=None, graph=None, notify=print,
              temperature=DEFAULT_TEMPERATURE):
    """Drive one session.

    client: anything with chat.completions.create (OpenAI SDK pointed at Ollama, vLLM, Groq, ...).
    ask_user: callable(question) -> answer string.
    on_event: optional callable(kind, payload) for logging tool calls.
    graph: optional pre-built Graph, so a caller (the web server) can watch it while the loop runs.
    notify: callable(text) that shows the person the result of a /command.
    temperature: sampling temperature passed to the model on every turn.
    """
    graph = graph or Graph(problem, session_id=session_id)
    runner = ToolRunner(graph, ask_user, data_dir, notify=notify)
    emit = on_event or (lambda kind, payload: None)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"The problem (node n0): {problem}"},
    ]

    for _ in range(MAX_STEPS):
        response = _create(
            client, emit, model=model, messages=_window(messages, graph, runner), tools=TOOLS, tool_choice="auto",
            temperature=temperature,
        )
        choice = response.choices[0].message
        calls = choice.tool_calls or []
        if not calls:
            # Model wrote prose instead of calling a tool. Push it back to the tools.
            messages.append({"role": "assistant", "content": choice.content or ""})
            messages.append({"role": "user", "content": "Use a tool. Call finish if the graph is complete."})
            continue

        messages.append({
            "role": "assistant",
            "content": choice.content or "",
            "tool_calls": [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.function.name, "arguments": c.function.arguments},
                }
                for c in calls
            ],
        })

        for call in calls:
            args = parse_args(call.function.arguments)
            emit("call", {"name": call.function.name, "args": args})
            result = runner.run(call.function.name, args)
            emit("result", {"name": call.function.name, "result": result})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
            if graph.finished:
                return graph

    graph.summary = graph.summary or "Session hit the step limit before the agent called finish."
    return graph
