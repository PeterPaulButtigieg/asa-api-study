from fastapi import (
    APIRouter,
    Request,
    Response,
    status,
)

from app.dtos.common_dtos import LinkDTO
from app.dtos.order_dtos import (
    OrderInDTO,
    OrderOutDTO,
)
from app.dtos.product_dtos import ProductOutDTO
from app.services.order_service import (
    create_order as create_order_service,
    get_order_by_id,
)
from app.services.product_service import (
    get_product_by_id,
    get_products,
)


router = APIRouter(
    prefix="/api/v1",
)


def build_product_response(
    product: dict,
    request: Request,
) -> ProductOutDTO:
    return ProductOutDTO(
        id=product["id"],
        name=product["name"],
        description=product["description"],
        price=product["price"],
        currency=product["currency"],
        image_url=str(
            request.url_for(
                "static",
                path=product["image_path"],
            )
        ),
        available_quantity=product["available_quantity"],
        features=product["features"],
        links=[
            LinkDTO(
                href=f"/api/v1/products/{product['id']}",
                rel="self",
                type="GET",
            ),
            LinkDTO(
                href="/api/v1/orders",
                rel="order",
                type="POST",
            ),
        ],
    )


def build_order_response(
    order: dict,
) -> OrderOutDTO:
    return OrderOutDTO(
        **order,
        links=[
            LinkDTO(
                href=f"/api/v1/orders/{order['id']}",
                rel="self",
                type="GET",
            ),
            LinkDTO(
                href=f"/api/v1/products/{order['product_id']}",
                rel="product",
                type="GET",
            ),
            LinkDTO(
                href="/api/v1/orders",
                rel="order-another",
                type="POST",
            ),
        ],
    )


@router.get(
    "",
    tags=["API"],
    name="api_root",
)
def read_api_root():
    return {
        "name": "Study Checkout API",
        "version": "1.0.0",
        "links": [
            {
                "href": "/api/v1",
                "rel": "self",
                "type": "GET",
            },
            {
                "href": "/api/v1/products",
                "rel": "products",
                "type": "GET",
            },
            {
                "href": "/api/v1/orders",
                "rel": "order",
                "type": "POST",
            },
        ],
    }


@router.get(
    "/products",
    response_model=list[ProductOutDTO],
    tags=["Products"],
    name="read_products",
)
def read_products(
    request: Request,
) -> list[ProductOutDTO]:
    products = get_products()

    return [
        build_product_response(
            product,
            request,
        )
        for product in products
    ]


@router.get(
    "/products/{product_id}",
    response_model=ProductOutDTO,
    tags=["Products"],
    name="read_product",
)
def read_product(
    product_id: int,
    request: Request,
) -> ProductOutDTO:
    product = get_product_by_id(product_id)

    return build_product_response(
        product,
        request,
    )


@router.post(
    "/orders",
    response_model=OrderOutDTO,
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
) -> OrderOutDTO:
    created_order = create_order_service(order)

    response.headers["Location"] = str(
        request.url_for(
            "read_order",
            order_id=created_order["id"],
        )
    )

    return build_order_response(
        created_order,
    )


@router.get(
    "/orders/{order_id}",
    response_model=OrderOutDTO,
    tags=["Orders"],
    name="read_order",
)
def read_order(
    order_id: str,
) -> OrderOutDTO:
    order = get_order_by_id(order_id)

    return build_order_response(
        order,
    )