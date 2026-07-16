#!/usr/bin/env python3
"""claude-learns SessionStart hook: remind the user when learnings are queued.

Plain stdout from a SessionStart hook is injected into Claude's context, not
shown to the user. To surface the reminder in the terminal we emit JSON with
a `systemMessage` (displayed to the user) and also pass the note to Claude
via hookSpecificOutput.additionalContext.
"""
import json
import os
import sys

QUEUE_NAME = "claude-learns-queue.json"


def main():
    if os.environ.get("CLAUDE_LEARNS_EXTRACTING"):
        return
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    transcript_path = data.get("transcript_path")
    if not transcript_path:
        return
    queue_path = os.path.join(os.path.dirname(transcript_path), QUEUE_NAME)
    if not os.path.exists(queue_path):
        return
    try:
        with open(queue_path) as f:
            queue = json.load(f)
    except (json.JSONDecodeError, OSError):
        return
    if not queue:
        return
    note = (f"claude-learns: {len(queue)} learning(s) queued for this project. "
            f"Run /learn to review.")
    print(json.dumps({
        "systemMessage": note,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": note,
        },
    }))


if __name__ == "__main__":
    main()
