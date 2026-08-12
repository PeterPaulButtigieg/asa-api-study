from typing import Annotated

from pydantic import BaseModel, Field

from app.accessibility import (
    AccessibilityAnnotation,
    AccessibilityNudgeType,
    current_value_list,
    sibling_field_values,
)
from app.dtos.common_dtos import AccessibilityDTO, LinkDTO


class ProductSummaryDTO(BaseModel):
    id: int
    name: Annotated[
        str,
        AccessibilityAnnotation(
            sc="2.4.6",
            type=AccessibilityNudgeType.HEADING,
            message="Use the product name as a clear visible label or heading for the product listing item.",
            values_resolver=current_value_list,
        ),
    ]
    description: str
    price: float = Field(ge=0)
    currency: str
    image_url: Annotated[
        str,
        AccessibilityAnnotation(
            sc="1.1.1",
            type=AccessibilityNudgeType.TEXT_ALTERNATIVE,
            message="Provide an appropriate text alternative for the product image.",
            values_resolver=sibling_field_values("name"),
        ),
    ]
    available_quantity: int = Field(ge=0)
    features: list[str]


class ProductDetailDTO(BaseModel):
    id: int
    name: Annotated[
        str,
        AccessibilityAnnotation(
            sc="1.3.1",
            type=AccessibilityNudgeType.SEMANTIC_RELATIONSHIP,
            message="Use semantic structure so the product name and features are programmatically conveyed as meaningful relationships, such as a main heading and a list.",
            values_resolver=current_value_list,
        ),
        AccessibilityAnnotation(
            sc="2.4.6",
            type=AccessibilityNudgeType.HEADING,
            message="Use the product name as the main descriptive heading for the product view.",
            values_resolver=current_value_list,
        ),
    ]
    description: str
    price: float = Field(ge=0)
    currency: str
    image_url: Annotated[
        str,
        AccessibilityAnnotation(
            sc="1.1.1",
            type=AccessibilityNudgeType.TEXT_ALTERNATIVE,
            message="Provide an appropriate text alternative for the product image.",
            values_resolver=sibling_field_values("name"),
        ),
    ]
    available_quantity: int = Field(ge=0)
    features: Annotated[
        list[str],
        AccessibilityAnnotation(
            sc="1.3.1",
            type=AccessibilityNudgeType.SEMANTIC_RELATIONSHIP,
            message="Use semantic structure so the product name and features are programmatically conveyed as meaningful relationships, such as a main heading and a list.",
            values_resolver=current_value_list,
        ),
    ]


class ProductCollectionResponseDTO(BaseModel):
    data: list[ProductSummaryDTO]
    links: list[LinkDTO]
    accessibility: AccessibilityDTO | None = None


class ProductResponseDTO(BaseModel):
    data: ProductDetailDTO
    links: list[LinkDTO]
    accessibility: AccessibilityDTO | None = None
