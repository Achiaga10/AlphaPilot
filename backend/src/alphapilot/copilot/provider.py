from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class CopilotProviderError(RuntimeError):
    code = "AI_PROVIDER_UNAVAILABLE"


class CopilotResponseInvalid(RuntimeError):
    code = "AI_RESPONSE_INVALID"


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    answer: str
    grounding_status: str
    fact_refs: tuple[str, ...]


class LLMProvider(Protocol):
    name: str
    model: str

    async def generate(
        self, *, question: str, system_policy: str, facts: dict[str, Any]
    ) -> ProviderResponse: ...

    async def available(self) -> bool: ...


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def available(self) -> bool:
        if not self.model:
            return False
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self.transport
            ) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.is_success
        except httpx.HTTPError:
            return False

    async def generate(
        self, *, question: str, system_policy: str, facts: dict[str, Any]
    ) -> ProviderResponse:
        if not self.model:
            raise CopilotProviderError("Ollama model is not configured")
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system_policy},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question_untrusted": question, "alphapilot_facts": facts},
                        default=str,
                        separators=(",", ":"),
                    ),
                },
            ],
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self.transport
            ) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CopilotProviderError("Configured local AI provider is unavailable") from exc
        try:
            content = json.loads(body["message"]["content"])
            answer = content["answer"].strip()
            status = content["grounding_status"]
            refs = tuple(content["fact_refs"])
            if (
                not answer
                or status not in {"GROUNDED", "LIMITED"}
                or not all(isinstance(item, str) for item in refs)
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CopilotResponseInvalid("AI provider returned an invalid response") from exc
        return ProviderResponse(answer, status, refs)


class FakeLLMProvider:
    name = "fake"
    model = "deterministic-test"

    def __init__(self, response: ProviderResponse) -> None:
        self.response = response
        self.last_request: tuple[str, str, dict[str, Any]] | None = None

    async def available(self) -> bool:
        return True

    async def generate(
        self, *, question: str, system_policy: str, facts: dict[str, Any]
    ) -> ProviderResponse:
        self.last_request = (question, system_policy, facts)
        return self.response
