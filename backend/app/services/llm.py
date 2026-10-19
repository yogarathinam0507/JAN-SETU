"""Provider-neutral LLM adapter. Only used when LLM_PROVIDER, LLM_API_KEY and LLM_MODEL are configured.
API keys stay server-side. Any failure raises LLMError - callers must surface it, never mask it."""
import json

import httpx

from ..config import get_settings


class LLMError(RuntimeError):
    pass


def chat_json(system: str, user: str, timeout: float = 20.0) -> dict:
    s = get_settings()
    if s.ai_mode != "llm":
        raise LLMError("No LLM provider configured")
    if s.llm_provider != "openai_compatible":
        raise LLMError(f"Unsupported LLM provider '{s.llm_provider}'")
    url = s.llm_base_url.rstrip("/") + "/chat/completions"
    try:
        resp = httpx.post(url, timeout=timeout, headers={"Authorization": f"Bearer {s.llm_api_key}"}, json={
            "model": s.llm_model, "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise LLMError(f"LLM request failed: {type(exc).__name__}") from exc


def generate_text(system: str, user: str, timeout: float = 30.0) -> str:
    s = get_settings()
    if s.ai_mode != "llm":
        raise LLMError("No LLM provider configured")
    url = s.llm_base_url.rstrip("/") + "/chat/completions"
    try:
        resp = httpx.post(url, timeout=timeout, headers={"Authorization": f"Bearer {s.llm_api_key}"}, json={
            "model": s.llm_model, "temperature": 0.2,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise LLMError(f"LLM request failed: {type(exc).__name__}") from exc
