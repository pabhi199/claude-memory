import sys
import json
import os
import re

project_dir = sys.argv[1]
sys.path.insert(0, os.path.join(project_dir, ".claude"))
import drift_lib as dl  # noqa: E402

data = json.load(sys.stdin)
session_id = data.get("session_id", "unknown")

state = dl.load_state(project_dir, session_id)
touched_files = state.get("touched_files", [])

# Nothing to fact-check against (e.g. handoff written before any real edits
# happened this session) -- don't manufacture a false alarm.
if not touched_files:
    sys.exit(0)

handoff_path = os.path.join(project_dir, ".claude", "handoff.md")
if not os.path.exists(handoff_path):
    sys.exit(0)

with open(handoff_path) as f:
    handoff_content = f.read()

handoff_lower = handoff_content.lower()


def basename(path):
    return re.split(r"[\\/]", path)[-1]


mentioned = [
    tf for tf in touched_files
    if basename(tf).lower() in handoff_lower
]

if not mentioned:
    file_list = ", ".join(basename(tf) for tf in touched_files[-10:])
    reason = (
        f"This handoff doesn't mention any of the files actually touched this "
        f"session ({file_list}). A handoff that doesn't reference real file "
        f"changes is a sign it may be too generic or inaccurate to be useful. "
        f"Please revise it to reflect what was actually changed."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
