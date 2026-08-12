from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Literal


class AccessibilityNudgeType(str, Enum):
    TEXT_ALTERNATIVE = "text-alternative"
    SEMANTIC_RELATIONSHIP = "semantic-relationship"
    HEADING = "heading"
    ACCESSIBLE_NAME = "accessible-name"
    STATUS_MESSAGE = "status-message"
    ERROR_IDENTIFICATION = "error-identification"
    ERROR_SUGGESTION = "error-suggestion"
    LABELS_OR_INSTRUCTIONS = "labels-or-instructions"


ValuesResolver = Callable[[Any, Any | None], list[str] | None]


@dataclass(frozen=True)
class AccessibilityAnnotation:
    sc: str
    type: AccessibilityNudgeType
    message: str
    values_resolver: ValuesResolver | None = None


@dataclass(frozen=True)
class LinkDefinition:
    href: str
    rel: str
    type: Literal["GET", "POST"]
    label: str
    accessibility: tuple[AccessibilityAnnotation, ...] = ()


def current_value_list(value: Any, _: Any | None = None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        values = [str(item) for item in value if item is not None]
        return values or None
    return [str(value)]


def sibling_field_values(field_name: str) -> ValuesResolver:
    def resolve(_: Any, context: Any | None) -> list[str] | None:
        if context is None:
            return None
        return current_value_list(getattr(context, field_name, None), context)

    return resolve


def child_field_values(field_name: str) -> ValuesResolver:
    def resolve(value: Any, _: Any | None) -> list[str] | None:
        if not isinstance(value, list):
            return None
        values = [str(getattr(item, field_name)) for item in value if getattr(item, field_name, None) is not None]
        return values or None

    return resolve
