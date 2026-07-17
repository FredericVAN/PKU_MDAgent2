"""Context-window management for the agent loop: summarize, don't truncate.

Mature agent harnesses (this very assistant's own context handling, and
Claude Code's auto-compact) do not discard old messages once the transcript
gets long - that silently destroys facts the model may still need (what was
already tried, why a previous attempt failed, the original task wording).
Instead, once the transcript crosses a size budget, everything except the
most recent turns is replaced by an LLM-written summary that explicitly
preserves the concrete facts that matter, and the loop continues on the
shortened history. This module only fires when that budget is actually
crossed - a short run never touches it.
"""

import json

# Rough token estimate: ~4 characters per token. Deliberately not tied to a
# provider-specific tokenizer (Qwen/OpenAI/Kimi all differ) - it only needs
# to be the right order of magnitude to trigger compaction comfortably
# before a real context-length error, not to be exact.
_CHARS_PER_TOKEN = 4


def estimate_tokens(messages: list) -> int:
    total_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    return total_chars // _CHARS_PER_TOKEN


def _turn_start_indices(messages: list) -> list:
    """Indices where a new turn begins - the only places it is safe to cut.
    Index 1 (the first user message, right after the system prompt) and
    every later assistant message start a new turn; the tool messages
    answering an assistant's tool_calls must always stay attached to it, so
    they are never a valid cut point."""
    if len(messages) <= 1:
        return []
    return [1] + [i for i, m in enumerate(messages) if i > 1 and m.get("role") == "assistant"]


_SUMMARY_PROMPT = """You are compacting the transcript of an in-progress LAMMPS-script-writing agent so it can keep working with less context.

Read the conversation excerpt below and write a concise but complete summary that a fresh reader could use to continue the task without seeing the original transcript. You MUST preserve, if present:
- The original user task/goal, restated in full.
- The current LAMMPS script's key parameters (element/potential, ensemble, box size, run length) - not the whole script text.
- Every check or run that was attempted, its outcome, and any errors encountered (so they are not blindly retried).
- The latest evaluate() score/reward and its main criticisms, if evaluate was called.
- What has NOT been tried yet / what the natural next step is.

Do not include filler commentary. Output plain text - a few short paragraphs or a bullet list, no markdown headers.

--- transcript to summarize ---
{transcript}
--- end transcript ---
"""


def _flatten(message: dict) -> str:
    if message.get("content"):
        return f"[{message.get('role')}] {message['content']}"
    if message.get("tool_calls"):
        calls = ", ".join(f"{c['function']['name']}({c['function']['arguments']})" for c in message["tool_calls"])
        return f"[assistant called tools: {calls}]"
    return f"[{message.get('role')}] {json.dumps(message, ensure_ascii=False)}"


def _summarize(messages_to_summarize: list, summarizer) -> str:
    transcript = "\n".join(_flatten(m) for m in messages_to_summarize)
    prompt = _SUMMARY_PROMPT.format(transcript=transcript[-20000:])
    resp = summarizer.chat([{"role": "user", "content": prompt}])
    return (resp.content or "").strip()


def summarize_and_compact(messages: list, summarizer, max_tokens: int, keep_last_turns: int = 2) -> list:
    """If `messages` is over `max_tokens`, replace everything but the system
    prompt and the last `keep_last_turns` turns with an LLM-written summary.
    Returns `messages` unchanged if under budget, or if there are not yet
    enough turns to safely compact."""
    if estimate_tokens(messages) <= max_tokens:
        return messages

    turn_starts = _turn_start_indices(messages)
    if len(turn_starts) <= keep_last_turns:
        return messages  # nothing old enough to compact yet

    cut_index = turn_starts[-keep_last_turns]
    to_summarize = messages[1:cut_index]
    if not to_summarize:
        return messages

    summary_text = _summarize(to_summarize, summarizer)
    summary_message = {
        "role": "user",
        "content": (
            "(Earlier progress on this task was compacted to save context. "
            "This summary replaces the raw transcript - it is not new "
            "information, just a shorter restatement of what already "
            "happened. Continue the task from here.)\n\n" + summary_text
        ),
    }
    return [messages[0], summary_message, *messages[cut_index:]]
