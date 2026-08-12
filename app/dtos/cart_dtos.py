from typing import Annotated

from pydantic import BaseModel, Field

from app.accessibility import AccessibilityAnnotation, AccessibilityNudgeType, child_field_values
from app.dtos.common_dtos import AccessibilityDTO, LinkDTO


class CartItemInDTO(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=5)


class CartItemDTO(BaseModel):
    product_id: int
    product_name: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)
    line_total: float = Field(ge=0)
    currency: str


class CartDataDTO(BaseModel):
    id: str
    items: Annotated[
        list[CartItemDTO],
        AccessibilityAnnotation(
            sc="1.3.1",
            type=AccessibilityNudgeType.SEMANTIC_RELATIONSHIP,
            message="Present cart items as a semantic list or table with quantities and totals programmatically associated.",
            values_resolver=child_field_values("product_name"),
        ),
    ]
    item_count: int = Field(ge=0)
    total: float = Field(ge=0)
    currency: str


class CartResponseDTO(BaseModel):
    data: CartDataDTO
    links: list[LinkDTO]
    accessibility: AccessibilityDTO | None = None
