from typing import Literal

from pydantic import BaseModel


class LinkDTO(BaseModel):
    href: str
    rel: str
    type: Literal["GET", "POST"]