import os
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable


class LLMClientConfigurationError(Exception):
    pass


class LLMProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        stage: str = "provider_request",
        error_type: str = "provider_transport_error",
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.error_type = error_type


@runtime_checkable
class LLMClient(Protocol):
    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True)
class LLMClientConfig:
    api_key: str
    model: str
    base_url: str

    @classmethod
    def from_env(cls) -> "LLMClientConfig":
        api_key = os.getenv("LLM_API_KEY")
        model = os.getenv("LLM_MODEL")
        base_url = os.getenv("LLM_BASE_URL", "")

        missing = [
            name
            for name, value in {
                "LLM_API_KEY": api_key,
                "LLM_MODEL": model,
            }.items()
            if not value
        ]

        if missing:
            raise LLMClientConfigurationError(
                f"Missing LLM configuration: {', '.join(missing)}"
            )

        return cls(api_key=api_key, model=model, base_url=base_url)
