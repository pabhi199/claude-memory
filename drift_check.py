import sys
import json
import os

project_dir = sys.argv[1]
sys.path.insert(0, os.path.join(project_dir, ".claude"))
import drift_lib as dl  # noqa: E402

data = json.load(sys.stdin)
session_id = data.get("session_id", "unknown")
last_assistant_message = data.get("last_assistant_message", "") or ""

config = dl.load_config(project_dir)
state = dl.load_state(project_dir, session_id)
turn = state["turn"]
state_dirty = False

# --- Signal 1: Claude's own hedging/self-doubt in its last response ---------
# Runs sequentially inside this one Stop hook (not a separate parallel hook)
# since same-event hooks race on the same state file.
if dl.SELF_DOUBT_RE.search(last_assistant_message):
    state["events"].append({"turn": turn, "weight": config["weights"]["self_doubt"], "type": "self_doubt"})
    state_dirty = True

# --- Signal 2: thrashing -- turns passing with no real file progress -------
# track-file-changes.sh updates last_file_change_turn whenever a real file
# (not handoff.md) gets written or edited. If too many turns have passed
# since the last real change, that's a sign of spinning without progress --
# regardless of whether anyone's corrected Claude or a tool has failed.
turns_since_progress = turn - state.get("last_file_change_turn", 0)
thrash_threshold = config.get("thrash_turns_threshold", 6)
has_touched_files = bool(state.get("touched_files"))
if turn > 0 and has_touched_files and turns_since_progress >= thrash_threshold:
    # Only score once per stretch -- re-check against the same
    # last_file_change_turn value so it doesn't re-fire every single Stop
    # while the drought continues.
    if state.get("thrash_flagged_for") != state.get("last_file_change_turn", 0):
        state["thrash_flagged_for"] = state.get("last_file_change_turn", 0)
        state["events"].append({"turn": turn, "weight": config["weights"]["thrash"], "type": "thrash"})
        state_dirty = True

if state_dirty:
    dl.prune_events(state, config["window_turns"])
    dl.save_state(project_dir, session_id, state)

# --- Compute windowed score and decide the response tier -------------------
score, counts = dl.window_score(state, config)
threshold = config["threshold"]
cooldown_ok = (turn - state.get("last_warned_turn", -9999)) >= config["cooldown_turns"]
soft_cooldown_ok = (turn - state.get("soft_warned_turn", -9999)) >= config.get("soft_cooldown_turns", 5)
soft_threshold = threshold * config.get("soft_warning_ratio", 0.6)

breakdown = (
    f"{counts['correction']} correction(s), {counts['failure']} tool failure(s), "
    f"{counts['loop']} repeated-action loop(s), {counts['self_doubt']} self-doubt signal(s), "
    f"{counts['thrash']} thrash signal(s)"
)

if score >= threshold and cooldown_ok:
    # HARD tier: block the stop, make Claude actually do something about it.
    state["last_warned_turn"] = turn
    dl.save_state(project_dir, session_id, state)

    reason = (
        f"Drift score is {score:.1f} (threshold {threshold:g}) over the last "
        f"{config['window_turns']} turns: {breakdown}. "
        f"Before finishing this reply: (1) briefly and honestly flag this to the user, "
        f"(2) write a concise handoff to .claude/handoff.md (current task, decisions made, "
        f"files touched, open questions, next steps), and (3) suggest they run /clear and "
        f"say 'continue from handoff' to start a fresh, more focused session."
    )
    print(json.dumps({"decision": "block", "reason": reason}))

elif score >= soft_threshold and soft_cooldown_ok:
    # SOFT tier: a quiet nudge visible to the user only. Doesn't block Claude,
    # doesn't force a handoff -- just surfaces the trend before it's serious.
    state["soft_warned_turn"] = turn
    dl.save_state(project_dir, session_id, state)

    print(json.dumps({
        "systemMessage": (
            f"Drift score climbing: {score:.1f}/{threshold:g} ({breakdown}). "
            f"Not urgent yet, but worth keeping an eye on."
        )
    }))

