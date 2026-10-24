"""Run a LifeGraph session from the terminal against Gemma 4 (local Ollama or Google's Gemini API)."""

import argparse
import os
import sys

from .agent import DEFAULT_TEMPERATURE, run_agent
from .graph import recurring_roots
from .render import save_html
from .tools import USER_COMMANDS

# Gemma 4 hosted on Google's Gemini API, through its OpenAI-compatible endpoint.
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_DEFAULT_MODEL = "gemma-4-26b-a4b-it"
LOCAL_DEFAULT_MODEL = "gemma4:e4b"

CATEGORIES = [
    "Career, ambition, or purpose",
    "Relationships or conflict",
    "A difficult decision",
    "Feeling stuck or overwhelmed",
    "Anything else",
]


def _client(base_url, api_key):
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("pip install openai  (the only runtime dependency)")
    return OpenAI(base_url=base_url, api_key=api_key)


def _landing():
    print("\nLifeGraph · Start with what's weighing on you")
    print("Enter a real problem or a hypothetical one. You don't need to know the root cause yet.\n")
    for i, c in enumerate(CATEGORIES, 1):
        print(f"  {i}. {c}")
    print()
    while True:
        raw = input("Pick a number, or just type the problem: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(CATEGORIES):
            print(f"\n{CATEGORIES[int(raw) - 1]}. What's going on?")
            raw = input("> ").strip()
        if raw:
            return raw


def _print_graph(graph):
    print("\n" + graph.outline())
    print(f"\n{graph.summary}")
    print(f"\nYOUR NEXT MOVE\n  {graph.next_move}")
    if graph.actions:
        print("\nAt the levers:")
        for node_id, action in graph.actions.items():
            print(f"  - {graph.nodes[node_id]['text']}: {action}")
    if graph.accept:
        print("\nLet go of:")
        for node_id, note in graph.accept.items():
            print(f"  - {graph.nodes[node_id]['text']}: {note}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lifegraph")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ask = sub.add_parser("ask", help="start a session")
    ask.add_argument("problem", nargs="?", help="what's weighing on you; omit for the landing screen")
    ask.add_argument("--model", default=os.environ.get("LIFEGRAPH_MODEL", LOCAL_DEFAULT_MODEL))
    ask.add_argument("--base-url", default=os.environ.get("LIFEGRAPH_BASE_URL", "http://localhost:11434/v1"))
    ask.add_argument("--api-key", default=os.environ.get("LIFEGRAPH_API_KEY", "ollama"))
    ask.add_argument("--data-dir", default=os.environ.get("LIFEGRAPH_DATA", "data"))
    ask.add_argument("--temperature", type=float, default=float(os.environ.get("LIFEGRAPH_TEMPERATURE", DEFAULT_TEMPERATURE)),
                     help=f"sampling temperature, 0 to 2 (default {DEFAULT_TEMPERATURE}); higher is more varied, lower is more reliable tool calls")
    ask.add_argument("--verbose", action="store_true", help="print every tool call")
    ask.add_argument(
        "--gemini",
        action="store_true",
        help="use Gemma 4 on Google's Gemini API (hosted) instead of local Ollama; needs GEMINI_API_KEY",
    )

    serve = sub.add_parser("serve", help="run the web UI at http://localhost:8000")
    serve.add_argument("--port", type=int, default=int(os.environ.get("LIFEGRAPH_PORT", "8000")))
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--model", default=os.environ.get("LIFEGRAPH_MODEL", LOCAL_DEFAULT_MODEL))
    serve.add_argument("--base-url", default=os.environ.get("LIFEGRAPH_BASE_URL", "http://localhost:11434/v1"))
    serve.add_argument("--api-key", default=os.environ.get("LIFEGRAPH_API_KEY", "ollama"))
    serve.add_argument("--data-dir", default=os.environ.get("LIFEGRAPH_DATA", "data"))
    serve.add_argument("--temperature", type=float, default=float(os.environ.get("LIFEGRAPH_TEMPERATURE", DEFAULT_TEMPERATURE)),
                     help="default sampling temperature for sessions; the landing page can override it per session")
    serve.add_argument("--gemini", action="store_true", help="use Gemma 4 on Google's Gemini API; needs GEMINI_API_KEY")

    roots = sub.add_parser("roots", help="explore your decision graph: causes under more than one problem")
    roots.add_argument("--data-dir", default=os.environ.get("LIFEGRAPH_DATA", "data"))

    args = parser.parse_args(argv)

    if args.cmd == "roots":
        groups = recurring_roots(args.data_dir)
        if not groups:
            print("No cause is linked across sessions yet. Run more sessions; the agent links repeats with link_past.")
            return 0
        for g in groups:
            print(f"[{g['ring']}] {g['text']}  ({len(g['problems'])} problems)")
            for p in g["problems"]:
                print(f"    - {p}")
        return 0

    if args.gemini:
        args.base_url = GEMINI_BASE_URL
        args.api_key = os.environ.get("GEMINI_API_KEY", "")
        if not args.api_key:
            sys.exit("--gemini needs GEMINI_API_KEY in the environment (get one at https://aistudio.google.com)")
        if "LIFEGRAPH_MODEL" not in os.environ and args.model == LOCAL_DEFAULT_MODEL:
            args.model = GEMINI_DEFAULT_MODEL

    if args.cmd == "serve":
        from .server import serve as run_server

        run_server(_client(args.base_url, args.api_key), args.model, args.data_dir, host=args.host, port=args.port,
                   temperature=args.temperature)
        return 0

    problem = args.problem or _landing()
    print(f"\n({USER_COMMANDS.splitlines()[0]} type /help to see how.)")

    def ask_user(question):
        print(f"\n{question}")
        return input("> ").strip()

    def on_event(kind, payload):
        if args.verbose:
            print(f"  [{kind}] {payload}")

    client = _client(args.base_url, args.api_key)
    graph = run_agent(client, args.model, problem, ask_user, args.data_dir, on_event=on_event, temperature=args.temperature)
    _print_graph(graph)
    json_path = graph.save(args.data_dir)
    html_path = save_html(graph, args.data_dir)
    print(f"\nSaved {json_path} and {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
