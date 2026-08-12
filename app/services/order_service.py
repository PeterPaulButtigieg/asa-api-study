from uuid import uuid4

from fastapi import HTTPException, status

from app.data import CARTS, ORDERS, PRODUCTS, SUCCESSFUL_TEST_CARD
from app.dtos.order_dtos import CheckoutInDTO
from app.errors import APIErrorItem, APIException


def place_order_from_cart(cart_id: str, checkout: CheckoutInDTO) -> dict:
    cart = CARTS.get(cart_id)
    if cart is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    if not cart["items"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cart is empty")
    normalized_card_number = checkout.payment.card_number.replace(" ", "").replace("-", "")
    if normalized_card_number != SUCCESSFUL_TEST_CARD:
        raise APIException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment failed",
            errors=[
                APIErrorItem(
                    field="payment.card_number",
                    message="Payment failed",
                    suggestion="Use the successful test card number 4242 4242 4242 4242.",
                )
            ],
        )

    order_items: list[dict] = []
    item_count = 0
    total = 0.0
    currency = "EUR"
    for entry in cart["items"]:
        product = PRODUCTS.get(entry["product_id"])
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        if entry["quantity"] > product["available_quantity"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requested quantity is unavailable")
        line_total = round(product["price"] * entry["quantity"], 2)
        order_items.append(
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

    for entry in cart["items"]:
        PRODUCTS[entry["product_id"]]["available_quantity"] -= entry["quantity"]

    order_id = f"ORDER-{uuid4().hex[:8].upper()}"
    created_order = {
        "id": order_id,
        "status": "confirmed",
        "message": "Order sent",
        "items": order_items,
        "item_count": item_count,
        "total": round(total, 2),
        "currency": currency,
    }
    ORDERS[order_id] = created_order
    cart["items"] = []
    return created_order


def get_order_by_id(order_id: str) -> dict:
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order
