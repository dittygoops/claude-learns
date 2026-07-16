#!/usr/bin/env python3
"""claude-learns rules compiler: regenerate CLAUDE.md from a rules registry.

The registry (rules.json) is the source of truth for judgment rules; CLAUDE.md
is a compiled artifact. The compiler owns only a marker-delimited block inside
CLAUDE.md, so hand-written content outside the markers survives recompilation.

Policy:
- Rules with enforcement other than "claude-md" (hooks, lint) are never
  emitted: they are enforced deterministically elsewhere and would only
  dilute the context.
- Universal rules are always inline.
- Activity-scoped rules are inline under a "When <activity>:" heading while
  the total emitted rule count is <= INLINE_LIMIT. Past that, each activity
  group is compiled to <rules_dir>/<activity>.md and CLAUDE.md carries a
  one-line pointer instead, keeping the always-loaded context small.

Usage: compile_rules.py <rules.json> <CLAUDE.md path> [rules_dir]
  rules_dir defaults to ".claude/rules" next to the CLAUDE.md file.
"""
import json
import os
import sys

BEGIN = "<!-- claude-learns:begin (generated from rules.json; edit the registry, not this block) -->"
END = "<!-- claude-learns:end -->"
INLINE_LIMIT = 8


def load_registry(path):
    with open(path) as f:
        reg = json.load(f)
    rules = [r for r in reg.get("rules", []) if r.get("status", "active") == "active"]
    return [r for r in rules if r.get("enforcement", "claude-md") == "claude-md"]


def render(rules, rules_dir, claude_md_dir):
    universal = [r for r in rules if not r.get("activities")]
    by_activity = {}
    for r in rules:
        for act in r.get("activities", []):
            by_activity.setdefault(act, []).append(r)

    lines = []
    for r in universal:
        lines.append(f"- {r['rule']}")

    inline = len(rules) <= INLINE_LIMIT
    pointer_files = {}
    for act in sorted(by_activity):
        group = by_activity[act]
        if inline:
            lines.append(f"- When working on {act}:")
            for r in group:
                lines.append(f"  - {r['rule']}")
        else:
            rel = os.path.join(rules_dir, f"{act}.md")
            body = [f"# Rules: {act}", ""]
            for r in group:
                body.append(f"- {r['rule']}")
                if r.get("example"):
                    body.append(f"  - Example: {r['example']}")
            pointer_files[os.path.join(claude_md_dir, rel)] = "\n".join(body) + "\n"
            lines.append(f"- Before working on {act}, read `{rel}` and follow its rules.")
    return "\n".join(lines), pointer_files


def splice(claude_md_path, block):
    content = ""
    if os.path.exists(claude_md_path):
        with open(claude_md_path) as f:
            content = f.read()
    generated = f"{BEGIN}\n{block}\n{END}"
    if BEGIN in content and END in content:
        pre = content.split(BEGIN)[0]
        post = content.split(END, 1)[1]
        content = pre + generated + post
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        content += generated + "\n"
    with open(claude_md_path, "w") as f:
        f.write(content)


def main():
    registry_path, claude_md_path = sys.argv[1], sys.argv[2]
    claude_md_dir = os.path.dirname(os.path.abspath(claude_md_path))
    rules_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(".claude", "rules")

    rules = load_registry(registry_path)
    block, pointer_files = render(rules, rules_dir, claude_md_dir)
    for path, body in pointer_files.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(body)
    splice(claude_md_path, block)
    print(f"compiled {len(rules)} rule(s) -> {claude_md_path}"
          + (f" + {len(pointer_files)} topic file(s)" if pointer_files else ""))


if __name__ == "__main__":
    main()
