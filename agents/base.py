"""Shared helpers for building Band agents.

Two kinds of agent in this project:
  - LLM agents (Intake, Matcher, Approver) -> LangGraph adapter + a chat model.
    The adapter hands the Band platform tools (send_message, etc.) to a ReAct
    agent, so the model itself decides to call send_message to hand off.
  - The security crew (Warden, Enforcer) -> no LLM, see warden/ (SimpleAdapter).
"""

import os
from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver


def make_llm(provider: str = "aiml", model: str | None = None, temperature: float = 0.0):
    """Return a chat model. Both providers are OpenAI-compatible, so we use the
    same ChatOpenAI client and only swap base_url + key + model name."""
    if provider == "featherless":
        return ChatOpenAI(
            model=model or os.getenv("FEATHERLESS_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
            api_key=os.getenv("FEATHERLESS_API_KEY"),
            base_url=os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"),
            temperature=temperature,
        )
    return ChatOpenAI(
        model=model or os.getenv("AIML_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("AIML_API_KEY"),
        base_url=os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1"),
        temperature=temperature,
    )


def make_langgraph_agent(env_prefix: str, system_prompt: str,
                         provider: str = "aiml", model: str | None = None) -> Agent:
    """Build an LLM-backed Band agent. `env_prefix` picks the keys from .env,
    e.g. 'INTAKE' reads INTAKE_AGENT_ID / INTAKE_API_KEY."""
    adapter = LangGraphAdapter(
        llm=make_llm(provider, model),
        checkpointer=InMemorySaver(),
        custom_section=system_prompt,
    )
    return Agent.create(
        adapter=adapter,
        agent_id=os.environ[f"{env_prefix}_AGENT_ID"],
        api_key=os.environ[f"{env_prefix}_API_KEY"],
        ws_url=os.getenv("THENVOI_WS_URL"),
        rest_url=os.getenv("THENVOI_REST_URL"),
    )
