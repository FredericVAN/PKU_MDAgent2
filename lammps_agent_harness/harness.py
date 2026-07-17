"""Agent-harness rewrite of LammpsAgents_by_langgraph.py - framework-free.

The original module encodes the whole workflow as a fixed LangGraph
StateGraph: node_init -> node_generate -> node_check_potentials ->
node_check_syntax -> node_run -> node_eval, wired together by hand-written
decide_syntax_next / decide_potentials_next / decide_next functions. The LLM
only ever fills in content at those fixed points - every branch (retry on
syntax error, retry on missing potential, when to stop) is decided by code,
not by the model.

This module follows the "harness + loop" style actual coding agents (e.g.
Claude Code) are built with: a thin loop that calls the model, executes
whichever tool(s) it asks for (see tools.py), feeds the results back as
plain `{"role": "tool", ...}` messages, and repeats. No agent framework is
used - just the `openai` SDK as an HTTP client (see llm_client.py) talking
Chat Completions wire format directly to whatever OpenAI-compatible endpoint
is configured (DashScope/Tongyi, OpenAI, Moonshot/Kimi, Ollama, ...). The
model decides the order of operations and when to stop (by calling the
`finish` tool); the harness only enforces a hard step budget as a safety
net. Nothing about the original file is touched - this is a standalone dev
version living in its own package.
"""

import json
import os
import shutil

from lammps_agent_harness.context import estimate_tokens, summarize_and_compact
from lammps_agent_harness.llm_client import build_llm
from lammps_agent_harness.prompts import build_system_prompt
from lammps_agent_harness.tools import TOOL_SCHEMAS, AgentSession, build_tool_functions
from utils.common_utils import generate_random_dirname
from utils.log_utils import log_to_file

LOG_FILE = "lammps_dev.log"
MAX_STEPS = 12

# Conservative on purpose: this is a budget to compact *before* a real
# context-length error, not an attempt to model any particular provider's
# actual window size. Tune up if your model comfortably fits more.
MAX_CONTEXT_TOKENS = 12000
KEEP_LAST_TURNS = 2


def log(msg: str) -> None:
    print(msg)
    log_to_file(msg, LOG_FILE)


def _new_session(user_input: str) -> AgentSession:
    generate_dir = generate_random_dirname()
    os.makedirs(generate_dir, exist_ok=True)
    return AgentSession(
        generate_dir=generate_dir,
        abs_generate_dir=os.path.abspath(generate_dir),
        user_input=user_input,
    )


def _compact(messages: list, summarizer) -> tuple:
    """Summarize-and-compact if the transcript has grown past budget.
    Returns (messages, event) where event is None if nothing changed."""
    before = len(messages)
    messages = summarize_and_compact(messages, summarizer, MAX_CONTEXT_TOKENS, KEEP_LAST_TURNS)
    if len(messages) == before:
        return messages, None
    event = f"compacted transcript: {before} -> {len(messages)} messages (~{estimate_tokens(messages)} tokens now)"
    return messages, event


def _dispatch(tool_functions: dict, name: str, args_json: str) -> str:
    fn = tool_functions.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        args = json.loads(args_json) if args_json else {}
    except json.JSONDecodeError as e:
        return f"Could not parse arguments for {name}: {e}"
    try:
        return fn(**args)
    except Exception as e:
        return f"Tool '{name}' raised an error: {e}"


def run_lammps_agent(user_input: str, is_delete_dir: bool = False, max_steps: int = MAX_STEPS) -> AgentSession:
    """Run the tool-calling agent loop for one task and return the final session state."""
    session = _new_session(user_input)
    code_llm = build_llm("code")
    judge_llm = build_llm("judge")
    tool_functions = build_tool_functions(session, judge_llm)

    messages = [
        {"role": "system", "content": build_system_prompt(session.generate_dir)},
        {"role": "user", "content": user_input},
    ]

    for step in range(1, max_steps + 1):
        log(f"--- step {step}/{max_steps} ---")
        msg = code_llm.chat(messages, tools=TOOL_SCHEMAS)
        messages.append(msg.model_dump(exclude_none=True))

        if msg.content:
            log(f"[assistant] {msg.content}")

        if not msg.tool_calls:
            log("Model responded without calling a tool; stopping.")
            break

        for call in msg.tool_calls:
            result = _dispatch(tool_functions, call.function.name, call.function.arguments)
            log(f"[tool call] {call.function.name}({call.function.arguments}) -> {result}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})

        if session.finished:
            log(f"Agent called finish(): {session.finish_summary}")
            break

        messages, compact_event = _compact(messages, judge_llm)
        if compact_event:
            log(f"[context] {compact_event}")
    else:
        session.finish_summary = session.finish_summary or "Step budget exhausted without an explicit finish() call."
        log(session.finish_summary)

    if is_delete_dir:
        shutil.rmtree(session.generate_dir, ignore_errors=True)

    return session


def run_lammps_agent_stream(user_input: str, max_steps: int = MAX_STEPS):
    """Generator variant of run_lammps_agent: yields one event dict per model
    turn / tool call, in the same spirit as
    LammpsAgents_by_langgraph.workflow.stream(), so this harness can be
    dropped into app.py's streaming endpoint later without redesigning the
    event shape from scratch."""
    session = _new_session(user_input)
    code_llm = build_llm("code")
    judge_llm = build_llm("judge")
    tool_functions = build_tool_functions(session, judge_llm)

    messages = [
        {"role": "system", "content": build_system_prompt(session.generate_dir)},
        {"role": "user", "content": user_input},
    ]

    def session_snapshot() -> dict:
        return {
            "files": os.listdir(session.generate_dir),
            "eval_result": session.eval_result,
            "final_score": session.final_score,
            "reward": session.reward,
            "generate_dir": session.generate_dir,
            "abs_generate_dir": session.abs_generate_dir,
        }

    for step in range(1, max_steps + 1):
        msg = code_llm.chat(messages, tools=TOOL_SCHEMAS)
        messages.append(msg.model_dump(exclude_none=True))

        if msg.content:
            yield {"type": "assistant", "step": step, "message": msg.content}

        if not msg.tool_calls:
            yield {"type": "done", "step": step, "reason": "model stopped calling tools"}
            return

        for call in msg.tool_calls:
            result = _dispatch(tool_functions, call.function.name, call.function.arguments)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})
            yield {
                "type": "tool_call",
                "step": step,
                "tool": call.function.name,
                "args": call.function.arguments,
                "result": str(result),
                "state": session_snapshot(),
            }

        if session.finished:
            yield {"type": "done", "step": step, "reason": session.finish_summary}
            return

        messages, compact_event = _compact(messages, judge_llm)
        if compact_event:
            yield {"type": "context_compacted", "step": step, "reason": compact_event}

    yield {"type": "done", "step": max_steps, "reason": "step budget exhausted"}


if __name__ == "__main__":
    test_task = (
        "Generate LAMMPS code to simulate the thermal expansion coefficient "
        "change of copper at 300K under NPT conditions, and output its volume "
        "change data."
    )
    final_session = run_lammps_agent(test_task, is_delete_dir=False)
    print("finished:", final_session.finished, "| summary:", final_session.finish_summary)
    print("final_score:", final_session.final_score, "| reward:", final_session.reward)
    print("generate_dir:", final_session.generate_dir)
