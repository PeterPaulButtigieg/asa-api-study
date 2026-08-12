from fastapi import APIRouter, Header, Request, Response, status

from app.accessibility import AccessibilityAnnotation, AccessibilityNudgeType, LinkDefinition, accessibility, current_value_list, get_endpoint_accessibility
from app.dtos.cart_dtos import CartDataDTO, CartItemDTO, CartItemInDTO, CartItemUpdateDTO, CartResponseDTO
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
from app.services.cart_service import (
    add_item_to_cart,
    create_cart as create_cart_service,
    get_cart_snapshot,
    remove_cart_item as remove_cart_item_service,
    update_cart_item as update_cart_item_service,
)
from app.services.order_service import get_order_by_id, place_order_from_cart
from app.services.product_service import get_product_by_id, get_products


router = APIRouter(prefix="/api/v1")


def build_product_summary(product: dict, request: Request) -> ProductSummaryDTO:
    return ProductSummaryDTO(
        id=product["id"],
        name=product["name"],
        description=product["description"],
        price=product["price"],
        currency=product["currency"],
        image_url=str(request.url_for("static", path=product["image_path"])),
        available_quantity=product["available_quantity"],
        features=product["features"],
    )


def build_product_detail(product: dict, request: Request) -> ProductDetailDTO:
    return ProductDetailDTO(
        id=product["id"],
        name=product["name"],
        description=product["description"],
        price=product["price"],
        currency=product["currency"],
        image_url=str(request.url_for("static", path=product["image_path"])),
        available_quantity=product["available_quantity"],
        features=product["features"],
    )


def build_product_collection_links() -> list[LinkDefinition]:
    return [
        LinkDefinition(href="/api/v1/products", rel="self", type="GET", label="Browse products"),
        LinkDefinition(
            href="/api/v1/carts",
            rel="create-cart",
            type="POST",
            label="Create cart",
            accessibility=get_endpoint_accessibility("create_cart"),
        ),
    ]


def build_product_detail_links(product_id: int) -> list[LinkDefinition]:
    return [
        LinkDefinition(href=f"/api/v1/products/{product_id}", rel="self", type="GET", label="View product"),
        LinkDefinition(href="/api/v1/products", rel="products", type="GET", label="Browse products"),
        LinkDefinition(
            href="/api/v1/carts",
            rel="create-cart",
            type="POST",
            label="Create cart",
            accessibility=get_endpoint_accessibility("create_cart"),
        ),
    ]


def build_cart_item_links(cart_id: str, product_id: int) -> list[LinkDefinition]:
    return [
        LinkDefinition(href=f"/api/v1/carts/{cart_id}/items/{product_id}", rel="update-item", type="PATCH", label="Update item quantity"),
        LinkDefinition(href=f"/api/v1/carts/{cart_id}/items/{product_id}", rel="remove-item", type="DELETE", label="Remove item from cart"),
    ]


def build_cart_item(cart_id: str, item: dict) -> CartItemDTO:
    return CartItemDTO(
        product_id=item["product_id"],
        product_name=item["product_name"],
        quantity=item["quantity"],
        unit_price=item["unit_price"],
        line_total=item["line_total"],
        currency=item["currency"],
        links=build_link_dtos(build_cart_item_links(cart_id, item["product_id"])),
    )


def build_cart_data(snapshot: dict) -> CartDataDTO:
    return CartDataDTO(
        id=snapshot["id"],
        items=[build_cart_item(snapshot["id"], item) for item in snapshot["items"]],
        item_count=snapshot["item_count"],
        total=snapshot["total"],
        currency=snapshot["currency"],
    )


def build_cart_links(cart_id: str) -> list[LinkDefinition]:
    return [
        LinkDefinition(href=f"/api/v1/carts/{cart_id}", rel="self", type="GET", label="View cart"),
        LinkDefinition(
            href=f"/api/v1/carts/{cart_id}/items",
            rel="add-item",
            type="POST",
            label="Add item to cart",
            accessibility=get_endpoint_accessibility("add_cart_item"),
        ),
        LinkDefinition(
            href=f"/api/v1/carts/{cart_id}/orders",
            rel="place-order",
            type="POST",
            label="Place order",
            accessibility=get_endpoint_accessibility("place_cart_order"),
        ),
        LinkDefinition(href="/api/v1/products", rel="products", type="GET", label="Browse products"),
    ]


def build_order_data(order: dict) -> OrderDataDTO:
    return OrderDataDTO(
        id=order["id"],
        status=order["status"],
        message=order["message"],
        items=[OrderItemDTO(**item) for item in order["items"]],
        item_count=order["item_count"],
        total=order["total"],
        currency=order["currency"],
    )


def build_order_links(order_id: str) -> list[LinkDefinition]:
    return [
        LinkDefinition(href=f"/api/v1/orders/{order_id}", rel="self", type="GET", label="View order"),
        LinkDefinition(href="/api/v1/products", rel="products", type="GET", label="Browse products"),
        LinkDefinition(
            href="/api/v1/carts",
            rel="create-cart",
            type="POST",
            label="Create another cart",
            accessibility=get_endpoint_accessibility("create_cart"),
        ),
    ]


def build_product_collection_response(products: list[dict], request: Request, accessibility_enabled: bool) -> ProductCollectionResponseDTO:
    data, links = [build_product_summary(product, request) for product in products], build_product_collection_links()
    accessibility = build_accessibility_response(data=data, links=links) if accessibility_enabled else None
    return ProductCollectionResponseDTO(data=data, links=build_link_dtos(links), accessibility=accessibility)


def build_product_response(product: dict, request: Request, accessibility_enabled: bool) -> ProductResponseDTO:
    data, links = build_product_detail(product, request), build_product_detail_links(product["id"])
    accessibility = build_accessibility_response(data=data, links=links) if accessibility_enabled else None
    return ProductResponseDTO(data=data, links=build_link_dtos(links), accessibility=accessibility)


def build_cart_response(snapshot: dict, accessibility_enabled: bool) -> CartResponseDTO:
    data, links = build_cart_data(snapshot), build_cart_links(snapshot["id"])
    accessibility = build_accessibility_response(data=data, links=links) if accessibility_enabled else None
    return CartResponseDTO(data=data, links=build_link_dtos(links), accessibility=accessibility)


def build_order_response(order: dict, accessibility_enabled: bool) -> OrderResponseDTO:
    data, links = build_order_data(order), build_order_links(order["id"])
    accessibility = build_accessibility_response(data=data, links=links) if accessibility_enabled else None
    return OrderResponseDTO(data=data, links=build_link_dtos(links), accessibility=accessibility)


@router.get("/products", response_model=ProductCollectionResponseDTO, response_model_exclude_none=True, tags=["Products"], name="read_products")
def read_products(
    request: Request,
    response: Response,
    accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION),
) -> ProductCollectionResponseDTO:
    append_accessibility_vary_header(response)
    return build_product_collection_response(get_products(), request, accessibility_enabled=accessibility_requested(accessibility))


@router.get("/products/{product_id}", response_model=ProductResponseDTO, response_model_exclude_none=True, tags=["Products"], name="read_product")
def read_product(
    product_id: int,
    request: Request,
    response: Response,
    accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION),
) -> ProductResponseDTO:
    append_accessibility_vary_header(response)
    return build_product_response(get_product_by_id(product_id), request, accessibility_enabled=accessibility_requested(accessibility))


@router.post("/carts", response_model=CartResponseDTO, response_model_exclude_none=True, status_code=status.HTTP_201_CREATED, tags=["Carts"], name="create_cart")
@accessibility(
    AccessibilityAnnotation(
        sc="4.1.2",
        type=AccessibilityNudgeType.ACCESSIBLE_NAME,
        message="Use the link or button label as the accessible name of the create-cart control.",
        values_resolver=current_value_list,
    )
)
def create_cart(
    request: Request,
    response: Response,
    accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION),
) -> CartResponseDTO:
    append_accessibility_vary_header(response)
    cart = create_cart_service()
    response.headers["Location"] = str(request.url_for("read_cart", cart_id=cart["id"]))
    return build_cart_response(get_cart_snapshot(cart["id"]), accessibility_enabled=accessibility_requested(accessibility))


@router.get("/carts/{cart_id}", response_model=CartResponseDTO, response_model_exclude_none=True, tags=["Carts"], name="read_cart")
def read_cart(
    cart_id: str,
    response: Response,
    accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION),
) -> CartResponseDTO:
    append_accessibility_vary_header(response)
    return build_cart_response(get_cart_snapshot(cart_id), accessibility_enabled=accessibility_requested(accessibility))


@router.post(
    "/carts/{cart_id}/items",
    response_model=CartResponseDTO,
    response_model_exclude_none=True,
    tags=["Carts"],
    name="add_cart_item",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Cart or product not found."},
        status.HTTP_409_CONFLICT: {"description": "Requested quantity is unavailable."},
    },
)
@accessibility(
    AccessibilityAnnotation(
        sc="4.1.2",
        type=AccessibilityNudgeType.ACCESSIBLE_NAME,
        message="Use the link or button label as the accessible name of the add-item control.",
        values_resolver=current_value_list,
    )
)
def add_cart_item(
    cart_id: str,
    item: CartItemInDTO,
    response: Response,
    accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION),
) -> CartResponseDTO:
    append_accessibility_vary_header(response)
    return build_cart_response(add_item_to_cart(cart_id, item), accessibility_enabled=accessibility_requested(accessibility))


@router.patch(
    "/carts/{cart_id}/items/{product_id}",
    response_model=CartResponseDTO,
    response_model_exclude_none=True,
    tags=["Carts"],
    name="update_cart_item",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Cart, product, or cart item not found."},
        status.HTTP_409_CONFLICT: {"description": "Requested quantity is unavailable."},
    },
)
def update_cart_item(
    cart_id: str,
    product_id: int,
    item: CartItemUpdateDTO,
    response: Response,
    accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION),
) -> CartResponseDTO:
    append_accessibility_vary_header(response)
    return build_cart_response(
        update_cart_item_service(cart_id, product_id, item),
        accessibility_enabled=accessibility_requested(accessibility),
    )


@router.delete(
    "/carts/{cart_id}/items/{product_id}",
    response_model=CartResponseDTO,
    response_model_exclude_none=True,
    tags=["Carts"],
    name="remove_cart_item",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Cart, product, or cart item not found."}},
)
def remove_cart_item(
    cart_id: str,
    product_id: int,
    response: Response,
    accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION),
) -> CartResponseDTO:
    append_accessibility_vary_header(response)
    return build_cart_response(
        remove_cart_item_service(cart_id, product_id),
        accessibility_enabled=accessibility_requested(accessibility),
    )


@router.post(
    "/carts/{cart_id}/orders",
    response_model=OrderResponseDTO,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    tags=["Orders"],
    name="place_cart_order",
    responses={
        status.HTTP_402_PAYMENT_REQUIRED: {"description": "Payment failed."},
        status.HTTP_404_NOT_FOUND: {"description": "Cart or product not found."},
        status.HTTP_409_CONFLICT: {"description": "Cart is empty or requested quantity is unavailable."},
    },
)
@accessibility(
    AccessibilityAnnotation(
        sc="4.1.2",
        type=AccessibilityNudgeType.ACCESSIBLE_NAME,
        message="Use the link or button label as the accessible name of the place-order control.",
        values_resolver=current_value_list,
    )
)
def place_cart_order(
    cart_id: str,
    checkout: CheckoutInDTO,
    request: Request,
    response: Response,
    accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION),
) -> OrderResponseDTO:
    append_accessibility_vary_header(response)
    created_order = place_order_from_cart(cart_id, checkout)
    response.headers["Location"] = str(request.url_for("read_order", order_id=created_order["id"]))
    return build_order_response(created_order, accessibility_enabled=accessibility_requested(accessibility))


@router.get("/orders/{order_id}", response_model=OrderResponseDTO, response_model_exclude_none=True, tags=["Orders"], name="read_order")
def read_order(
    order_id: str,
    response: Response,
    accessibility: bool = Header(default=False, alias=ACCESSIBILITY_HEADER_ALIAS, description=ACCESSIBILITY_HEADER_DESCRIPTION),
) -> OrderResponseDTO:
    append_accessibility_vary_header(response)
    return build_order_response(get_order_by_id(order_id), accessibility_enabled=accessibility_requested(accessibility))
