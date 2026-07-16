# Claude Code Context Pack

Everything needed to manage context health across a Claude Code session and across sessions — no security guardrails (dangerous commands, secret files, formatting), since that's already covered elsewhere on your team.

## What's in it

### Context handoff — always exactly one `handoff.md`

| Hook | Event | What it does |
|---|---|---|
| `precompact-handoff.sh` | `PreCompact` (matcher: `auto`) | Fires exactly when Claude Code is about to auto-compact because context is nearly full. Blocks compaction **once** and instructs Claude to write a real handoff summary to `.claude/handoff.md` (current task, decisions made, files touched, open questions, next steps). A marker file prevents it from blocking repeatedly. |
| `sessionstart-handoff-notice.sh` | `SessionStart` (matcher: `startup,resume`) | If `.claude/handoff.md` exists, adds a quiet one-line note to context: it exists, don't load it unless asked. Nothing is auto-injected. |
| `userprompt-handoff-inject.sh` | `UserPromptSubmit` | Scans the user's message for phrases like "continue from last time", "resume", "pick up where we left off". Only when one matches does it inject the full `handoff.md` content into that turn's context. |

`handoff.md` is overwritten each time, never accumulated into a growing history file.

### Verified handoffs

A `"type": "prompt"` `PostToolUse` hook (defined directly in `settings.json`) fires whenever Claude writes or edits `.claude/handoff.md`. It sends the content to a fast model with a checklist: current task, key decisions, files touched, open questions, next steps. If anything's missing or too vague, it returns `{"decision": "block", "reason": "..."}` and Claude rewrites it before the turn ends.

## Drift detection — recency-weighted, self-correcting, loop- and thrash-aware, fact-checked, and graduated

The first version counted corrections and tool failures cumulatively for the whole session and warned once, forever, with a binary trigger. This version is built out on six fronts:

1. **Recency-weighted, not cumulative.** Every signal is tagged with the turn it happened on. The score only looks at the last `window_turns` (default 15) turns — old drift from early in a long session stops mattering once you've moved past it.
2. **Self-correcting.** User messages that read as affirmations ("perfect", "that works now", "thanks") score *negative* weight, pulling the score back down.
3. **Loop detection.** A `PreToolUse` hook tracks recent tool-call signatures. If Claude tries the *exact same action* 3+ times in a row, that's scored *and* Claude gets an immediate nudge via `additionalContext`.
4. **Claude's own hedging counts too.** `drift-check.sh` reads `last_assistant_message` and scores genuine self-doubt ("let me try a different approach," "I may have made a mistake") — narrowly enough that ordinary technical hedging ("this might not work on slower connections") does **not** false-positive.
5. **Thrashing.** A new `track-file-changes.sh` hook records every real file touched and which turn it happened on. If too many turns (`thrash_turns_threshold`, default 6) pass with tool activity but no actual file progress, that's scored as drift too — catching a session spinning its wheels even when nobody's complained and nothing's technically failed. It's guarded to never fire on a session that never touched any files in the first place (pure conversation isn't "thrashing").
6. **Fact-checked handoffs.** A new `verify-handoff-facts.sh` hook deterministically (no LLM call) cross-checks that `handoff.md` actually mentions at least one file from the *real* touched-files list for the session. A fluent-sounding but generic handoff that doesn't reference anything actually changed gets blocked with the specific mismatch — a ground-truth complement to the LLM "does this sound complete" check.

All of this is centralized in two shared files instead of being duplicated across scripts:

| File | Role |
|---|---|
| `drift-config.json` | Every tunable number in one place: window size, cooldowns, threshold, soft-warning ratio, per-signal weights. Tune once, every hook and the statusline stay in sync. |
| `drift_lib.py` | Shared scoring logic (load config/state, compute windowed score, correction/positive/self-doubt regexes). Imported by every drift-related hook and by the statusline. |

| Hook | Event | What it does |
|---|---|---|
| `track-corrections.sh` | `UserPromptSubmit` | Advances the turn counter. Scores `+correction` or `-positive` weight based on the message content. |
| `track-tool-failures.sh` | `PostToolUseFailure` | Scores `+failure` weight at the current turn. |
| `loop-detector.sh` | `PreToolUse` (`Bash\|Edit\|Write\|MultiEdit`) | Tracks recent tool-call signatures; scores `+loop` (once per contiguous repeat) and nudges Claude directly. |
| `track-file-changes.sh` | `PostToolUse` (`Write\|Edit\|MultiEdit`) | Records every real file touched (excluding `handoff.md` itself) and the turn of the last real change. Feeds both thrash detection and the fact-check hook. |
| `verify-handoff-facts.sh` | `PostToolUse` (scoped to `handoff.md` writes) | Deterministic ground-truth check: blocks if `handoff.md` doesn't mention any file actually touched this session. Skips the check entirely if no files were touched yet. |
| `drift-check.sh` | `Stop` | Scores `+self_doubt` from Claude's own `last_assistant_message` and `+thrash` if progress has stalled, then computes the windowed score and picks a response tier (see below). |
| `session-state-cleanup.sh` | `SessionEnd` | Deletes the session's state file. |

### Graduated response — three tiers, not one binary trigger

- **Statusline** (always visible): the live score, updating every turn — see below.
- **Soft tier** (`score >= threshold * soft_warning_ratio`, default 60%): a quiet `systemMessage` visible to you only. Doesn't block Claude, doesn't force a handoff — just surfaces the trend early. Has its own shorter cooldown (`soft_cooldown_turns`) so it can repeat more often than the hard tier.
- **Hard tier** (`score >= threshold`): blocks the stop once, instructs Claude to flag it, write a handoff, and suggest `/clear`. Re-arms after `cooldown_turns` if drift recurs.

### Tuning it

Everything lives in `drift-config.json`:

```json
{
  "window_turns": 15,
  "cooldown_turns": 10,
  "threshold": 4.0,
  "loop_repeat_count": 3,
  "loop_lookback": 6,
  "thrash_turns_threshold": 6,
  "soft_warning_ratio": 0.6,
  "soft_cooldown_turns": 5,
  "max_touched_files": 25,
  "weights": {
    "correction": 1.5,
    "failure": 1.0,
    "loop": 2.5,
    "positive": -2.0,
    "self_doubt": 1.0,
    "thrash": 2.0
  }
}
```

- Lower `threshold` or raise the weights for earlier/more sensitive warnings.
- Raise `window_turns` if you want drift to persist longer before "aging out."
- Raise `cooldown_turns` / `soft_cooldown_turns` if either tier is firing too often.
- Raise `thrash_turns_threshold` if legitimate slow/thoughtful stretches (planning, research) are getting flagged.
- Add your team's actual phrasing to `CORRECTION_RE` / `POSITIVE_RE` / `SELF_DOUBT_RE` in `drift_lib.py`.

After any tuning change, run the test suite (see below) before trusting it in a real session.

### Optional stronger version (semantic, costs a small LLM call)

The regex-based signals can miss drift that doesn't use an obvious phrase (e.g. Claude quietly contradicting an earlier decision in a way that doesn't hedge). Claude Code supports a `"type": "prompt"` hook for semantic yes/no classification instead, addable as an extra `Stop` handler — costs one extra small-model call per turn, so it's opt-in:

```json
{
  "type": "prompt",
  "prompt": "Given this Claude Code turn: $ARGUMENTS\n\nDoes the assistant's response contradict something it said earlier in this session, repeat an already-tried failed approach, or ignore explicit user correction? Answer only \"yes\" or \"no\".",
  "model": "claude-haiku-4-5-20251001"
}
```

## Automated test suite

`.claude/tests/test_drift.py` runs every hook as a real subprocess against an isolated temp project directory and asserts the expected output — 22 checks covering every signal, the loop/thrash dedup logic, both fact-check outcomes, and all three response tiers.

```bash
.claude/run-tests.sh
```

Run this after any change to `drift-config.json`, `drift_lib.py`, or any hook. It's what caught a real bug during development: an early version of the self-doubt regex matched "this might not work well on slower connections" (an ordinary technical caveat), which the test suite's false-positive case flagged immediately.

## Live drift score in the statusline

`.claude/statusline.py` reads the same shared state/config as the hooks (via `drift_lib.py`), so the number you see is exactly the number the Stop hook is comparing against the threshold.

```
[Sonnet 5]  ▓▓▓░░░░░░░ 30%   ● drift 6.0/4 C:1 F:1 L:1 U:1 T:0
```

- Context bar: green <50%, yellow 50-75%, red above.
- Drift dot: green below half the threshold, yellow up to it, red at/over it.
- `6.0/4`: current windowed score vs. threshold.
- `C:n F:n L:n U:n T:n`: correction / failure / loop / self-doubt / thrash counts within the current window.

Test standalone before trusting it:

```bash
echo '{"model":{"display_name":"Sonnet 5"},"workspace":{"project_dir":"'"$(pwd)"'"},"session_id":"test","context_window":{"used_percentage":42}}' | python3 .claude/statusline.py
```

## A known limitation, honestly

This is still pattern-matching plus a weighted sum — not a real judgment of whether the session is actually going well. It can:
- Miss drift that never surfaces as a correction phrase, a tool failure, a literal repeated action, hedging language, or a progress stall (e.g. Claude confidently going down a wrong but "smooth," actively-editing path).
- False-positive on a user who happens to say "that's wrong" about something unrelated to Claude's work.
- The self-doubt and fact-check signals are deliberately narrow/conservative to avoid false alarms — which also means some real drift phrased differently, or a handoff that vaguely references work without naming files, won't be caught. Both trade recall for precision on purpose, since a noisy signal here erodes trust in the whole score faster than a missed one does.
- The fact-check is a simple substring match on file basenames — it can't tell if the *content* of the handoff is accurate, only whether it references real files at all.

Treat the score as a **prompt to look**, not a verdict. The optional semantic `"type": "prompt"` hook above is the way to get closer to real judgment, at the cost of a small LLM call per turn.

## Setup — merging with an existing settings.json

Since your team already has other hooks configured, **don't just drop this `settings.json` in and overwrite theirs.** Merge instead:

1. Copy `.claude/hooks/`, `.claude/statusline.py`, `.claude/drift_lib.py`, and `.claude/drift-config.json` from this pack into your existing `.claude/` folder.
2. Open your existing `.claude/settings.json` and merge in each top-level key from this pack's `settings.json`:
   - Add the `statusLine` key (or merge `drift_indicator()` into a statusline you already have).
   - Add `SessionStart`, `UserPromptSubmit`, `PostToolUseFailure`, `PreCompact`, `Stop`, and `SessionEnd` entries as new array items under `hooks` — additive, so they run alongside whatever's already registered for those events.
   - For `PreToolUse` and `PostToolUse`: if matcher groups already exist for those tool patterns (e.g. for auto-formatting or command blocking), add this pack's handlers into the same group's `hooks` array rather than creating a duplicate group. Either works, but one group is tidier.
3. Make scripts executable:
   ```bash
   chmod +x .claude/hooks/*.sh
   ```
4. Add to `.gitignore`:
   ```
   .claude/handoff.md
   .claude/.handoff-marker
   .claude/.session-state/
   .claude/logs/
   ```
   `settings.json`, `statusline.py`, `drift_lib.py`, `drift-config.json`, and everything in `.claude/hooks/` stay **committed**.
5. Restart Claude Code, or run `/hooks` to confirm everything loaded.
