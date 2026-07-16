#!/usr/bin/env python3
"""claude-learns SessionEnd hook: extract learnings from the session transcript.

Condenses the transcript into a USER/ASSISTANT dialogue, asks a cheap model
to extract corrections, preferences, and facts (judged semantically, so they
can appear anywhere in a message), and appends them to the project's queue
for later human review via /learn.

The hook itself returns immediately: it validates the payload, then respawns
this script detached (--worker) so extraction never blocks session exit or
gets cancelled by the hook timeout. Results land in the queue; the
SessionStart reminder surfaces them next session. Worker activity is logged
to claude-learns.log next to the queue.

Safety:
- CLAUDE_LEARNS_EXTRACTING env guard prevents the extraction subprocess's own
  session from re-triggering this hook (infinite loop).
- Sessions with fewer than MIN_USER_MESSAGES user messages are skipped.
- One model call per session, dialogue capped at MAX_DIALOGUE chars.
- The model subprocess runs with --strict-mcp-config so it skips MCP servers.
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

MODEL = os.environ.get("CLAUDE_LEARNS_MODEL", "claude-haiku-4-5-20251001")
MAX_TEXT = 700           # chars per message before truncation
MAX_DIALOGUE = 60000     # chars of dialogue sent to the model
MIN_USER_MESSAGES = 2    # skip trivial sessions
QUEUE_NAME = "claude-learns-queue.json"

EXTRACTION_PROMPT = """\
You are analyzing a transcript of a session between a user and an AI coding \
assistant. Your job is to extract LEARNINGS: things the user corrected, \
redirected, or expressed as a lasting preference, which should change how the \
assistant behaves in FUTURE sessions.

A correction can appear anywhere: mid-message, buried between agreements, \
phrased as a question, or implied ("why does the doc say X?" when X is wrong). \
Judge by meaning, not phrasing.

Classify each learning:
- "mechanical": enforceable by a deterministic check (formatting, naming,
  banned tokens, required commands). Could become a lint rule or hook.
- "judgment": requires context to apply (style, scope, approach, tone).
  Could become a CLAUDE.md guideline.
- "fact": a stable fact about the user or project (names, paths, stack,
  conventions). Belongs in memory, not rules.

DISCARD (do not output):
- One-time task clarifications that don't generalize ("no, edit the other file").
- The user changing their own mind about requirements.
- Normal iteration on work-in-progress ("make the button blue instead").
- Anything already being handled correctly after one mention within the session,
  UNLESS the user framed it as a lasting preference.

For each learning output:
- "type": mechanical | judgment | fact
- "evidence": short verbatim quote(s) from the user
- "assistant_did": one sentence, what the assistant did that triggered it
  (or "unprompted preference" if the user simply stated it)
- "rule": one imperative sentence, the generalized rule for future sessions
- "confidence": 0.0-1.0, how sure you are this generalizes beyond this session

Output ONLY a JSON array (possibly empty). No markdown fences, no commentary.

TRANSCRIPT:
"""


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            c.get("text", "") for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        )
    return ""


def tools_of(content):
    if not isinstance(content, list):
        return []
    return [
        f"[tool: {c.get('name', '?')}]" for c in content
        if isinstance(c, dict) and c.get("type") == "tool_use"
    ]


def condense(path):
    """Turn a transcript JSONL into USER:/ASSISTANT: dialogue. Returns (dialogue, n_user_msgs)."""
    lines = []
    n_user = 0
    with open(path, errors="ignore") as f:
        for raw in f:
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            role = d.get("type")
            if role not in ("user", "assistant"):
                continue
            msg = d.get("message", {})
            text = text_of(msg.get("content")).strip()
            if role == "user" and (not text or text.startswith(("<", "[Request", "Caveat:"))):
                continue
            if role == "assistant":
                tools = tools_of(msg.get("content"))
                if not text and not tools:
                    continue
                body = text if text else " ".join(tools)
            else:
                n_user += 1
                body = text
            if len(body) > MAX_TEXT:
                body = body[:MAX_TEXT] + " [...truncated]"
            tag = "USER" if role == "user" else "ASSISTANT"
            if lines and tag == "ASSISTANT" and lines[-1].startswith(tag + ":"):
                lines[-1] += "\n" + body
            else:
                lines.append(f"{tag}: {body}")
    dialogue = "\n\n".join(lines)
    if len(dialogue) > MAX_DIALOGUE:
        dialogue = dialogue[-MAX_DIALOGUE:]  # keep the most recent portion
    return dialogue, n_user


def extract(dialogue):
    env = dict(os.environ, CLAUDE_LEARNS_EXTRACTING="1")
    result = subprocess.run(
        ["claude", "-p", "--model", MODEL, "--strict-mcp-config"],
        input=EXTRACTION_PROMPT + dialogue,
        capture_output=True, text=True, timeout=600, env=env,
    )
    out = result.stdout.strip()
    if out.startswith("```"):
        out = out.strip("`\n")
        if out.startswith("json"):
            out = out[4:]
    learnings = json.loads(out)
    if not isinstance(learnings, list):
        return []
    return [l for l in learnings if isinstance(l, dict) and l.get("rule")]


def append_to_queue(queue_path, learnings, session_id):
    existing = []
    if os.path.exists(queue_path):
        try:
            with open(queue_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = []
    seen = {e.get("hash") for e in existing}
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    for l in learnings:
        h = hashlib.sha256(l["rule"].lower().encode()).hexdigest()[:16]
        if h in seen:
            continue
        seen.add(h)
        existing.append({
            "hash": h,
            "captured_at": now,
            "session_id": session_id,
            **l,
        })
        added += 1
    with open(queue_path, "w") as f:
        json.dump(existing, f, indent=2)
    return added, len(existing)


def log(transcript_path, msg):
    log_path = os.path.join(os.path.dirname(transcript_path), "claude-learns.log")
    try:
        with open(log_path, "a") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")
    except OSError:
        pass


def worker(transcript_path, session_id):
    """Detached worker: condense, extract, append. May take minutes."""
    try:
        dialogue, n_user = condense(transcript_path)
    except OSError as e:
        log(transcript_path, f"session {session_id}: condense failed: {e}")
        return
    if n_user < MIN_USER_MESSAGES or not dialogue.strip():
        return

    try:
        learnings = extract(dialogue)
    except Exception as e:
        log(transcript_path, f"session {session_id}: extraction failed: {e}")
        return

    queue_path = os.path.join(os.path.dirname(transcript_path), QUEUE_NAME)
    added, total = append_to_queue(queue_path, learnings, session_id)
    log(transcript_path, f"session {session_id}: extracted {len(learnings)}, "
                         f"queued {added} new ({total} total)")


def hook():
    """SessionEnd hook: validate payload, spawn detached worker, return fast."""
    if os.environ.get("CLAUDE_LEARNS_EXTRACTING"):
        return  # we ARE the extraction subprocess; never recurse

    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    transcript_path = data.get("transcript_path")
    if not transcript_path or not os.path.exists(transcript_path):
        return

    devnull = open(os.devnull, "r+b")
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--worker",
         transcript_path, data.get("session_id", "")],
        stdin=devnull, stdout=devnull, stderr=devnull,
        start_new_session=True,  # survive the parent session's exit
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    else:
        hook()
