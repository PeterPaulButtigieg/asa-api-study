from uuid import uuid4

from fastapi import HTTPException, status

from app.data import CARTS, PRODUCTS
from app.dtos.cart_dtos import CartItemInDTO


def create_cart() -> dict:
    cart_id = f"CART-{uuid4().hex[:8].upper()}"
    cart = {"id": cart_id, "items": []}
    CARTS[cart_id] = cart
    return cart


def get_cart_by_id(cart_id: str) -> dict:
    cart = CARTS.get(cart_id)
    if cart is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    return cart


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
    product = PRODUCTS.get(item.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    existing_item = next((entry for entry in cart["items"] if entry["product_id"] == item.product_id), None)
    requested_quantity = item.quantity + (existing_item["quantity"] if existing_item else 0)
    if requested_quantity > product["available_quantity"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requested quantity is unavailable")
    if existing_item is None:
        cart["items"].append({"product_id": item.product_id, "quantity": item.quantity})
    else:
        existing_item["quantity"] = requested_quantity
    return build_cart_snapshot(cart)
