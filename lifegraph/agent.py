"""The agent loop: model picks a tool, we run it, result goes back, until finish."""

import json

from .graph import Graph
from .prompts import SYSTEM_PROMPT
from .tools import TOOLS, ToolRunner, parse_args

MAX_STEPS = 60


def run_agent(client, model, problem, ask_user, data_dir, on_event=None, session_id=None, graph=None, notify=print):
    """Drive one session.

    client: anything with chat.completions.create (OpenAI SDK pointed at Ollama, vLLM, Groq, ...).
    ask_user: callable(question) -> answer string.
    on_event: optional callable(kind, payload) for logging tool calls.
    graph: optional pre-built Graph, so a caller (the web server) can watch it while the loop runs.
    notify: callable(text) that shows the person the result of a /command.
    """
    graph = graph or Graph(problem, session_id=session_id)
    runner = ToolRunner(graph, ask_user, data_dir, notify=notify)
    emit = on_event or (lambda kind, payload: None)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"The problem (node n0): {problem}"},
    ]

    for _ in range(MAX_STEPS):
        response = client.chat.completions.create(
            model=model, messages=messages, tools=TOOLS, tool_choice="auto", temperature=0.3
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
