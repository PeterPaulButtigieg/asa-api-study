from dataclasses import dataclass
from typing import Mapping, Sequence

from fastapi import HTTPException


@dataclass(frozen=True)
class APIErrorItem:
    field: str
    message: str
    suggestion: str | None = None


class APIException(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str,
        errors: Sequence[APIErrorItem] | None = None,
        headers: Mapping[str, str] | None = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=dict(headers) if headers else None)
        self.errors = tuple(errors or ())
