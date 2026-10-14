import pytest

from flowmate.agent import (
    LLMClient,
    LLMClientConfig,
    LLMPlanner,
    LLMProviderError,
    OpenAILLMClient,
    UnsupportedPlanningScenarioError,
)
from flowmate.schemas import LLMPlanResponse


USER_INPUT = "我明天早上八点半要去公司开会，帮我安排一下明早出门。"
SYSTEM_PROMPT = "system prompt with weather_tool and navigation_tool"


def valid_response_model() -> LLMPlanResponse:
    return LLMPlanResponse(
        unsupported=False,
        reason=None,
        plan={
            "goal": "安排明早通勤",
            "risk_level": "LOW",
            "requires_confirmation": False,
            "steps": [
                {
                    "order": 1,
                    "description": "检查明早天气",
                    "tool_name": "weather_tool",
                    "arguments": {"location": "current_city", "date": "tomorrow"},
                },
                {
                    "order": 2,
                    "description": "计算到公司的通勤时间",
                    "tool_name": "navigation_tool",
                    "arguments": {
                        "origin": "home",
                        "destination": "company",
                        "departure_time": "tomorrow morning",
                    },
                },
            ],
        },
    )


def unsupported_response_model() -> LLMPlanResponse:
    return LLMPlanResponse(
        unsupported=True,
        reason="Current tools cannot control smart-home devices.",
        plan=None,
    )


class FakeOpenAIResponse:
    def __init__(self, output_parsed: LLMPlanResponse | None) -> None:
        self.output_parsed = output_parsed


class FakeResponsesResource:
    def __init__(self, output_parsed: LLMPlanResponse | None) -> None:
        self.output_parsed = output_parsed
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return FakeOpenAIResponse(self.output_parsed)


class FakeOpenAISDKClient:
    def __init__(self, output_parsed: LLMPlanResponse | None) -> None:
        self.responses = FakeResponsesResource(output_parsed)


class FakeChatCompletionsResource:
    def __init__(self, content, finish_reason: str = "stop") -> None:
        self.content = content
        self.finish_reason = finish_reason
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type(
            "FakeChatResponse",
            (),
            {
                "choices": [
                    type(
                        "FakeChoice",
                        (),
                        {
                            "finish_reason": self.finish_reason,
                            "message": type(
                                "FakeMessage",
                                (),
                                {"content": self.content},
                            )()
                        },
                    )()
                ]
            },
        )()


class FakeDeepSeekSDKClient:
    def __init__(self, content, finish_reason: str = "stop") -> None:
        self.chat = type(
            "FakeChat",
            (),
            {"completions": FakeChatCompletionsResource(content, finish_reason)},
        )()


class RaisingResponsesResource:
    def parse(self, **kwargs):
        raise RuntimeError("provider unavailable")


class RaisingOpenAISDKClient:
    def __init__(self) -> None:
        self.responses = RaisingResponsesResource()


class RaisingChatCompletionsResource:
    def create(self, **kwargs):
        raise RuntimeError("provider unavailable")


class RaisingDeepSeekSDKClient:
    def __init__(self) -> None:
        self.chat = type(
            "FakeChat",
            (),
            {"completions": RaisingChatCompletionsResource()},
        )()


def create_config() -> LLMClientConfig:
    return LLMClientConfig(
        api_key="test-secret-key",
        model="test-model",
        base_url="",
    )


def test_openai_llm_client_follows_contract():
    client = OpenAILLMClient(create_config(), sdk_client=FakeOpenAISDKClient(valid_response_model()))

    assert isinstance(client, LLMClient)


def test_user_input_is_passed_to_provider():
    sdk_client = FakeOpenAISDKClient(valid_response_model())
    client = OpenAILLMClient(create_config(), sdk_client=sdk_client)

    client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    provider_input = sdk_client.responses.calls[0]["input"]
    assert provider_input[1]["content"] == USER_INPUT


def test_system_prompt_is_passed_to_provider():
    sdk_client = FakeOpenAISDKClient(valid_response_model())
    client = OpenAILLMClient(create_config(), sdk_client=sdk_client)

    client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    provider_input = sdk_client.responses.calls[0]["input"]
    assert provider_input[0]["content"] == SYSTEM_PROMPT


def test_model_uses_configured_llm_model():
    sdk_client = FakeOpenAISDKClient(valid_response_model())
    client = OpenAILLMClient(create_config(), sdk_client=sdk_client)

    client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    assert sdk_client.responses.calls[0]["model"] == "test-model"


def test_valid_structured_output_converts_to_mapping():
    client = OpenAILLMClient(create_config(), sdk_client=FakeOpenAISDKClient(valid_response_model()))

    output = client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    assert output["unsupported"] is False
    assert output["plan"]["steps"][0]["tool_name"] == "weather_tool"


def test_unsupported_output_can_flow_to_llm_planner():
    client = OpenAILLMClient(
        create_config(),
        sdk_client=FakeOpenAISDKClient(unsupported_response_model()),
    )
    planner = LLMPlanner(client)

    with pytest.raises(UnsupportedPlanningScenarioError):
        planner.plan("帮我把客厅灯关掉")


def test_provider_exception_is_wrapped_as_llm_provider_error():
    client = OpenAILLMClient(create_config(), sdk_client=RaisingOpenAISDKClient())

    with pytest.raises(LLMProviderError) as exc_info:
        client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    assert exc_info.value.stage == "provider_request"
    assert exc_info.value.error_type == "provider_transport_error"


def test_api_key_is_not_returned_in_provider_output():
    client = OpenAILLMClient(create_config(), sdk_client=FakeOpenAISDKClient(valid_response_model()))

    output = client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    assert "test-secret-key" not in str(output)


def test_deepseek_endpoint_uses_json_chat_output():
    sdk_client = FakeDeepSeekSDKClient(
        valid_response_model().model_dump_json()
    )
    config = LLMClientConfig(
        api_key="test-secret-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )
    client = OpenAILLMClient(config, sdk_client=sdk_client)

    output = client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    request = sdk_client.chat.completions.calls[0]
    assert request["model"] == "deepseek-v4-flash"
    assert request["response_format"] == {"type": "json_object"}
    assert request["max_tokens"] == 8192
    assert request["messages"][1]["content"] == USER_INPUT
    assert output["plan"]["steps"][0]["tool_name"] == "weather_tool"


def test_deepseek_accepts_json_with_surrounding_whitespace():
    sdk_client = FakeDeepSeekSDKClient(
        f"  \n{valid_response_model().model_dump_json()}\n  "
    )
    config = LLMClientConfig(
        api_key="test-secret-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )
    client = OpenAILLMClient(config, sdk_client=sdk_client)

    output = client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    assert output["unsupported"] is False


def test_deepseek_accepts_json_markdown_code_fence():
    sdk_client = FakeDeepSeekSDKClient(
        f"```json\n{valid_response_model().model_dump_json()}\n```"
    )
    config = LLMClientConfig(
        api_key="test-secret-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )
    client = OpenAILLMClient(config, sdk_client=sdk_client)

    output = client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    assert output["unsupported"] is False


def test_deepseek_empty_content_reports_empty_output():
    sdk_client = FakeDeepSeekSDKClient("")
    config = LLMClientConfig(
        api_key="test-secret-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )
    client = OpenAILLMClient(config, sdk_client=sdk_client)

    with pytest.raises(LLMProviderError) as exc_info:
        client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    assert exc_info.value.stage == "response_extraction"
    assert exc_info.value.error_type == "provider_empty_output"


def test_deepseek_length_limited_empty_content_reports_token_limit():
    sdk_client = FakeDeepSeekSDKClient("", finish_reason="length")
    config = LLMClientConfig(
        api_key="test-secret-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )
    client = OpenAILLMClient(config, sdk_client=sdk_client)

    with pytest.raises(LLMProviderError) as exc_info:
        client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    assert exc_info.value.stage == "response_extraction"
    assert exc_info.value.error_type == "provider_empty_output"
    assert "token limit" in str(exc_info.value)


def test_deepseek_malformed_json_reports_invalid_json():
    sdk_client = FakeDeepSeekSDKClient('{"unsupported": false')
    config = LLMClientConfig(
        api_key="test-secret-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )
    client = OpenAILLMClient(config, sdk_client=sdk_client)

    with pytest.raises(LLMProviderError) as exc_info:
        client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    assert exc_info.value.stage == "json_decode"
    assert exc_info.value.error_type == "provider_invalid_json"


def test_deepseek_non_object_json_reports_parse_error():
    sdk_client = FakeDeepSeekSDKClient("[]")
    config = LLMClientConfig(
        api_key="test-secret-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )
    client = OpenAILLMClient(config, sdk_client=sdk_client)

    with pytest.raises(LLMProviderError) as exc_info:
        client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    assert exc_info.value.stage == "json_decode"
    assert exc_info.value.error_type == "provider_parse_error"


def test_deepseek_provider_exception_reports_transport_error():
    config = LLMClientConfig(
        api_key="test-secret-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )
    client = OpenAILLMClient(config, sdk_client=RaisingDeepSeekSDKClient())

    with pytest.raises(LLMProviderError) as exc_info:
        client.generate_plan(USER_INPUT, SYSTEM_PROMPT)

    assert exc_info.value.stage == "provider_request"
    assert exc_info.value.error_type == "provider_transport_error"


def test_deepseek_unsupported_json_output_is_returned():
    sdk_client = FakeDeepSeekSDKClient(
        unsupported_response_model().model_dump_json()
    )
    config = LLMClientConfig(
        api_key="test-secret-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )
    planner = LLMPlanner(OpenAILLMClient(config, sdk_client=sdk_client))

    with pytest.raises(UnsupportedPlanningScenarioError):
        planner.plan("帮我把客厅灯关掉")
