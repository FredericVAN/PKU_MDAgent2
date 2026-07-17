"""Persist a completed agent run's full trajectory and a readable trace.

Every run gets its own folder under RUNS_DIR (keyed by the same run id as
the run's sandbox working directory, so the two are easy to cross-reference),
containing three files:

- trajectory.json: the raw OpenAI-format message list, verbatim. Full
  fidelity - this is what you'd replay or feed back to the model.
- trace.md: a human-readable, auto-formatted step-by-step narrative (what
  the agent reasoned, which tool it called, what came back) - the same
  information as trajectory.json, laid out for a person to skim.
- result.json: a short summary record (status, score, reward, timing) -
  cheap to list many runs without opening each trajectory.

This directory is separate from the run's sandbox `generate_dir` (which
holds the actual LAMMPS script/log/dump files and may be deleted with
is_delete_dir=True) so the record of what happened survives even when the
working files don't.
"""

import json
import os
import time

RUNS_DIR = "lammps_agent_harness_runs"


def _run_dir(run_id: str) -> str:
    path = os.path.join(RUNS_DIR, run_id)
    os.makedirs(path, exist_ok=True)
    return path


def _render_trace_md(user_input: str, events: list, session) -> str:
    lines = ["# LAMMPS Agent Run Trace", "", f"**Task:** {user_input}", ""]
    current_step = None
    for ev in events:
        step = ev.get("step")
        if ev["type"] != "done" and step != current_step:
            lines.append(f"## Step {step}")
            lines.append("")
            current_step = step

        if ev["type"] == "assistant" and ev.get("message"):
            lines.append("**Agent reasoning:**")
            lines.append("")
            lines.append(ev["message"])
            lines.append("")
        elif ev["type"] == "tool_call":
            lines.append(f"**Tool call:** `{ev['tool']}({ev['args']})`")
            lines.append("")
            lines.append("**Result:**")
            lines.append("```")
            lines.append(str(ev["result"])[:2000])
            lines.append("```")
            lines.append("")
        elif ev["type"] == "context_compacted":
            lines.append(f"*(context compacted: {ev['reason']})*")
            lines.append("")
        elif ev["type"] == "done":
            lines.append("## Outcome")
            lines.append("")
            lines.append(ev["reason"])
            lines.append("")

    reward = session.reward
    reward_str = f"{reward:.3f}" if isinstance(reward, (int, float)) else str(reward)
    lines.append("---")
    lines.append("")
    lines.append(f"- **Finished cleanly:** {session.finished}")
    lines.append(f"- **Final score:** {session.final_score}")
    lines.append(f"- **Reward:** {reward_str}")
    return "\n".join(lines)


def save_run(run_id: str, user_input: str, messages: list, events: list, session) -> str:
    """Write trajectory.json, trace.md, result.json for this run. Returns the run's folder path."""
    run_dir = _run_dir(run_id)

    with open(os.path.join(run_dir, "trajectory.json"), "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    with open(os.path.join(run_dir, "trace.md"), "w", encoding="utf-8") as f:
        f.write(_render_trace_md(user_input, events, session))

    result = {
        "run_id": run_id,
        "user_input": user_input,
        "finished": session.finished,
        "finish_summary": session.finish_summary,
        "final_score": session.final_score,
        "reward": session.reward,
        "eval_result": session.eval_result,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(run_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return run_dir
