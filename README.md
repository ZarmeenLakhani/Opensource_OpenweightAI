# Why Rings

An agent that asks you "why" until it finds the real causes of a recurring problem, then lands every cause in one of three rings: **control**, **influence**, **outside**. Over many sessions your problems become one decision graph, and the causes that keep showing up in your control ring are your highest-leverage habits.

Runs on any open-weight model behind an OpenAI-compatible endpoint (Ollama, vLLM, llama.cpp, Groq). Your life graph stays on your machine as plain JSON.

Built for the agent track of the Open Source / Open Weight AI hackathon.

## How it works

```
"I keep skipping the gym"            [control]
  └─ Too tired after work            [influence]
      └─ I work late most days       [influence]
          └─ Meetings pile up        [influence]   <- lever
              └─ Manager sets them   [outside]     <- chain leaves your reach here
                  └─ Team 8h ahead   [outside]
```

The agent does not stop at "why 5". It stops when a cause is clearly actionable or clearly outside your control. The edge where a chain crosses from your reach into **outside** is the control boundary, and the node just before it is a **lever**: the best place to act. The agent must give you one concrete action for every lever before it is allowed to finish.

## The agent

The model never writes prose to you. It only calls tools, and `ask_why` is the only tool that reaches you:

| Tool | What it does |
|---|---|
| `set_ring(node_id, ring, reason)` | place a node in control / influence / outside |
| `ask_why(node_id, question)` | ask you one question about one node, returns your answer |
| `add_cause(parent_id, text, ring, reason, actionable)` | add a cause under a node; two calls on the same parent is a branch |
| `search_history(text)` | find similar causes from past sessions |
| `link_past(node_id, past_ref)` | mark a cause as the same as one from a past session |
| `finish(summary, actions, accept)` | end; rejected if any lever has no action |

The loop (`whyrings/agent.py`) is about 50 lines: model picks a tool, Python runs it against the graph, the result goes back as a tool message, repeat until `finish`. Guardrails live in the tool runner, not the prompt: you cannot ask about an unclassified node, cannot probe past depth 5, and cannot finish without an action per lever.

## Run it

```bash
pip install -r requirements.txt            # only dependency: openai SDK, used as a generic client
ollama pull qwen2.5:7b                      # any tool-calling open-weight model works
python -m whyrings ask "I keep skipping the gym"
```

Each session writes `data/sessions/<id>.json` and `data/sessions/<id>.html` (three rings, red edges at the boundary, red outlines on levers, your actions on the right).

Other endpoints:

```bash
python -m whyrings ask --base-url http://localhost:8000/v1 --model meta-llama/Llama-3.1-8B-Instruct "..."
WHYRINGS_BASE_URL=https://api.groq.com/openai/v1 WHYRINGS_API_KEY=... WHYRINGS_MODEL=llama-3.3-70b-versatile python -m whyrings ask "..."
```

Add `--verbose` to watch every tool call.

Once you have a few sessions:

```bash
python -m whyrings roots
```

prints causes that sit under more than one problem, sorted by how many problems they explain and then by ring (control first). That list is the point of the whole thing.

## Test without a model

```bash
python -m unittest discover tests
```

`tests/fake_model.py` replays a scripted list of tool calls through the real loop, tool runner, graph and renderer, so the whole pipeline is covered without a model server.

## Layout

```
whyrings/
  agent.py     the loop
  tools.py     tool schemas + ToolRunner (the guardrails)
  graph.py     Graph, boundary edges, levers, history search, recurring roots
  prompts.py   system prompt
  render.py    rings as standalone HTML/SVG
  cli.py       `ask` and `roots` commands
tests/
  fake_model.py  scripted model for tests and demos
  test_agent.py
```

## Not therapy

This is a reflection tool. The prompt forbids the model from turning answers into labels or self-blame, and rephrases self-worth answers as concrete situations. If a session goes somewhere heavier than a planning tool should handle, stop and talk to a person.
