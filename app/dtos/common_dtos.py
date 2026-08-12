from typing import Literal

from pydantic import BaseModel

from app.accessibility import AccessibilityNudgeType, HttpMethod


class LinkDTO(BaseModel):
    href: str
    rel: str
    type: HttpMethod
    label: str


class AccessibilityNudgeDTO(BaseModel):
    success_criterion: str
    level: Literal["A", "AA", "AAA"]
    target: list[str]
    type: AccessibilityNudgeType
    message: str
    values: list[str] | None = None
    details: str


class AccessibilityDTO(BaseModel):
    standard: str
    nudges: list[AccessibilityNudgeDTO]
