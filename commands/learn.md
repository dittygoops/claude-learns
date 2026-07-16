---
description: Review queued learnings, update the rules registry, and recompile CLAUDE.md
---

# /learn — review the learnings queue

Process the claude-learns queue for this project with the user in the loop.
The queue lives at `<project transcript dir>/claude-learns-queue.json`, i.e.
`~/.claude/projects/<sanitized-cwd>/claude-learns-queue.json` (derive the
sanitized name from the current working directory: replace `/` and `.` with `-`).

## The rules registry

The registry is the source of truth for rules; CLAUDE.md is a compiled
artifact and must never be edited by hand during /learn.

- Project registry: `.claude/rules.json` in the project root.
- Global registry: `~/.claude/rules.json`.

Registry format:

```json
{
  "rules": [
    {
      "id": "kebab-case-slug",
      "rule": "One imperative sentence.",
      "example": "optional concrete example",
      "tier": "mechanical | judgment",
      "activities": ["prd-writing"],
      "enforcement": "claude-md | hook:<script path> | lint:<config path>",
      "evidence": ["verbatim user quote"],
      "created": "YYYY-MM-DD",
      "violations": ["YYYY-MM-DD"],
      "status": "active | retired"
    }
  ]
}
```

`activities` is the ontology axis: a short kebab-case tag for when the rule
applies (e.g. `prd-writing`, `outreach-drafting`, `git-commits`). Empty list =
universal, applies to every session. Reuse existing tags from the registry
before inventing new ones; a fragmented tag vocabulary defeats grouping.

## Steps

1. Read the queue. If missing or empty, say so and stop.

2. Read both registries. First pass, silently: group near-duplicate queue
   items, and match each item against registry rules (including hook/lint
   enforced ones). A match is a **recurrence**: record it, don't re-propose it.

3. Present items one at a time (grouped when near-duplicates). Show: rule,
   type, evidence, what the assistant did, confidence, and any recurrence
   match. Ask: **Apply / Edit / Skip**.

4. On Apply:
   - **mechanical** → generate the deterministic enforcement: a hook script
     (in `~/.claude/hooks/` + settings.json registration) or a lint/formatter
     config entry. Test it with piped sample input. Then add the rule to the
     registry with `enforcement: "hook:..."` or `"lint:..."` so recurrence
     tracking sees it. It will NOT be emitted into CLAUDE.md.
   - **judgment** → add to the project registry (or global if the user says
     it applies everywhere) with `enforcement: "claude-md"`, one imperative
     sentence plus an example, and activity tags (ask yourself: does this rule
     matter on every turn, or only during a specific activity?).
   - **fact** → store in the memory system, not in any registry.
   - **recurrence** → increment the rule's `violations` with today's date,
     then discuss with the user: sharpen the wording, or promote the tier
     (judgment → hook) if violations keep accumulating.

5. On Edit, let the user rewrite, then route as above. On Skip, drop it.

6. After all items, recompile every registry you touched:
   - project: `python3 "<plugin root>/scripts/compile_rules.py" .claude/rules.json CLAUDE.md`
   - global: `python3 "<plugin root>/scripts/compile_rules.py" ~/.claude/rules.json ~/.claude/CLAUDE.md rules`

   (`<plugin root>` is this plugin's directory; find it via the path of this
   command file.) Show the user the resulting CLAUDE.md block.

7. Remove processed items from the queue (keep deferred ones) and summarize
   what was applied where.

## Principles

- Never apply anything without the user's explicit choice.
- Fewer, sharper rules beat many vague ones. Push back on one-time
  clarifications dressed up as rules.
- Prefer the hardest enforcement tier that fits: hook > CLAUDE.md > memory.
- Registry rules the user retires stay in the file with `status: "retired"`
  (history matters for recurrence analysis); the compiler skips them.
