import json
from json import JSONDecodeError
from typing import Any, Mapping
from urllib.parse import urlparse

from flowmate.agent.llm_client import LLMClientConfig, LLMProviderError
from flowmate.schemas import LLMPlanResponse


DEEPSEEK_MAX_TOKENS = 8192


class OpenAILLMClient:
    def __init__(
        self,
        config: LLMClientConfig,
        sdk_client: Any | None = None,
    ) -> None:
        self.config = config

        if sdk_client is not None:
            self._client = sdk_client
            return

        try:
            from openai import OpenAI
        except Exception as exc:
            raise LLMProviderError(
                "OpenAI SDK is not installed.",
                stage="provider_client_initialization",
                error_type="provider_transport_error",
            ) from exc

        client_kwargs: dict[str, str] = {"api_key": config.api_key}
        if config.base_url:
            client_kwargs["base_url"] = config.base_url

        self._client = OpenAI(**client_kwargs)

    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        if self._is_deepseek_endpoint():
            return self._generate_deepseek_json_plan(user_input, system_prompt)

        try:
            response = self._client.responses.parse(
                model=self.config.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                text_format=LLMPlanResponse,
            )
        except Exception as exc:
            raise LLMProviderError(
                "OpenAI plan generation request failed.",
                stage="provider_request",
                error_type="provider_transport_error",
            ) from exc

        try:
            parsed = response.output_parsed
            if parsed is None:
                raise ValueError("OpenAI response did not include parsed structured output.")

            return parsed.model_dump(mode="json")
        except Exception as exc:
            raise LLMProviderError(
                "OpenAI structured response parsing failed at response_extraction stage.",
                stage="response_extraction",
                error_type="provider_parse_error",
            ) from exc

    def _is_deepseek_endpoint(self) -> bool:
        hostname = urlparse(self.config.base_url).hostname or ""
        return hostname == "api.deepseek.com" or hostname.endswith(".deepseek.com")

    def _generate_deepseek_json_plan(
        self,
        user_input: str,
        system_prompt: str,
    ) -> Mapping[str, Any]:
        try:
            response = self._client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                response_format={"type": "json_object"},
                max_tokens=DEEPSEEK_MAX_TOKENS,
            )
        except Exception as exc:
            raise LLMProviderError(
                "DeepSeek plan generation request failed.",
                stage="provider_request",
                error_type="provider_transport_error",
            ) from exc

        content = self._extract_deepseek_content(response)
        json_text = self._normalize_json_content(content)
        return self._decode_json_object(json_text)

    def _extract_deepseek_content(self, response: Any) -> str:
        try:
            choice = response.choices[0]
            content = choice.message.content
        except Exception as exc:
            raise LLMProviderError(
                "DeepSeek response extraction failed at response_extraction stage.",
                stage="response_extraction",
                error_type="provider_parse_error",
            ) from exc

        finish_reason = getattr(choice, "finish_reason", None)
        if content is None:
            self._raise_deepseek_empty_content(finish_reason)
        if not isinstance(content, str):
            raise LLMProviderError(
                "DeepSeek response content was not text.",
                stage="response_extraction",
                error_type="provider_parse_error",
            )
        if not content.strip():
            self._raise_deepseek_empty_content(finish_reason)

        return content

    def _raise_deepseek_empty_content(self, finish_reason: Any) -> None:
        if finish_reason == "length":
            raise LLMProviderError(
                "DeepSeek response content was empty because the provider hit the output token limit.",
                stage="response_extraction",
                error_type="provider_empty_output",
            )
        raise LLMProviderError(
            "DeepSeek response content was empty.",
            stage="response_extraction",
            error_type="provider_empty_output",
        )

    def _normalize_json_content(self, content: str) -> str:
        text = content.strip()
        lines = text.splitlines()
        if len(lines) >= 2 and lines[0].strip().startswith("```"):
            closing_line = lines[-1].strip()
            if closing_line == "```":
                text = "\n".join(lines[1:-1]).strip()

        if not text:
            raise LLMProviderError(
                "DeepSeek response content was empty after JSON extraction.",
                stage="response_extraction",
                error_type="provider_empty_output",
            )

        return text

    def _decode_json_object(self, content: str) -> Mapping[str, Any]:
        try:
            parsed = json.loads(content)
        except JSONDecodeError as exc:
            raise LLMProviderError(
                "DeepSeek response parsing failed at json_decode stage.",
                stage="json_decode",
                error_type="provider_invalid_json",
            ) from exc

        if not isinstance(parsed, Mapping):
            raise LLMProviderError(
                "DeepSeek JSON parsing failed at json_decode stage: output must be an object.",
                stage="json_decode",
                error_type="provider_parse_error",
            )

        return parsed
