"""Minimal, framework-free LLM client for the agent harness.

Deliberately does not use LangChain. Every provider this project cares about
(DashScope/Tongyi-Qwen, OpenAI, Moonshot/Kimi, DeepSeek, Ollama) now exposes
an OpenAI-compatible Chat Completions endpoint, so a single thin wrapper
around the `openai` SDK - used purely as an HTTP client - covers all of them.
There is no provider-abstraction layer to fight with: the wire format is
just "list of {role, content, ...} dicts in, one message dict out."
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# provider -> (default base_url, api_key env var or None if no key needed)
_PROVIDER_DEFAULTS = {
    "dashscope": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "tongyi": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),  # alias, matches LammpsAgents_by_langgraph.py's provider name
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
}


class LLMClient:
    """A (provider, model) pair that speaks Chat Completions directly."""

    def __init__(self, provider: str, model: str):
        if provider not in _PROVIDER_DEFAULTS:
            raise ValueError(f"Unsupported provider: {provider!r}. Known: {list(_PROVIDER_DEFAULTS)}")
        default_base_url, key_env = _PROVIDER_DEFAULTS[provider]
        base_url = os.getenv("OPENAI_API_BASE") if provider == "openai" else None
        base_url = base_url or default_base_url
        api_key = os.getenv(key_env) if key_env else None
        if key_env and not api_key:
            raise RuntimeError(f"Missing {key_env} in the environment - required for provider={provider!r}.")

        self.provider = provider
        self.model = model
        self._client = OpenAI(api_key=api_key or "not-needed", base_url=base_url)

    def chat(self, messages: list, tools: list | None = None):
        """One Chat Completions call. Returns the response message object
        (has .content, .tool_calls, and .model_dump() for re-appending to
        the conversation)."""
        extra_body = {}
        if self.provider in ("dashscope", "tongyi"):
            # DashScope's Qwen3 models default "thinking mode" on, which that
            # endpoint rejects for non-streaming calls unless explicitly disabled.
            extra_body["enable_thinking"] = False
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto" if tools else None,
            extra_body=extra_body or None,
        )
        return resp.choices[0].message


def build_llm(role: str) -> LLMClient:
    """role: 'code' or 'judge'. Reads CODE_LLM_PROVIDER/CODE_LLM_MODEL or
    JUDGE_LLM_PROVIDER/JUDGE_LLM_MODEL - the same env vars
    LammpsAgents_by_langgraph.py uses - so both versions share one config
    story even though this one never imports LangChain."""
    prefix = "CODE" if role == "code" else "JUDGE"
    default_model = "qwen3-8b" if role == "code" else "qwen-flash"
    provider = os.getenv(f"{prefix}_LLM_PROVIDER", "tongyi")
    model = os.getenv(f"{prefix}_LLM_MODEL", default_model)
    return LLMClient(provider=provider, model=model)
