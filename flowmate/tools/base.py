from abc import ABC, abstractmethod
from typing import Any, Generic, Mapping, TypeVar

from pydantic import BaseModel

InputModelT = TypeVar("InputModelT", bound=BaseModel)
ResultModelT = TypeVar("ResultModelT", bound=BaseModel)


class BaseTool(ABC, Generic[InputModelT, ResultModelT]):
    name: str
    description: str
    input_schema: type[InputModelT]

    def run(self, arguments: Mapping[str, Any]) -> ResultModelT:
        validated_input = self.input_schema(**dict(arguments))
        return self.execute(validated_input)

    @abstractmethod
    def execute(self, input_data: InputModelT) -> ResultModelT:
        raise NotImplementedError
