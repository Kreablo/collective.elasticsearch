
from collective.elasticsearch import logger
from elastic_transport import NdjsonSerializer
from elastic_transport import JsonSerializer
from typing import Any
from abc import ABC, abstractmethod


class HasDefault(ABC):
    """Serialization classes with a default method."""

    @abstractmethod
    def default(self, obj: Any) -> str:
        pass

class ExtendedDefault(HasDefault):
    """Additional datatype serialization support."""

    def default(self, obj: Any) -> str:
        if isinstance(obj, set):
            return [x for x in obj]
        return super().default(obj)


class ExtendedJsonSerializer(ExtendedDefault, JsonSerializer):
    """Extend serialzation with additional json serialization."""


class ExtendedNdjsonSerializer(ExtendedDefault, NdjsonSerializer):
    """Extend serialization with additional data type support."""
