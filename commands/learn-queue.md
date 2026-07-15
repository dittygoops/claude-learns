---
description: View queued learnings without processing them
---

# /learn-queue — peek at the queue

Read `~/.claude/projects/<sanitized-cwd>/claude-learns-queue.json` (derive the
sanitized name from the current working directory: replace `/` and `.` with
`-`). If missing or empty, say so.

Otherwise print a compact table: captured date, type, confidence, and the rule.
Do not modify the queue. Remind the user that /learn processes it.
