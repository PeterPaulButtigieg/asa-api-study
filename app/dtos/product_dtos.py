from pydantic import BaseModel, Field

from app.dtos.common_dtos import LinkDTO


class ProductOutDTO(BaseModel):
    id: int
    name: str
    description: str
    price: float = Field(ge=0)
    currency: str
    image_url: str
    available_quantity: int = Field(ge=0)
    features: list[str]
    links: list[LinkDTO]