from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.dtos.common_dtos import LinkDTO


class CustomerInDTO(BaseModel):
    full_name: str = Field(
        min_length=1,
        max_length=100,
    )
    email: EmailStr


class DeliveryAddressInDTO(BaseModel):
    address_line: str = Field(
        min_length=1,
        max_length=200,
    )
    city: str = Field(
        min_length=1,
        max_length=100,
    )
    postcode: str = Field(
        min_length=1,
        max_length=20,
    )


class PaymentInDTO(BaseModel):
    cardholder_name: str = Field(
        min_length=1,
        max_length=100,
    )
    card_number: str = Field(
        min_length=12,
        max_length=23,
    )
    expiry_date: str = Field(
        pattern=r"^\d{2}/\d{2}$",
    )
    security_code: str = Field(
        pattern=r"^\d{3,4}$",
    )


class OrderInDTO(BaseModel):
    product_id: int
    quantity: int = Field(
        ge=1,
        le=5,
    )

    customer: CustomerInDTO
    delivery_address: DeliveryAddressInDTO
    payment: PaymentInDTO

    marketing_opt_in: bool = False


class OrderOutDTO(BaseModel):
    id: str
    status: Literal["confirmed"]
    message: str

    product_id: int
    product_name: str
    quantity: int

    total: float
    currency: str

    links: list[LinkDTO]