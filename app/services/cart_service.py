from uuid import uuid4

from annotated_types import Le
from fastapi import HTTPException, status

from app.data import CARTS, PRODUCTS
from app.dtos.cart_dtos import CartItemInDTO, CartItemUpdateDTO
from app.errors import APIErrorItem, APIException


def create_cart() -> dict:
    cart_id = f"CART-{uuid4().hex[:8].upper()}"
    CARTS[cart_id] = {"id": cart_id, "items": []}
    return CARTS[cart_id]


def get_cart_by_id(cart_id: str) -> dict:
    cart = CARTS.get(cart_id)
    if cart is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    return cart


def _get_product_or_error(product_id: int) -> dict:
    product = PRODUCTS.get(product_id)
    if product is not None:
        return product
    raise APIException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Product not found",
        errors=[APIErrorItem(field="product_id", message="Product not found", suggestion="Use a product ID returned by GET /api/v1/products.")],
    )


def _get_cart_item(cart: dict, product_id: int) -> dict | None:
    return next((entry for entry in cart["items"] if entry["product_id"] == product_id), None)


def _get_quantity_upper_bound() -> int | None:
    for metadata in CartItemUpdateDTO.model_fields["quantity"].metadata:
        if isinstance(metadata, Le):
            return metadata.le
    return None


def _build_quantity_unavailable_suggestion(product: dict) -> str:
    quantity_upper_bound = _get_quantity_upper_bound()
    maximum_quantity = product["available_quantity"] if quantity_upper_bound is None else min(product["available_quantity"], quantity_upper_bound)
    if maximum_quantity < 1:
        return "This product is currently unavailable."
    return f"Enter a quantity between 1 and {maximum_quantity}."


def _raise_quantity_unavailable(product: dict) -> None:
    raise APIException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Requested quantity is unavailable",
        errors=[
            APIErrorItem(
                field="quantity",
                message="Requested quantity is unavailable",
                suggestion=_build_quantity_unavailable_suggestion(product),
            )
        ],
    )


def _raise_missing_cart_item(action: str) -> None:
    raise APIException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Product is not in the cart",
        errors=[APIErrorItem(field="product_id", message="Product is not in the cart", suggestion=f"Add the product to the cart before {action} it.")],
    )


def build_cart_snapshot(cart: dict) -> dict:
    items: list[dict] = []
    item_count = 0
    total = 0.0
    currency = "EUR"
    for entry in cart["items"]:
        product = PRODUCTS.get(entry["product_id"])
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        line_total = round(product["price"] * entry["quantity"], 2)
        items.append(
            {
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": entry["quantity"],
                "unit_price": product["price"],
                "line_total": line_total,
                "currency": product["currency"],
            }
        )
        item_count += entry["quantity"]
        total += line_total
        currency = product["currency"]
    return {"id": cart["id"], "items": items, "item_count": item_count, "total": round(total, 2), "currency": currency}


def get_cart_snapshot(cart_id: str) -> dict:
    return build_cart_snapshot(get_cart_by_id(cart_id))


def add_item_to_cart(cart_id: str, item: CartItemInDTO) -> dict:
    cart = get_cart_by_id(cart_id)
    product = _get_product_or_error(item.product_id)
    existing_item = _get_cart_item(cart, item.product_id)
    requested_quantity = item.quantity + (existing_item["quantity"] if existing_item else 0)
    if requested_quantity > product["available_quantity"]:
        _raise_quantity_unavailable(product)
    if existing_item is None:
        cart["items"].append({"product_id": item.product_id, "quantity": item.quantity})
    else:
        existing_item["quantity"] = requested_quantity
    return build_cart_snapshot(cart)


def update_cart_item(cart_id: str, product_id: int, item: CartItemUpdateDTO) -> dict:
    cart = get_cart_by_id(cart_id)
    product = _get_product_or_error(product_id)
    existing_item = _get_cart_item(cart, product_id)
    if existing_item is None:
        _raise_missing_cart_item("updating")
    if item.quantity > product["available_quantity"]:
        _raise_quantity_unavailable(product)
    existing_item["quantity"] = item.quantity
    return build_cart_snapshot(cart)


def remove_cart_item(cart_id: str, product_id: int) -> dict:
    cart = get_cart_by_id(cart_id)
    _get_product_or_error(product_id)
    if _get_cart_item(cart, product_id) is None:
        _raise_missing_cart_item("removing")
    cart["items"] = [entry for entry in cart["items"] if entry["product_id"] != product_id]
    return build_cart_snapshot(cart)
