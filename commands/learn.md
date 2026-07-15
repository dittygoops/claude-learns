---
description: Review queued learnings and route each by tier (hook / CLAUDE.md / memory)
---

# /learn — review the learnings queue

Process the claude-learns queue for this project with the user in the loop.
The queue lives at `<project transcript dir>/claude-learns-queue.json`, i.e.
`~/.claude/projects/<sanitized-cwd>/claude-learns-queue.json` (derive the
sanitized name from the current working directory: replace `/` and `.` with `-`).

## Steps

1. Read the queue file. If missing or empty, tell the user there is nothing to
   review and stop.

2. First pass, silently: group near-duplicate learnings (same rule in different
   words) and note any learning that matches a rule ALREADY in CLAUDE.md or an
   existing hook. A repeat means the existing rule is not working; flag it as
   **recurrence** rather than proposing it again.

3. Present learnings one at a time (or grouped when near-duplicates). For each,
   show: the rule, the type, the evidence quote, what the assistant did, and
   confidence. Then ask the user: **Apply / Edit / Skip**.

4. On Apply, route by type:
   - **mechanical** → do NOT add to CLAUDE.md. Offer to generate a deterministic
     enforcement: a hook script (Stop/PreToolUse in `~/.claude/hooks/` +
     settings.json registration), a linter/formatter config entry, or a
     pre-commit check. Write it, test it with piped sample input, show the user.
   - **judgment** → add ONE tight bullet to the project's CLAUDE.md (or
     `~/.claude/CLAUDE.md` if the user says it is global), phrased as an
     imperative with a concrete example. Keep CLAUDE.md small: if it already
     has many rules, suggest pruning stale ones in the same pass.
   - **fact** → store in the memory system (project memory file), not in rules.
   - **recurrence** → show the existing rule next to the new evidence and ask
     whether to sharpen its wording or promote it to a harder tier (judgment →
     mechanical hook).

5. On Edit, let the user rewrite the rule, then route as above.
   On Skip, drop it.

6. After all items: remove processed items from the queue file (keep any the
   user deferred), and summarize what was applied where.

## Principles

- Never apply anything without the user's explicit choice.
- Fewer, sharper rules beat many vague ones. Push back on rules that are
  one-time clarifications in disguise.
- Prefer the hardest enforcement tier that fits: hook > CLAUDE.md > memory.
