from fastapi import APIRouter, Header, Request, Response, status

from app.dtos.common_dtos import LinkDTO
from app.dtos.order_dtos import OrderInDTO, OrderOutDTO
from app.dtos.product_dtos import ProductOutDTO
from app.services.order_service import create_order as create_order_service
from app.services.accessibility_service import (
    ACCESSIBILITY_HEADER_ALIAS,
    ACCESSIBILITY_HEADER_DESCRIPTION,
    append_accessibility_vary_header,
    build_accessibility_dtos,
)
from app.services.product_service import get_product_by_id

router = APIRouter(prefix="/api/v1")

def build_product_response(
    product: dict,
    request: Request,
    accessibility_enabled: bool = False,
    accessibility_mappings: list[tuple[str, str]] | None = None,
) -> ProductOutDTO:
    accessibility = None
    if accessibility_enabled:
        if accessibility_mappings is None:
            accessibility_mappings = [("1.1.1", "image_url"), ("2.4.6", "name")]
        accessibility = build_accessibility_dtos(accessibility_mappings)
    return ProductOutDTO(
        id=product["id"],
        name=product["name"],
        description=product["description"],
        price=product["price"],
        currency=product["currency"],
        image_url=str(request.url_for("static", path=product["image_path"])),
        available_quantity=product["available_quantity"],
        features=product["features"],
        accessibility=accessibility,
        links=[
            LinkDTO(href=f"/api/v1/products/{product['id']}", rel="self", type="GET"),
            LinkDTO(href="/api/v1/orders", rel="order", type="POST"),
        ],
    )

def build_order_response(
    order: dict,
    accessibility_enabled: bool = False,
) -> OrderOutDTO:
    accessibility = None
    if accessibility_enabled:
        accessibility_mappings = [("2.4.6", "product_name")]
        if order.get("message"):
            accessibility_mappings.append(("4.1.3", "message"))
        accessibility = build_accessibility_dtos(accessibility_mappings)
    return OrderOutDTO(
        **order,
        accessibility=accessibility,
        links=[
            LinkDTO(href=f"/api/v1/orders/{order['id']}", rel="self", type="GET"),
            LinkDTO(href=f"/api/v1/products/{order['product_id']}", rel="product", type="GET"),
            LinkDTO(href="/api/v1/orders", rel="order-another", type="POST"),
        ],
    )

@router.get(
    "/products/{product_id}",
    response_model=ProductOutDTO,
    response_model_exclude_none=True,
    tags=["Products"],
    name="read_product",
)
def read_product(
    product_id: int,
    request: Request,
    response: Response,
    accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION),
) -> ProductOutDTO:
    append_accessibility_vary_header(response)
    product = get_product_by_id(product_id)
    return build_product_response(
        product,
        request,
        accessibility_enabled=accessibility,
        accessibility_mappings=[
            ("1.1.1", "image_url"),
            ("1.3.1", "name"),
            ("1.3.1", "features"),
            ("2.4.6", "name"),
            ("4.1.2", "links[rel=order]"),
        ],
    )

@router.post(
    "/orders",
    response_model=OrderOutDTO,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    tags=["Orders"],
    name="create_order",
    responses={
        status.HTTP_402_PAYMENT_REQUIRED: {
            "description": "Payment failed.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Product not found.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Requested quantity is unavailable.",
        },
    },
)

def create_order(
    order: OrderInDTO,
    request: Request,
    response: Response,
    accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION),
) -> OrderOutDTO:
    append_accessibility_vary_header(response)
    request.state.order_context = {"product_id": order.product_id, "quantity": order.quantity}
    created_order = create_order_service(order)
    response.headers["Location"] = str(request.url_for("read_order", order_id=created_order["id"]))
    return build_order_response(created_order, accessibility_enabled=accessibility)
