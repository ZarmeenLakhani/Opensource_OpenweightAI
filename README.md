# LifeGraph

[![tests](https://github.com/ZarmeenLakhani/Opensource_OpenweightAI/actions/workflows/tests.yml/badge.svg)](https://github.com/ZarmeenLakhani/Opensource_OpenweightAI/actions/workflows/tests.yml)

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

**3. Lay out the paths.** The agent proposes two or three paths for your situation and runs a what-if on each, so the tree shows what each path leads to:

```
                        [ I hate my job ]
                   (what bothers me · 4, click to open)
          ┌───────────────────┼─────────────────────┐
 [ Stay another year ]  [ Ask to own a project ]  [ Test one idea on the side ]
          │                   │                       │
   salary stays,        know within a month      learn if anyone wants it
   resentment grows     → negotiate ownership    → build a prototype
                                                 → test customer demand
                                                 → set a savings target
```

Every node is colored by region: green you control, amber you can influence, grey is outside your control. The lever (the last node you can reach before a chain goes outside) is outlined red.

**4. Your quest this week.** "Spend two hours this week interviewing three potential customers about one idea. No resignation required." Mark it done when you have, and it counts.

## What the agent does that a worksheet doesn't

- **Digs with the five whys, adaptively.** Up to five `why` probes, each shaped by the previous answer, plus `clarify` to surface the assumption or competing need. Five is the ceiling, not the target: a branch stops when its newest cause is clearly actionable or clearly outside your control.
- **Lays out paths and tests them.** Two or three `option` nodes (stay, change within, leave, phrased for you), then a `what_if` on each. It must lay out at least two paths and run at least one what-if before it is allowed to finish.
- **Builds a living graph.** Nodes are causes, paths, consequences or actions. One answer can open two causes (a branch). Consequences and actions hang off the path they belong to.
- **Classifies honestly.** Each node has a region and, where it applies, a `shifts_when` condition ("moves to control once savings cover 6 months"). Actions can never be placed in "outside".
- **Finds the lever.** Where a cause chain crosses from your reach into "outside", the node just before the crossing is a lever. The agent must give a concrete action for every lever.
- **Ends with the smallest useful action.** `finish` is rejected without a single `next_move`.
- **Makes it a game.** Points for every cause dug (+10), lever found (+25), path laid out (+15), what-if explored (+20), a next move (+50) and a quest done (+100). The dock shows the stage you are in (dig, paths, what ifs, your move), how much of the map is within your reach, and your xp. The landing page keeps lifetime totals: xp, quests done, levers found.
- **Lets you challenge the map.** Click any node to move it between regions, remove its branch, or send the agent down it next. Or type a command instead of an answer:

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
| `add_option(parent_id, text, ring, reason)` | a path you could take; control or influence only |
| `add_action(parent_id, text, ring, reason)` | something you could do; control or influence only |
| `add_consequence(parent_id, text, ring, reason)` | where a path or what-if would lead |
| `search_history(text)` / `link_past(node_id, past_ref)` | connect to the same cause in a past session |
| `finish(summary, next_move, actions, accept)` | end; rejected without a next move, two paths, a what-if, or an action per lever |

The loop (`lifegraph/agent.py`) is about 50 lines: model picks a tool, Python runs it against the graph, the result goes back as a tool message, repeat until `finish`. The guardrails live in `lifegraph/tools.py`, not in the prompt: classify before probing, no `why` past depth 5, 12 questions max, at least one what-if, `accept` only for outside nodes.

## Run it locally with Gemma 4

```bash
pip install -r requirements.txt            # only dependency: openai SDK, used as a generic client
ollama pull gemma4:e4b
python -m lifegraph serve                   # web UI at http://localhost:8000
```

Open http://localhost:8000: the landing screen with categories, then a chat on the left and the live map on the right (three regions filling in as you answer, the graph tree underneath, your next move at the top when it finishes). The web server is Python's standard library, nothing else to install. `--port`, `--model`, `--base-url` and `--gemini` work the same as for `ask`.

Prefer the terminal?

```bash
python -m lifegraph ask                     # landing screen with categories
python -m lifegraph ask "I hate my job"     # or jump straight in
```

Each session writes `data/sessions/<id>.json` and `data/sessions/<id>.html` (next move at the top, the graph on the left with levers and boundary crossings marked, the three regions on the right). Past sessions are listed on the landing page.

Which Gemma 4 to pull:

| Tag | Good for | Notes |
|---|---|---|
| `gemma4:e2b` | laptops with little RAM | fastest; can stumble on multi-step tool use |
| `gemma4:e4b` | most laptops (default) | tool calling, plus native audio input |
| `gemma4:26b` | 16GB+ machines | MoE, only 4B active so it is fast; best tool-calling reliability |
| `gemma4:31b` | a desktop GPU | dense, strongest answers |

If the agent loops on errors or writes prose instead of calling tools, move one row down the table. Keep Ollama current: early 0.20.x builds had a broken tool parser for Gemma 4. Add `--verbose` to watch every tool call.

**Temperature.** Default `0.3`, which keeps tool calls well-formed. Raise it for more varied questions and paths, lower it if a small model starts producing broken tool calls:

```bash
python -m lifegraph serve --temperature 0.8          # server default
LIFEGRAPH_TEMPERATURE=0.8 python -m lifegraph ask "..."
```

The landing page has a slider that sets it per session, remembered in your browser. Values are clamped to 0 to 2.

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
  server.py    local web server: sessions in threads, JSON API
  web/index.html  the page: landing, chat, live map
  cli.py       `serve`, `ask` (terminal) and `roots`
tests/
  fake_model.py  scripted model for tests and demos
  test_agent.py
  test_server.py drives a full session over HTTP
```

## Not therapy

This is a reflection tool. The prompt forbids the model from labelling you or turning answers into self-blame, and rephrases self-worth answers as concrete situations. If a session goes somewhere heavier than a planning tool should handle, stop and talk to a person.
