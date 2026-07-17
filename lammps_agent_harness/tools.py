"""Tool implementations for the LAMMPS agent harness - framework-free.

Generic capabilities (write_file/read_file/list_files/run_shell_command)
mirror the primitives a real coding agent gets (Claude Code's own
Write/Read/Glob/Bash): the agent decides how to invoke LAMMPS and what to
inspect afterward, instead of a bespoke run_simulation wrapper pre-parsing
everything for it. Only two tools stay domain-specific, because they do
real work a generic primitive can't replace:
- check_potentials: searches/downloads/fuzzy-matches potential files -
  logic, not just an OS command.
- evaluate: needs a second, independent judge-model call.

Each tool is a plain Python function plus a hand-written JSON schema in the
`{"type": "function", "function": {...}}` shape shared by OpenAI, DashScope
(Tongyi/Qwen), Moonshot/Kimi, and most other function-calling APIs.
harness.py dispatches a model's tool_calls straight against the dict
returned by build_tool_functions() - there is no Tool class, no framework
registry, just a name -> callable lookup.
"""

import os
import subprocess
from dataclasses import dataclass, field

import json_repair

from prompt import lammps_evaluator_system_prompt
from utils.common_utils import cal_reward, extract_jsonstr_from_outputstr
from utils.lammps_potential_tools import check_lammps_potentials_tool

MAX_FILE_CHARS = 8000
MAX_SHELL_OUTPUT_CHARS = 8000
DEFAULT_SHELL_TIMEOUT = 30


@dataclass
class AgentSession:
    """Mutable state for a single agent run, shared by every tool call."""

    generate_dir: str
    abs_generate_dir: str
    user_input: str = ""
    eval_result: dict = None
    final_score: float = 0
    reward: float = 0
    finished: bool = False
    finish_summary: str = ""
    # Filenames the agent itself created via write_file - used to tell input
    # files (the script) apart from output files (log/dump, produced by
    # actually running LAMMPS) without guessing from naming conventions.
    written_files: set = field(default_factory=set)


def classify_files(session: "AgentSession") -> tuple:
    """Split the sandbox's current file listing into (input_files,
    output_files): input = written by the agent via write_file, output =
    everything else (i.e. produced by run_shell_command)."""
    all_files = set(os.listdir(session.generate_dir))
    input_files = sorted(all_files & session.written_files)
    output_files = sorted(all_files - session.written_files)
    return input_files, output_files


def _truncate(text: str, max_chars: int = MAX_FILE_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return f"{text[:half]}\n...\n[truncated {len(text) - max_chars} characters]\n...\n{text[-half:]}"


def _resolve_in_sandbox(session: "AgentSession", filename: str) -> str:
    """Resolve `filename` inside session.generate_dir, rejecting any path
    that would escape it (e.g. `../../secrets.txt`)."""
    base = os.path.abspath(session.generate_dir)
    target = os.path.abspath(os.path.join(base, filename))
    if os.path.commonpath([base, target]) != base:
        raise ValueError(f"Path escapes the sandboxed working directory: {filename}")
    return target


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write (or overwrite) a file inside your sandboxed working directory - e.g. the "
                "LAMMPS input script itself. Paths are relative to that directory; you cannot "
                "write outside it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Relative path, e.g. \"in.lammps\"."},
                    "content": {"type": "string", "description": "Full file content to write."},
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file from your sandboxed working directory - e.g. a log or dump file "
                "produced by run_shell_command. Long files are truncated (head + tail shown)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Relative path to read."},
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List every file currently in your sandboxed working directory.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell_command",
            "description": (
                "Run a shell command inside your sandboxed working directory (cwd is set for "
                "you) and get back its stdout+stderr and exit code. Use this to invoke LAMMPS "
                "itself, e.g. `lmp -in in.lammps -log log.lammps`. A short timeout is fine for a "
                "quick syntax/startup check; give a longer one for a real run."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run."},
                    "timeout_seconds": {
                        "type": "integer",
                        "description": f"Kill the command after this many seconds (default {DEFAULT_SHELL_TIMEOUT}).",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_potentials",
            "description": (
                "Check whether every interatomic potential file referenced by a script (the "
                "potentials/... paths in its pair_coeff lines) is actually available, and "
                "attempt to fetch/recommend substitutes for any that are missing. Give it the "
                "filename of a script you already wrote with write_file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "The script file to check, e.g. \"in.lammps\"."},
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate",
            "description": (
                "Ask an independent judge model to score a script and its run log against the "
                "original task. Give it filenames you already wrote/produced - it reads them "
                "itself. Call this once you have a run you believe succeeded, to check whether "
                "it is good enough to finish."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "script_filename": {"type": "string", "description": "The LAMMPS script file to evaluate."},
                    "log_filename": {
                        "type": "string",
                        "description": "The run's log/output file, if any (optional - static-only review if omitted).",
                    },
                },
                "required": ["script_filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": (
                "Call this exactly once, when you are done: either the script runs well and "
                "scored acceptably, or you have made a reasonable number of attempts and "
                "further iteration is not converging."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "1-3 sentence recap of the final outcome."},
                },
                "required": ["summary"],
            },
        },
    },
]


def build_tool_functions(session: AgentSession, judge_llm) -> dict:
    """Return {tool_name: callable(**kwargs) -> str}, bound to this run's session."""

    def write_file(filename: str, content: str) -> str:
        path = _resolve_in_sandbox(session, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        session.written_files.add(filename)
        return f"Wrote {len(content)} characters to {filename}."

    def read_file(filename: str) -> str:
        path = _resolve_in_sandbox(session, filename)
        if not os.path.isfile(path):
            return f"No such file: {filename}. Files present: {os.listdir(session.generate_dir)}"
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return _truncate(f.read())

    def list_files() -> str:
        entries = os.listdir(session.generate_dir)
        return "\n".join(entries) if entries else "(empty)"

    def run_shell_command(command: str, timeout_seconds: int = DEFAULT_SHELL_TIMEOUT) -> str:
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=session.generate_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=timeout_seconds,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            return f"exit_code={proc.returncode}\n{_truncate(output, MAX_SHELL_OUTPUT_CHARS)}"
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout_seconds}s (it may still be running in the background)."
        except Exception as e:
            return f"Failed to run command: {e}"

    def check_potentials(filename: str) -> str:
        path = _resolve_in_sandbox(session, filename)
        if not os.path.isfile(path):
            return f"No such file: {filename}. Write the script with write_file first."
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            script = f.read()
        result = check_lammps_potentials_tool(script, top_k=10)
        return f"all_ready={result.get('all_ready', False)}. {result.get('message', '')}"

    def evaluate(script_filename: str, log_filename: str = "") -> str:
        script_path = _resolve_in_sandbox(session, script_filename)
        if not os.path.isfile(script_path):
            return f"No such script file: {script_filename}."
        with open(script_path, "r", encoding="utf-8", errors="ignore") as f:
            script = f.read()

        run_result = "(no log file given - static review only)"
        if log_filename:
            log_path = _resolve_in_sandbox(session, log_filename)
            if os.path.isfile(log_path):
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    run_result = _truncate(f.read(), 10000)
            else:
                run_result = f"(log file {log_filename} not found)"

        eval_prompt = f"""{lammps_evaluator_system_prompt}
        # Input
        ## user_input:
        {session.user_input}

        ## lammps_code:
        {script}

        ## run_result:
        {run_result}
        """
        eval_msg = judge_llm.chat([{"role": "user", "content": eval_prompt}])
        raw_content = (eval_msg.content or "").strip()
        try:
            content = extract_jsonstr_from_outputstr(raw_content)
            score_obj = json_repair.loads(content)
            # The evaluator prompt nests scores under "score_summary"; fall back
            # to a flat lookup in case a model emits them at the top level.
            summary = score_obj.get("score_summary", score_obj)
            module_score = summary.get("module_score", 0)
            penalty_score = summary.get("penalty_score", 0)
            session.final_score = summary.get("final_score", 0)
            session.reward = cal_reward(module_score, penalty_score)
            session.eval_result = score_obj
            return (
                f"final_score={session.final_score}, reward={session.reward:.3f}\n"
                f"comment={score_obj.get('final_comment', '')}"
            )
        except Exception as e:
            return f"Evaluation response could not be parsed: {e}\nraw response: {raw_content[:2000]}"

    def finish(summary: str) -> str:
        session.finished = True
        session.finish_summary = summary
        return "Session marked finished."

    return {
        "write_file": write_file,
        "read_file": read_file,
        "list_files": list_files,
        "run_shell_command": run_shell_command,
        "check_potentials": check_potentials,
        "evaluate": evaluate,
        "finish": finish,
    }
