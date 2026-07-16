# claude-learns

Semantic correction capture for Claude Code.

Existing correction-capture tools gate their queue with regex on each user
prompt. Regex misses most real corrections: they appear mid-message, buried
between agreements, or phrased as questions ("why does the doc say X?"). And a
user message alone isn't a learning; the learning is the *pair* of what the
assistant did and what the user said about it.

claude-learns takes a different approach:

1. **Capture** — a `SessionEnd` hook condenses the full session transcript and
   makes one cheap model call (Haiku by default) to extract learnings
   semantically, with the assistant's actions as context. One-time task
   clarifications are discarded; generalizable corrections, preferences, and
   facts are queued.
2. **Review** — `/learn` walks the queue with you (Apply / Edit / Skip).
   Nothing is ever applied without your say.
3. **Route by tier** — approved learnings go to the *hardest enforcement tier
   that fits*, instead of all becoming CLAUDE.md bullets:
   - **mechanical** (bannable tokens, formatting, required commands) → a
     generated hook or lint rule that *enforces* the behavior deterministically
   - **judgment** (style, scope, approach) → one tight, example-laden
     CLAUDE.md bullet
   - **fact** (names, paths, conventions) → memory, not rules
4. **Recurrence tracking** — if a new correction matches a rule you already
   have, `/learn` flags it: the rule isn't working, so sharpen it or promote
   it to a harder tier.

## Install

```bash
claude plugin marketplace add <you>/claude-learns
claude plugin install claude-learns@claude-learns-marketplace --scope user
```

## Commands

- `/learn` — review and route queued learnings
- `/learn-queue` — peek at the queue without processing

## Cost & privacy

Extraction runs one `claude -p` call (Haiku) per session with at least two
user messages, capped at ~60k characters of condensed dialogue. This spends
your API/subscription tokens (typically well under a cent per session). Your
transcript is sent only to the same Anthropic API your session already uses.
Set `CLAUDE_LEARNS_MODEL` to override the model.

## How it avoids footguns

- The SessionEnd hook returns in milliseconds: it spawns a detached worker
  process that does the extraction, so session exit is never blocked and the
  hook can't be cancelled mid-extraction (long transcripts can take minutes).
- Worker results and failures are logged to `claude-learns.log` next to the
  queue; the SessionStart reminder surfaces new learnings the next session.
- An env guard (`CLAUDE_LEARNS_EXTRACTING`) prevents the extraction
  subprocess's own session from re-triggering the hook.
- Trivial sessions (fewer than two user messages) are skipped.
- Exact-duplicate rules are deduped by content hash at queue time;
  near-duplicates (same rule, different words) are merged during `/learn`.

## License

MIT
