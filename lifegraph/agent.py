"""The agent loop: model picks a tool, we run it, result goes back, until finish."""

import json
import re
import time

from .graph import Graph
from .prompts import SYSTEM_PROMPT
from .tools import TOOLS, ToolRunner, parse_args

MAX_STEPS = 60
DEFAULT_TEMPERATURE = 0.3  # low keeps tool calls well-formed; raise it for more varied questions and paths
RATE_LIMIT_RETRIES = 8  # hosted free tiers meter input tokens per minute; every turn resends the whole conversation


def _retry_after(exc):
    """Seconds to wait if `exc` is a rate limit, else None. Reads the server's own hint when it gives one."""
    status = getattr(exc, "status_code", None)
    text = str(exc)
    if status != 429 and "429" not in text and type(exc).__name__ != "RateLimitError":
        return None
    m = re.search(r"retry in (\d+(?:\.\d+)?)\s*s", text, re.I) or re.search(r"retry[- _]after[^\d]*(\d+(?:\.\d+)?)", text, re.I)
    return min(60.0, float(m.group(1)) + 1.0) if m else 15.0


def _create(client, emit, **kwargs):
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as exc:  # the SDK's own classes; we only need to know whether it is a rate limit
            wait = _retry_after(exc)
            if wait is None or attempt == RATE_LIMIT_RETRIES:
                raise
            emit("retry", {"wait": wait, "attempt": attempt + 1, "error": str(exc)[:200]})
            time.sleep(wait)
            continue
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
            client, emit, model=model, messages=messages, tools=TOOLS, tool_choice="auto", temperature=temperature
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
