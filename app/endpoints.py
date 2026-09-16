from fastapi import APIRouter, Header, Request, Response, status

from app.accessibility import AccessibilityAnnotation, AccessibilityNudgeType, LinkDefinition, accessibility, current_value_list, get_endpoint_accessibility
from app.dtos.order_dtos import CheckoutInDTO, OrderDataDTO, OrderItemDTO, OrderResponseDTO
from app.dtos.product_dtos import ProductCollectionResponseDTO, ProductDetailDTO, ProductResponseDTO, ProductSummaryDTO
from app.services.accessibility_service import (
    ACCESSIBILITY_HEADER_ALIAS,
    ACCESSIBILITY_HEADER_DESCRIPTION,
    accessibility_requested,
    append_accessibility_vary_header,
    build_accessibility_response,
    build_link_dtos,
)
from app.services.order_service import get_order_by_id, place_order
from app.services.product_service import get_product_by_id, get_products


router = APIRouter(prefix="/api/v1")


def build_product_summary(product: dict, request: Request) -> ProductSummaryDTO:
    return ProductSummaryDTO(
        id=product["id"], name=product["name"], description=product["description"], price=product["price"], currency=product["currency"],
        image_url=str(request.url_for("static", path=product["image_path"])), available_quantity=product["available_quantity"], features=product["features"],
    )


def build_product_detail(product: dict, request: Request) -> ProductDetailDTO:
    return ProductDetailDTO(
        id=product["id"], name=product["name"], description=product["description"], price=product["price"], currency=product["currency"],
        image_url=str(request.url_for("static", path=product["image_path"])), available_quantity=product["available_quantity"], features=product["features"],
    )


def build_product_collection_links() -> list[LinkDefinition]:
    return [LinkDefinition(href="/api/v1/products", rel="self", type="GET", label="Browse products")]


def build_product_detail_links(product_id: int) -> list[LinkDefinition]:
    return [
        LinkDefinition(href=f"/api/v1/products/{product_id}", rel="self", type="GET", label="View product"),
        LinkDefinition(href="/api/v1/products", rel="products", type="GET", label="Browse products"),
        LinkDefinition(href="/api/v1/orders", rel="order", type="POST", label="Buy now", accessibility=get_endpoint_accessibility("place_order_endpoint")),
    ]


def build_order_data(order: dict) -> OrderDataDTO:
    return OrderDataDTO(
        id=order["id"], status=order["status"], message=order["message"], items=[OrderItemDTO(**item) for item in order["items"]],
        item_count=order["item_count"], total=order["total"], currency=order["currency"],
    )


def build_order_links(order_id: str) -> list[LinkDefinition]:
    return [
        LinkDefinition(href=f"/api/v1/orders/{order_id}", rel="self", type="GET", label="View order"),
        LinkDefinition(href="/api/v1/products", rel="products", type="GET", label="Browse products"),
    ]


def build_product_collection_response(products: list[dict], request: Request, accessibility_enabled: bool) -> ProductCollectionResponseDTO:
    data, links = [build_product_summary(product, request) for product in products], build_product_collection_links()
    return ProductCollectionResponseDTO(data=data, links=build_link_dtos(links), accessibility=build_accessibility_response(data=data, links=links) if accessibility_enabled else None)


def build_product_response(product: dict, request: Request, accessibility_enabled: bool) -> ProductResponseDTO:
    data, links = build_product_detail(product, request), build_product_detail_links(product["id"])
    return ProductResponseDTO(data=data, links=build_link_dtos(links), accessibility=build_accessibility_response(data=data, links=links) if accessibility_enabled else None)


def build_order_response(order: dict, accessibility_enabled: bool) -> OrderResponseDTO:
    data, links = build_order_data(order), build_order_links(order["id"])
    return OrderResponseDTO(data=data, links=build_link_dtos(links), accessibility=build_accessibility_response(data=data, links=links) if accessibility_enabled else None)


@router.get("/products", response_model=ProductCollectionResponseDTO, response_model_exclude_none=True, tags=["Products"], name="read_products")
def read_products(request: Request, response: Response, accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION)) -> ProductCollectionResponseDTO:
    append_accessibility_vary_header(response)
    return build_product_collection_response(get_products(), request, accessibility_enabled=accessibility_requested(accessibility))


@router.get("/products/{product_id}", response_model=ProductResponseDTO, response_model_exclude_none=True, tags=["Products"], name="read_product")
def read_product(product_id: int, request: Request, response: Response, accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION)) -> ProductResponseDTO:
    append_accessibility_vary_header(response)
    return build_product_response(get_product_by_id(product_id), request, accessibility_enabled=accessibility_requested(accessibility))


@router.post(
    "/orders", response_model=OrderResponseDTO, response_model_exclude_none=True, status_code=status.HTTP_201_CREATED, tags=["Orders"], name="place_order",
    responses={
        status.HTTP_402_PAYMENT_REQUIRED: {"description": "Payment failed."},
        status.HTTP_404_NOT_FOUND: {"description": "Product not found."},
        status.HTTP_409_CONFLICT: {"description": "Requested quantity is unavailable."},
    },
)
@accessibility(
    AccessibilityAnnotation(sc="4.1.2", type=AccessibilityNudgeType.ACCESSIBLE_NAME, message="Use the Buy now control's label as its accessible name.", values_resolver=current_value_list),
    AccessibilityAnnotation(sc="2.5.3", type=AccessibilityNudgeType.VISIBLE_LABEL, message="Ensure the accessible name of the Buy now control includes its visible label.", values_resolver=current_value_list),
)
def place_order_endpoint(
    checkout: CheckoutInDTO, request: Request, response: Response,
    accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION),
) -> OrderResponseDTO:
    append_accessibility_vary_header(response)
    created_order = place_order(checkout)
    response.headers["Location"] = str(request.url_for("read_order", order_id=created_order["id"]))
    return build_order_response(created_order, accessibility_enabled=accessibility_requested(accessibility))


@router.get("/orders/{order_id}", response_model=OrderResponseDTO, response_model_exclude_none=True, tags=["Orders"], name="read_order")
def read_order(order_id: str, response: Response, accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION)) -> OrderResponseDTO:
    append_accessibility_vary_header(response)
    return build_order_response(get_order_by_id(order_id), accessibility_enabled=accessibility_requested(accessibility))
