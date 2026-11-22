"""LLM providers behind one interface: mock (default, used in CI), OpenAI, Gemini.

Calls go through plain HTTPS with httpx, so there is no SDK to pin. Only ids,
timings and status codes are logged, never prompts, responses or keys.
"""

import json
import logging
import time
from typing import Protocol

import httpx

from regdiff_ai.llm.prompt import INPUT_MARKER
from regdiff_common.config import Settings, get_settings
from regdiff_common.logging import log_event

log = logging.getLogger(__name__)

DEFAULT_MODELS = {"openai": "gpt-4o-mini", "gemini": "gemini-3.5-flash"}
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
HTTP_ATTEMPTS = 2  # per call; assess() adds one more validated attempt, then falls back


class LLMError(Exception):
    pass


class LLMClient(Protocol):
    name: str

    def complete_json(self, system: str, user: str) -> str: ...


class MockLLM:
    """Deterministic stand-in that answers from the input JSON, citing real evidence ids."""

    name = "mock"

    def complete_json(self, system: str, user: str) -> str:
        data = json.loads(user.split(INPUT_MARKER, 1)[1])
        change, evidence = data["change"], data["evidence"]
        ids_by_role: dict[str, list[str]] = {}
        for item in evidence:
            ids_by_role.setdefault(item["role"], []).append(item["id"])
        change_ids = ids_by_role.get("old_clause", []) + ids_by_role.get("new_clause", [])
        change_ids = change_ids or [evidence[0]["id"]]

        differences = "; ".join(
            f"{d['kind']} {', '.join(d['old']) or '-'} -> {', '.join(d['new']) or '-'}"
            for d in change["deterministic_differences"]
        )
        summary = f"Clause {change['clause']} of {change['regulation']} is {change['change_type'].replace('_', ' ')}"
        summary += f" ({differences})." if differences else "."

        affected, actions = [], []
        for candidate in data["candidate_affected_items"]:
            cited = candidate["evidence_ids"] or change_ids
            affected.append(
                {
                    "item": candidate["id"],
                    "reason": f"{candidate['label']} is linked to clause {change['clause']} ({candidate['relation']}).",
                    "evidence_ids": cited,
                }
            )
            actions.append(
                {
                    "action": f"Review {candidate['label']} against the new clause text.",
                    "evidence_ids": change_ids + cited,
                }
            )
        if not actions:
            actions.append(
                {"action": "Confirm whether any internal policy relies on this clause.", "evidence_ids": change_ids}
            )

        return json.dumps(
            {
                "change_summary": summary,
                "summary_evidence_ids": change_ids,
                "affected": affected,
                "potential_impact": [
                    {
                        "statement": "Processes that rely on the previous clause text may need to be updated.",
                        "evidence_ids": change_ids,
                    }
                ],
                "recommended_actions": actions,
            }
        )


class _HttpLLM:
    provider = ""

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise LLMError(f"LLM_MODE={self.provider} needs LLM_API_KEY")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model or DEFAULT_MODELS[self.provider]
        self.name = f"{self.provider}:{self.model}"
        self.client = httpx.Client(timeout=settings.llm_timeout_seconds)

    def complete_json(self, system: str, user: str) -> str:
        last_error: Exception | None = None
        for attempt in range(1, HTTP_ATTEMPTS + 1):
            started = time.perf_counter()
            try:
                response = self._post(system, user)
                duration_ms = round((time.perf_counter() - started) * 1000)
                log_event(
                    log,
                    "llm_call",
                    provider=self.provider,
                    model=self.model,
                    attempt=attempt,
                    status=response.status_code,
                    duration_ms=duration_ms,
                )
                if response.status_code in RETRYABLE_STATUS:
                    raise LLMError(f"{self.provider} returned HTTP {response.status_code}")
                response.raise_for_status()
                return self._extract(response.json())
            except (httpx.TransportError, LLMError) as exc:
                last_error = exc
                if attempt < HTTP_ATTEMPTS:
                    time.sleep(2 * attempt)
            except httpx.HTTPStatusError as exc:
                raise LLMError(f"{self.provider} rejected the request: HTTP {exc.response.status_code}") from exc
        raise LLMError(f"{self.provider} failed after retries: {last_error}")

    def _post(self, system: str, user: str) -> httpx.Response:
        raise NotImplementedError

    def _extract(self, body: dict) -> str:
        raise NotImplementedError


class OpenAILLM(_HttpLLM):
    provider = "openai"

    def _post(self, system: str, user: str) -> httpx.Response:
        return self.client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
        )

    def _extract(self, body: dict) -> str:
        return body["choices"][0]["message"]["content"]


class GeminiLLM(_HttpLLM):
    provider = "gemini"

    def _post(self, system: str, user: str) -> httpx.Response:
        return self.client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            headers={"x-goog-api-key": self.api_key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
            },
        )

    def _extract(self, body: dict) -> str:
        return body["candidates"][0]["content"]["parts"][0]["text"]


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    if settings.llm_mode == "openai":
        return OpenAILLM(settings)
    if settings.llm_mode == "gemini":
        return GeminiLLM(settings)
    return MockLLM()
