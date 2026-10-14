from dataclasses import dataclass
from time import sleep
from typing import Any, Mapping

from flowmate.agent.llm_client import LLMClient, LLMProviderError


RETRYABLE_PROVIDER_ERROR_TYPES = {
    "provider_transport_error",
    "provider_empty_output",
    "provider_invalid_json",
    "provider_parse_error",
}


@dataclass(frozen=True)
class RetryCallMetadata:
    attempt_count: int = 0
    retry_performed: bool = False
    first_provider_error_type: str | None = None
    final_provider_error_type: str | None = None


class RetryPolicy:
    def __init__(
        self,
        retryable_error_types: set[str] | None = None,
    ) -> None:
        self.retryable_error_types = retryable_error_types or RETRYABLE_PROVIDER_ERROR_TYPES

    def is_retryable(self, error: Exception) -> bool:
        return (
            isinstance(error, LLMProviderError)
            and error.error_type in self.retryable_error_types
        )


class RetryingLLMClient:
    def __init__(
        self,
        inner_client: LLMClient,
        *,
        max_attempts: int = 2,
        retry_policy: RetryPolicy | None = None,
        retry_delay_seconds: float = 0,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")

        self.inner_client = inner_client
        self.max_attempts = max_attempts
        self.retry_policy = retry_policy or RetryPolicy()
        self.retry_delay_seconds = retry_delay_seconds
        self.last_call_metadata = RetryCallMetadata()

    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        first_provider_error_type: str | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                output = self.inner_client.generate_plan(user_input, system_prompt)
            except Exception as exc:
                if isinstance(exc, LLMProviderError) and first_provider_error_type is None:
                    first_provider_error_type = exc.error_type

                should_retry = (
                    attempt < self.max_attempts
                    and self.retry_policy.is_retryable(exc)
                )
                if should_retry:
                    self.last_call_metadata = RetryCallMetadata(
                        attempt_count=attempt,
                        retry_performed=True,
                        first_provider_error_type=first_provider_error_type,
                        final_provider_error_type=exc.error_type
                        if isinstance(exc, LLMProviderError)
                        else None,
                    )
                    if self.retry_delay_seconds > 0:
                        sleep(self.retry_delay_seconds)
                    continue

                self.last_call_metadata = RetryCallMetadata(
                    attempt_count=attempt,
                    retry_performed=attempt > 1,
                    first_provider_error_type=first_provider_error_type,
                    final_provider_error_type=exc.error_type
                    if isinstance(exc, LLMProviderError)
                    else None,
                )
                raise

            self.last_call_metadata = RetryCallMetadata(
                attempt_count=attempt,
                retry_performed=attempt > 1,
                first_provider_error_type=first_provider_error_type,
                final_provider_error_type=None,
            )
            return output

        raise RuntimeError("Retry loop exited unexpectedly.")
