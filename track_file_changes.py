import sys
import json
import os

project_dir = sys.argv[1]
sys.path.insert(0, os.path.join(project_dir, ".claude"))
import drift_lib as dl  # noqa: E402

data = json.load(sys.stdin)
session_id = data.get("session_id", "unknown")
tool_input = data.get("tool_input", {})
file_path = tool_input.get("file_path", "")

# The handoff file itself doesn't count as "progress" -- writing it is what
# happens *when* a session is stuck (triggered by drift-check or precompact),
# so counting it would mask the very thing we're trying to detect.
if file_path.endswith("handoff.md"):
    sys.exit(0)

if not file_path:
    sys.exit(0)

config = dl.load_config(project_dir)
state = dl.load_state(project_dir, session_id)
turn = state["turn"]

touched = state.get("touched_files", [])
if file_path not in touched:
    touched.append(file_path)
max_files = config.get("max_touched_files", 25)
state["touched_files"] = touched[-max_files:]

state["last_file_change_turn"] = turn

dl.prune_events(state, config["window_turns"])
dl.save_state(project_dir, session_id, state)
