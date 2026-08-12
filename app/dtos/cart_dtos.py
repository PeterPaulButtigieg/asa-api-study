from typing import Annotated

from pydantic import BaseModel, Field

from app.accessibility import (
    AccessibilityAnnotation,
    AccessibilityNudgeType,
    ValidationAnnotation,
    child_field_values,
    link_label_targets,
)
from app.dtos.common_dtos import AccessibilityDTO, LinkDTO


CartProductId = Annotated[int, ValidationAnnotation(suggestion="Use a product ID returned by GET /api/v1/products.")]
CartQuantity = Annotated[
    int,
    Field(ge=1, le=5),
    ValidationAnnotation(suggestion="Enter a whole number within the allowed range."),
]


class CartItemInDTO(BaseModel):
    product_id: CartProductId
    quantity: CartQuantity


class CartItemUpdateDTO(BaseModel):
    quantity: CartQuantity


class CartItemDTO(BaseModel):
    product_id: int
    product_name: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)
    line_total: float = Field(ge=0)
    currency: str
    links: Annotated[
        list[LinkDTO],
        AccessibilityAnnotation(
            sc="4.1.2",
            type=AccessibilityNudgeType.ACCESSIBLE_NAME,
            message="Use the link or button label as the accessible name of each cart-item action control.",
            values_resolver=child_field_values("label"),
            targets_resolver=link_label_targets,
        ),
    ]


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
