"""
Automated test suite for the drift-detection system.

Runs every hook as a real subprocess (exactly how Claude Code invokes it),
against an isolated temporary project directory, and asserts the expected
JSON output / state changes. This exists so a threshold or regex tweak in
drift-config.json or drift_lib.py can be verified in seconds instead of
manually replaying scenarios by hand every time.

Run with: python3 .claude/tests/test_drift.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

PACK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .claude/
HOOKS_DIR = os.path.join(PACK_ROOT, "hooks")

results = []


def check(label, condition):
    results.append((label, bool(condition)))
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}")


class TempProject:
    """A throwaway project dir with just drift_lib.py + drift-config.json,
    so hook scripts' `sys.path.insert(..., .claude)` / `import drift_lib`
    resolves exactly like it would in a real project."""

    def __enter__(self):
        self.dir = tempfile.mkdtemp()
        claude_dir = os.path.join(self.dir, ".claude")
        os.makedirs(claude_dir)
        shutil.copy(os.path.join(PACK_ROOT, "drift_lib.py"), claude_dir)
        shutil.copy(os.path.join(PACK_ROOT, "drift-config.json"), claude_dir)
        return self.dir

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)


def run_hook(script_name, project_dir, stdin_obj):
    proc = subprocess.run(
        [sys.executable, os.path.join(HOOKS_DIR, script_name), project_dir],
        input=json.dumps(stdin_obj),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"  !! {script_name} exited {proc.returncode}: {proc.stderr}")
    out = proc.stdout.strip()
    return json.loads(out) if out else None


def read_state(project_dir, session_id):
    path = os.path.join(project_dir, ".claude", ".session-state", f"{session_id}.json")
    return json.load(open(path)) if os.path.exists(path) else None


def write_handoff(project_dir, content):
    with open(os.path.join(project_dir, ".claude", "handoff.md"), "w") as f:
        f.write(content)


# ---------------------------------------------------------------------------
print("\n=== track_corrections.py ===")
with TempProject() as proj:
    sid = "s1"
    run_hook("track_corrections.py", proj, {"session_id": sid, "prompt": "add a login button"})
    state = read_state(proj, sid)
    check("turn advances to 1 on first prompt", state["turn"] == 1)
    check("no event for neutral prompt", state["events"] == [])

    run_hook("track_corrections.py", proj, {"session_id": sid, "prompt": "that's wrong, I already told you"})
    state = read_state(proj, sid)
    check("correction phrase scores a correction event", any(e["type"] == "correction" for e in state["events"]))

    run_hook("track_corrections.py", proj, {"session_id": sid, "prompt": "perfect, that works now, thanks"})
    state = read_state(proj, sid)
    check("positive phrase scores a positive event", any(e["type"] == "positive" for e in state["events"]))

# ---------------------------------------------------------------------------
print("\n=== track_tool_failures.py ===")
with TempProject() as proj:
    sid = "s2"
    run_hook("track_tool_failures.py", proj, {"session_id": sid})
    state = read_state(proj, sid)
    check("failure event recorded", any(e["type"] == "failure" for e in state["events"]))

# ---------------------------------------------------------------------------
print("\n=== loop_detector.py ===")
with TempProject() as proj:
    sid = "s3"
    call = {"session_id": sid, "tool_name": "Bash", "tool_input": {"command": "npm test"}}
    out1 = run_hook("loop_detector.py", proj, call)
    out2 = run_hook("loop_detector.py", proj, call)
    out3 = run_hook("loop_detector.py", proj, call)
    check("no loop flagged before 3rd repeat", out1 is None and out2 is None)
    check("loop flagged on 3rd identical call", out3 is not None and "additionalContext" in out3["hookSpecificOutput"])
    state = read_state(proj, sid)
    check("exactly one loop event recorded (deduped)", sum(1 for e in state["events"] if e["type"] == "loop") == 1)

    out4 = run_hook("loop_detector.py", proj, call)
    check("4th identical call doesn't add a 2nd loop event", out4 is None)

# ---------------------------------------------------------------------------
print("\n=== track_file_changes.py ===")
with TempProject() as proj:
    sid = "s4"
    run_hook("track_corrections.py", proj, {"session_id": sid, "prompt": "start"})  # turn -> 1
    run_hook("track_file_changes.py", proj, {"session_id": sid, "tool_input": {"file_path": "src/auth.py"}})
    state = read_state(proj, sid)
    check("real file recorded in touched_files", "src/auth.py" in state["touched_files"])
    check("last_file_change_turn updated", state["last_file_change_turn"] == 1)

    run_hook("track_file_changes.py", proj, {"session_id": sid, "tool_input": {"file_path": ".claude/handoff.md"}})
    state = read_state(proj, sid)
    check("handoff.md itself is excluded from touched_files", ".claude/handoff.md" not in state["touched_files"])

# ---------------------------------------------------------------------------
print("\n=== verify_handoff_facts.py ===")
with TempProject() as proj:
    sid = "s5"
    run_hook("track_corrections.py", proj, {"session_id": sid, "prompt": "start"})
    run_hook("track_file_changes.py", proj, {"session_id": sid, "tool_input": {"file_path": "src/jwt_auth.py"}})

    write_handoff(proj, "# Handoff\nRefactored the login flow. No files mentioned specifically here.")
    out = run_hook("verify_handoff_facts.py", proj, {"session_id": sid})
    check("blocks when handoff mentions none of the touched files", out is not None and out.get("decision") == "block")

    write_handoff(proj, "# Handoff\nUpdated jwt_auth.py to fix token refresh.")
    out = run_hook("verify_handoff_facts.py", proj, {"session_id": sid})
    check("passes when handoff mentions an actually-touched file", out is None)

with TempProject() as proj:
    sid = "s5b"
    write_handoff(proj, "# Handoff\nSomething vague.")
    out = run_hook("verify_handoff_facts.py", proj, {"session_id": sid})
    check("skips fact-check when no files were touched yet (nothing to compare)", out is None)

# ---------------------------------------------------------------------------
print("\n=== drift_check.py: self-doubt signal (true/false positives) ===")
with TempProject() as proj:
    sid = "s6"
    run_hook("track_corrections.py", proj, {"session_id": sid, "prompt": "x"})
    run_hook("drift_check.py", proj, {
        "session_id": sid,
        "last_assistant_message": "This might not work well on slower connections.",
    })
    state = read_state(proj, sid)
    check("ordinary hedging about the system is NOT scored as self-doubt",
          not any(e["type"] == "self_doubt" for e in state["events"]))

with TempProject() as proj:
    sid = "s7"
    run_hook("track_corrections.py", proj, {"session_id": sid, "prompt": "x"})
    run_hook("drift_check.py", proj, {
        "session_id": sid,
        "last_assistant_message": "Let me try a different approach since that did not work.",
    })
    state = read_state(proj, sid)
    check("genuine self-doubt about Claude's own attempt IS scored",
          any(e["type"] == "self_doubt" for e in state["events"]))

# ---------------------------------------------------------------------------
print("\n=== drift_check.py: thrash detection ===")
with TempProject() as proj:
    sid = "s8"
    # One real file change, then many turns with no further progress.
    run_hook("track_corrections.py", proj, {"session_id": sid, "prompt": "start"})
    run_hook("track_file_changes.py", proj, {"session_id": sid, "tool_input": {"file_path": "a.py"}})
    for _ in range(7):
        run_hook("track_corrections.py", proj, {"session_id": sid, "prompt": "still working on it"})
    run_hook("drift_check.py", proj, {"session_id": sid})
    state = read_state(proj, sid)
    check("thrash event recorded after turns pass with no file progress",
          any(e["type"] == "thrash" for e in state["events"]))

with TempProject() as proj:
    sid = "s9"
    # Never touched any files -- pure conversation, should NOT thrash-flag.
    for _ in range(8):
        run_hook("track_corrections.py", proj, {"session_id": sid, "prompt": "let's discuss the plan"})
    run_hook("drift_check.py", proj, {"session_id": sid})
    state = read_state(proj, sid)
    check("no thrash flag for a session that never touched any files",
          not any(e["type"] == "thrash" for e in state["events"]))

# ---------------------------------------------------------------------------
print("\n=== drift_check.py: graduated response tiers ===")
with TempProject() as proj:
    sid = "s10"
    run_hook("track_corrections.py", proj, {"session_id": sid, "prompt": "that's wrong, I already told you"})
    run_hook("track_tool_failures.py", proj, {"session_id": sid})
    # correction (1.5) + failure (1.0) = 2.5, which is >= soft threshold (4.0
    # * 0.6 = 2.4) but well below full threshold (4.0).
    out = run_hook("drift_check.py", proj, {"session_id": sid})
    check("soft tier fires a systemMessage (not a block) below full threshold",
          out is not None and "systemMessage" in out and "decision" not in out)

with TempProject() as proj:
    sid = "s11"
    run_hook("track_corrections.py", proj, {"session_id": sid, "prompt": "that's wrong, I already told you"})
    call = {"session_id": sid, "tool_name": "Bash", "tool_input": {"command": "npm test"}}
    for _ in range(3):
        run_hook("loop_detector.py", proj, call)
    run_hook("track_tool_failures.py", proj, {"session_id": sid})
    out = run_hook("drift_check.py", proj, {"session_id": sid})
    check("hard tier blocks once score exceeds full threshold", out is not None and out.get("decision") == "block")

    out2 = run_hook("drift_check.py", proj, {"session_id": sid})
    check("immediate re-check is suppressed by cooldown", out2 is None or out2.get("decision") != "block")

# ---------------------------------------------------------------------------
print(f"\n{'=' * 40}")
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"{passed}/{total} passed")
if passed != total:
    print("\nFAILED:")
    for label, ok in results:
        if not ok:
            print(f"  - {label}")
    sys.exit(1)
