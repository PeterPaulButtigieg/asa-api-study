from typing import Literal

from pydantic import BaseModel


class LinkDTO(BaseModel):
    href: str
    rel: str
    type: Literal["GET", "POST"]

class AccessibilityDTO(BaseModel):
    sc: str
    content: str
    level: Literal["A", "AA", "AAA"]
    href: str
    applies_to: list[str]
