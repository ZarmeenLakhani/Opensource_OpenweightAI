"""Run a Why Rings session from the terminal against any OpenAI-compatible open-weight endpoint."""

import argparse
import os
import sys

from .agent import run_agent
from .graph import recurring_roots
from .render import save_html


def _client(base_url, api_key):
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("pip install openai  (the only runtime dependency)")
    return OpenAI(base_url=base_url, api_key=api_key)


def _print_graph(graph):
    print()
    for node_id in graph.dfs_order():
        node = graph.nodes[node_id]
        marker = " <- lever" if node_id in graph.levers() else ""
        print(f"{'  ' * node['depth']}[{node['ring']}] {node['text']}{marker}")
    print(f"\n{graph.summary}\n")
    if graph.actions:
        print("Do this week:")
        for node_id, action in graph.actions.items():
            print(f"  - {graph.nodes[node_id]['text']}: {action}")
    if graph.accept:
        print("\nLet go of:")
        for node_id, note in graph.accept.items():
            print(f"  - {graph.nodes[node_id]['text']}: {note}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="whyrings")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ask = sub.add_parser("ask", help="start a 5 Whys session")
    ask.add_argument("problem", nargs="?", help="the thing that keeps happening")
    ask.add_argument("--model", default=os.environ.get("WHYRINGS_MODEL", "qwen2.5:7b"))
    ask.add_argument("--base-url", default=os.environ.get("WHYRINGS_BASE_URL", "http://localhost:11434/v1"))
    ask.add_argument("--api-key", default=os.environ.get("WHYRINGS_API_KEY", "ollama"))
    ask.add_argument("--data-dir", default=os.environ.get("WHYRINGS_DATA", "data"))
    ask.add_argument("--verbose", action="store_true", help="print every tool call")

    roots = sub.add_parser("roots", help="causes that show up under more than one problem")
    roots.add_argument("--data-dir", default=os.environ.get("WHYRINGS_DATA", "data"))

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

    problem = args.problem or input("What keeps happening? ").strip()
    if not problem:
        return 1

    def ask_user(question):
        print(f"\n{question}")
        return input("> ").strip()

    def on_event(kind, payload):
        if args.verbose:
            print(f"  [{kind}] {payload}")

    client = _client(args.base_url, args.api_key)
    graph = run_agent(client, args.model, problem, ask_user, args.data_dir, on_event=on_event)
    _print_graph(graph)
    json_path = graph.save(args.data_dir)
    html_path = save_html(graph, args.data_dir)
    print(f"\nSaved {json_path} and {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
