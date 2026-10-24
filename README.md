# LifeGraph

Start with what's weighing on you. An agent probes it adaptively (why, what would make this feel safe, what if you tried X), builds a living decision graph of causes, possible actions and consequences, and lands every piece in one of three regions: **control**, **influence**, **outside my control**. It ends with one small next move, not a speech. Over many sessions, the causes that keep showing up under different problems become your decision graph.

Built on **Gemma 4**, running locally through Ollama, or hosted on Google's Gemini API. Apache 2.0 weights, your graph stays as plain JSON on your machine.

Built for the agent track of the Open Source / Open Weight AI hackathon.

## How the experience works

**1. Start with the problem.** "I hate my job. I feel like I'm wasting my potential."

**2. Adaptive probes.** The agent follows your answers, not a script:

```
Why does your job feel like a waste?
  Because I'm executing other people's ideas instead of building something myself.
Why does that bother you?
  Because I want ownership over outcomes, not just deliverables.
Why aren't you pursuing ownership?
  Because I need financial stability.
Why does that keep you stuck?
  Because I don't have a clear alternative worth the risk.
What would make a change feel safe enough?
  A tested idea, evidence of demand, and enough savings to make a transition.
What if you tested one idea while staying employed?
  I'd find out if anyone wants it without quitting.
```

**3. Map the regions.** Three distinct, labeled regions, not nested circles:

| Control | Influence | Outside my control |
|---|---|---|
| Build a prototype | Negotiate ownership of one project | The economy |
| Test customer demand | Find a cofounder | Other people's decisions |
| Set a savings target | | Whether every idea succeeds |

**4. Your next move.** "Spend two hours this week interviewing three potential customers about one idea. No resignation required."

## What the agent does that a worksheet doesn't

- **Probes adaptively.** Three question kinds: `why`, `clarify` (surface the assumption or competing need), `what_if` (test a path). It must run at least one what-if before it is allowed to finish.
- **Builds a living graph.** Nodes are causes, actions or consequences. One answer can open two causes (a branch). Actions hang off the cause they address.
- **Classifies honestly.** Each node has a region and, where it applies, a `shifts_when` condition ("moves to control once savings cover 6 months"). Actions can never be placed in "outside".
- **Finds the lever.** Where a cause chain crosses from your reach into "outside", the node just before the crossing is a lever. The agent must give a concrete action for every lever.
- **Ends with the smallest useful action.** `finish` is rejected without a single `next_move`.
- **Lets you challenge the map.** Whenever it asks you something, you can type a command instead of an answer:

```
/map                      show the map so far
/move n3 influence        put a node in control, influence or outside
/edit n2 <new wording>    correct how the agent phrased something
/delete n4                remove a branch you don't agree with
/explore n1               ask the agent to follow a different node next
```

The agent sees your edits and the new outline, is told not to undo them, and follows your `/explore` request.

## The agent

The model never writes prose to you. It only calls tools, and `ask` is the only one that reaches you:

| Tool | What it does |
|---|---|
| `set_ring(node_id, ring, reason, shifts_when?)` | place or move a node |
| `ask(node_id, kind, question)` | one question about one node; returns your answer plus any map edits you made |
| `add_cause(parent_id, text, ring, reason, actionable, shifts_when?)` | a cause under a node |
| `add_action(parent_id, text, ring, reason)` | something you could do; control or influence only |
| `add_consequence(parent_id, text, ring, reason)` | where a what-if would lead |
| `search_history(text)` / `link_past(node_id, past_ref)` | connect to the same cause in a past session |
| `finish(summary, next_move, actions, accept)` | end; rejected without a next move, an action per lever, or a what-if |

The loop (`lifegraph/agent.py`) is about 50 lines: model picks a tool, Python runs it against the graph, the result goes back as a tool message, repeat until `finish`. The guardrails live in `lifegraph/tools.py`, not in the prompt: classify before probing, no `why` past depth 5, 12 questions max, at least one what-if, `accept` only for outside nodes.

## Run it locally with Gemma 4

```bash
pip install -r requirements.txt            # only dependency: openai SDK, used as a generic client
ollama pull gemma4:e4b
python -m lifegraph ask                     # landing screen with categories
python -m lifegraph ask "I hate my job"     # or jump straight in
```

Each session writes `data/sessions/<id>.json` and `data/sessions/<id>.html` (next move at the top, the graph on the left with levers and boundary crossings marked, the three regions on the right).

Which Gemma 4 to pull:

| Tag | Good for | Notes |
|---|---|---|
| `gemma4:e2b` | laptops with little RAM | fastest; can stumble on multi-step tool use |
| `gemma4:e4b` | most laptops (default) | tool calling, plus native audio input |
| `gemma4:26b` | 16GB+ machines | MoE, only 4B active so it is fast; best tool-calling reliability |
| `gemma4:31b` | a desktop GPU | dense, strongest answers |

If the agent loops on errors or writes prose instead of calling tools, move one row down the table. Keep Ollama current: early 0.20.x builds had a broken tool parser for Gemma 4. Add `--verbose` to watch every tool call.

## Or hosted Gemma 4 on the Gemini API

```bash
export GEMINI_API_KEY=...                   # from https://aistudio.google.com
python -m lifegraph ask --gemini "I hate my job"                # gemma-4-26b-a4b-it
python -m lifegraph ask --gemini --model gemma-4-31b-it "..."
```

Same open weights, same agent, just not on your machine. Other OpenAI-compatible endpoints work with `--base-url` and `--model`, or `LIFEGRAPH_BASE_URL`, `LIFEGRAPH_MODEL`, `LIFEGRAPH_API_KEY`.

## Explore your decision graph

```bash
python -m lifegraph roots
```

prints causes that sit under more than one problem, sorted by how many problems they explain and then by region (control first). That list is the point of the whole thing.

## Test without a model

```bash
python -m unittest discover tests
```

`tests/fake_model.py` replays the career example above as a scripted list of tool calls through the real loop, tool runner, graph and renderer, so the whole pipeline is covered without a model server.

## Layout

```
lifegraph/
  agent.py     the loop
  tools.py     tool schemas, ToolRunner (the guardrails), /commands for editing the map
  graph.py     Graph: nodes, regions, boundary edges, levers, history search, recurring roots
  prompts.py   system prompt
  render.py    HTML page: next move, graph, three regions
  cli.py       landing screen, `ask` and `roots`
tests/
  fake_model.py  scripted model for tests and demos
  test_agent.py
```

## Not therapy

This is a reflection tool. The prompt forbids the model from labelling you or turning answers into self-blame, and rephrases self-worth answers as concrete situations. If a session goes somewhere heavier than a planning tool should handle, stop and talk to a person.
