---
name: handoff
description: Create or load a timestamped handoff file so a fresh session can continue work exactly where it stopped. Run manually with /handoff create or /handoff load.
disable-model-invocation: true
argument-hint: "[create|load] [file]"
arguments: [mode, file]
---

# Handoff

A handoff is a short briefing for a reader with zero memory of this session. Write it for a capable colleague who has never seen the project.

## Commands

| Command | What happens |
|---|---|
| `/handoff create` | Write a new handoff file |
| `/handoff load` | Load the latest handoff file |
| `/handoff load <file>` | Load that specific file |
| `/handoff` (no argument) | Ask: "Create a new handoff or load the latest one?" Do nothing until the user answers |

This skill runs only when the user types `/handoff`. Never guess the mode from session state or from the user's wording. The mode is `$mode` and the optional file is `$file`. If the mode isn't exactly `create` or `load`, ask.

## Where files live

- **Launch directory** = `${CLAUDE_PROJECT_DIR}`, the folder Claude was invoked in. Claude Code fills this in before the skill is read, and it does not drift. Never use `pwd` or the current shell directory, because that can move during the session (e.g. into `.claude/skills/`).
- **Root**: the git root of the launch directory, from `git -C "${CLAUDE_PROJECT_DIR}" rev-parse --show-toplevel`. If that gives nothing (not a git repo), use the launch directory itself.
- If the launch directory is empty, still shows a `$` placeholder instead of a path, or the root is a skills, temp, or scratchpad directory, stop and ask the user where to put the handoff.
- **Folder** = `<root>/handoffs/`
- Run every command against `<root>`: `git -C "<root>" …` for git, absolute paths for `ls`, and `cd "<root>" && <cmd>` for Verify commands.
- **File name** = `HANDOFF-<YYYYMMDD-HHMMSS>.md`, from `date +%Y%m%d-%H%M%S`

Every create makes a new file; nothing is overwritten. Because names sort by time, the latest handoff is always the last name in alphabetical order.

## Create

1. Get the timestamp with `date +%Y%m%d-%H%M%S`. Create `<root>/handoffs/` if missing.
2. Check real state with `git -C "<root>" status`, `git -C "<root>" branch --show-current`, `git -C "<root>" log --oneline -5`, changed files, and whether tests pass. No git repo? Run `ls -la` on the absolute paths of the key directories and omit Branch/Commit.
3. Write `<root>/handoffs/HANDOFF-<timestamp>.md` with this template. Skip empty sections except Next steps.

```markdown
# Handoff: <task>
Created: <YYYY-MM-DD HH:MM:SS> · Branch: <branch> · Commit: <sha>

## Goal
<What "done" looks like, 1–3 sentences>

## Status
<One line>. Not verified: <anything not re-checked, or "none">

## Done
- <item + file paths>

## Next steps
1. <Concrete action you could start immediately>

## Decisions
- <decision> — <why>

## Dead ends
- <what was tried> — <why it failed>

## Key files
- `path` — <why it matters>

## Verify
- `<command>` — <expected result>

## How the user works
- <working-style cues only, e.g. says "next" to advance; nothing personal>

## Blockers / gotchas
- <open questions, env quirks, required env var names>
```

Rules:
- Be specific: paths, commands, exact errors.
- Always give the *why* for decisions.
- Keep it under ~100 lines.
- Never write secrets, only their names.
- Reference only files that will still exist. Copy anything from temp or scratchpad directories into the project, or say it's gone.
- Write facts, not the conversation.

4. Reply with exactly: the file path, the one-line status, and the first next step. If `handoffs/` isn't in `.gitignore`, mention it once so the user can choose to ignore or commit it.

## Load

1. **Pick the file.**
   - `<file>` given → load that file. A relative name is resolved against `<root>/handoffs/`; an absolute path is used as given. Never resolve it against the shell's current directory. If it doesn't exist, say so and stop.
   - No file given → list `<root>/handoffs/HANDOFF-*.md`, sort by name, take the last one.
   - None found → reply "No handoff found in `<root>/handoffs/`." and stop. Don't search elsewhere or create one.
2. **Say which file was loaded** (path and its timestamp) in the first line of the reply.
3. **Check it against reality:** branch/commit via `git -C "<root>"` if git, that key files exist (absolute paths under `<root>`), and run the Verify command with `cd "<root>" && <cmd>` if it's cheap and read-only. Flag anything stale or missing.
4. **Summarize** goal, status, and the first next step in a few lines. Then ask before acting. If the user replies "next", "yes", or "go", do that first step.
5. Don't retry anything under "Dead ends" without a new reason.
