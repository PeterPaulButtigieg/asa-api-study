from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field

from app.accessibility import AccessibilityAnnotation, AccessibilityNudgeType, child_field_values, current_value_list
from app.dtos.common_dtos import AccessibilityDTO, LinkDTO


class CustomerInDTO(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr


class DeliveryAddressInDTO(BaseModel):
    address_line: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    postcode: str = Field(min_length=1, max_length=20)


class PaymentInDTO(BaseModel):
    cardholder_name: str = Field(min_length=1, max_length=100)
    card_number: str = Field(min_length=12, max_length=23)
    expiry_date: str = Field(pattern=r"^\d{2}/\d{2}$")
    security_code: str = Field(pattern=r"^\d{3,4}$")


class CheckoutInDTO(BaseModel):
    customer: CustomerInDTO
    delivery_address: DeliveryAddressInDTO
    payment: PaymentInDTO


class OrderItemDTO(BaseModel):
    product_id: int
    product_name: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)
    line_total: float = Field(ge=0)
    currency: str


class OrderDataDTO(BaseModel):
    id: str
    status: Literal["confirmed"]
    message: Annotated[
        str,
        AccessibilityAnnotation(
            sc="4.1.3",
            type=AccessibilityNudgeType.STATUS_MESSAGE,
            message="Announce the order result as a status message without moving focus.",
            values_resolver=current_value_list,
        ),
    ]
    items: Annotated[
        list[OrderItemDTO],
        AccessibilityAnnotation(
            sc="1.3.1",
            type=AccessibilityNudgeType.SEMANTIC_RELATIONSHIP,
            message="Present ordered items as a semantic list or table with quantities and totals programmatically associated.",
            values_resolver=child_field_values("product_name"),
        ),
    ]
    item_count: int = Field(ge=0)
    total: float = Field(ge=0)
    currency: str


class OrderResponseDTO(BaseModel):
    data: OrderDataDTO
    links: list[LinkDTO]
    accessibility: AccessibilityDTO | None = None
