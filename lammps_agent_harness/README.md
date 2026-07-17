# lammps_agent_harness

> **Work in progress.** This harness is still under active development. Its implementation and interfaces are being continuously modified, tested, and refined, so behavior and file layout may change as testing progresses.

> **Experimental demo.** This harness is a proof-of-concept preview for MDAgent3 — not production code, and not (yet) the officially adopted workflow for this repo. APIs and file layout may change without notice.

A "harness + loop" rewrite of the [`lammps_workflow`](../lammps_workflow) package — a dev/experimental version, standalone in this package. Nothing in `lammps_workflow` or `app.py` was changed; this can be adopted later or left as a reference implementation.

## Why this exists

The original module encodes the whole workflow as a fixed LangGraph `StateGraph`: `init → generate → check_potentials → check_syntax → run → eval`, wired together by hand-written `decide_*_next` functions. The LLM only ever fills in content at those fixed points — every branch (retry on syntax error, retry on missing potential, when to stop) is decided by code, not by the model.

This package follows the style actual coding agents (e.g. Claude Code) are built with instead: a thin loop calls the model, executes whichever tool(s) it asks for, feeds the results back, and repeats until the model itself calls `finish` (or a step budget is hit as a safety net). The model decides the order of operations — the harness doesn't hardcode a workflow graph.

It also doesn't use LangChain. Every provider this project cares about (DashScope/Tongyi-Qwen, OpenAI, Moonshot/Kimi, DeepSeek, Ollama) exposes an OpenAI-compatible Chat Completions endpoint, so `llm_client.py` talks to that wire format directly via the `openai` SDK, used purely as an HTTP client.

## Files

| File | Purpose |
|---|---|
| `llm_client.py` | Minimal provider→endpoint mapping + a `chat()` method. No framework. |
| `tools.py` | Tool implementations: generic `write_file`/`read_file`/`list_files`/`run_shell_command`, plus domain-specific `check_potentials` (real fetch/download logic) and `evaluate` (needs a separate judge-model call). |
| `prompts.py` | System prompt. Tool-calling-native from the start — does **not** reuse `prompt.generate_lammps_script_prompt`'s "return one JSON blob" instruction (see "A prompt lesson" below for why). |
| `context.py` | Context-window management: summarize-and-compact when the transcript crosses a size budget, not a fixed-turn truncation. |
| `recorder.py` | Persists each run's full trajectory + a human-readable trace + a short result record. |
| `harness.py` | The loop itself (`_agent_loop`), plus `run_lammps_agent` (blocking) and `run_lammps_agent_stream` (generator, same event shape as `lammps_workflow.workflow.stream()` so it could be dropped into `app.py`'s SSE endpoint later). |

## Requirements

- `DASHSCOPE_API_KEY` in `.env` (or the equivalent key for whichever provider you configure — see below).
- An actual `lmp` (LAMMPS) executable on `PATH`. **conda-forge's `lammps` package does not support Windows** (confirmed against the official docs — only linux-64/macOS). On Windows, use the [official installer](https://packages.lammps.org/windows.html) (`LAMMPS-64bit-Python-stable.exe` is a good default — Python-bundled, serial, no MPI runtime needed) and add its `bin/` directory to `PATH`. On Linux/macOS, `conda install -c conda-forge lammps` works fine.
- Note: this harness drives LAMMPS via `run_shell_command` (the CLI), not the `lammps` Python bindings — so you do **not** need the `lammps` pip package's bundled `liblammps.dll` to work (it has an unrelated, separate DLL-dependency issue on Windows that this harness sidesteps entirely).

## Recommended default config

```bash
CODE_LLM_PROVIDER=tongyi
CODE_LLM_MODEL=qwen3.6-flash
JUDGE_LLM_PROVIDER=tongyi
JUDGE_LLM_MODEL=qwen3.5-flash
```

These are the same env vars `lammps_workflow` reads, so both versions share one config story.

Why not `qwen3-8b`/`qwen-flash` (the original module's hardcoded defaults)? Querying DashScope's live model list shows those are a superseded generation — `qwen3.5-flash`/`qwen3.6-flash` are current, cheaper per token, and tested here to genuinely self-correct on real LAMMPS errors (see the recorded run below), where `qwen3-8b` got stuck re-emitting the same broken script four times in a row after the identical error. `qwen3.6-flash` for `code_llm` (needs to reason through debugging), `qwen3.5-flash` for `judge_llm` (cheaper, scoring doesn't need as much capability).

To use a different OpenAI-compatible endpoint (Kimi/DeepSeek/OpenAI itself), set `CODE_LLM_PROVIDER=openai`, `OPENAI_API_BASE=<endpoint>`, `OPENAI_API_KEY=<key>`. See `.env-EXAMPLE`.

## Running it

```bash
python -m lammps_agent_harness.harness
```

or from other code:

```python
from lammps_agent_harness import run_lammps_agent

session = run_lammps_agent("Simulate copper's thermal expansion at 300K under NPT.")
print(session.finished, session.final_score, session.reward)
```

Each run is saved under `lammps_agent_harness_runs/<run_id>/`:
- `trajectory.json` — the complete raw message list (system/user/assistant/tool), full fidelity.
- `trace.md` — the same information rendered as a readable step-by-step narrative.
- `result.json` — a short summary (status, score, reward, timing) for listing many runs cheaply.

## A prompt lesson (learned by actually testing, not assumed)

An earlier version of `prompts.py` reused `generate_lammps_script_prompt()` wholesale — including its "return one big JSON blob" instruction — and appended a note telling the model to ignore that and use tools instead. That worked with `qwen3-8b` but broke with `qwen3.6-flash`, which resolved the contradiction the other way: it never called a tool at all, just emitted the JSON as plain text. The fix wasn't a stronger override — it was removing the contradiction at the source. `prompts.py` now restates only the genuinely reusable domain knowledge (potentials path convention, the example potentials list) in a prompt that is tool-calling-native from the start, with no conflicting instruction for a model to resolve one way or the other. Different models will paper over a contradictory prompt differently; don't rely on one model's tolerance for it.

## A validated real run

With the config above, a full task (NVE simulation of an FCC Lennard-Jones system) actually completed end to end:

1. Wrote a script, forgot `mass` → real LAMMPS error → **correctly diagnosed and fixed it**
2. Ran again, got `WARNING: No fixes with time integration, atoms won't move` → **correctly added `fix nve`**
3. Ran again, got `ERROR: Lost atoms` (numerical instability) → **correctly diagnosed and reduced the timestep**
4. Ran clean — log showed total energy stable within a narrow band across all 50 steps (NVE conservation)
5. Called `evaluate` → judge model scored it 29/30, reward 0.975
6. Called `finish` with an accurate summary

Three genuine self-correction cycles against real tool output, not scripted — see `lammps_agent_harness_runs/` for the saved trajectory/trace of a run like this.
