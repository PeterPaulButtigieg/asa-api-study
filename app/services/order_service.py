from uuid import uuid4

from fastapi import status

from app.data import ORDERS, PRODUCTS, SUCCESSFUL_TEST_CARD
from app.dtos.order_dtos import CheckoutInDTO
from app.errors import APIErrorItem, APIException


def place_order(checkout: CheckoutInDTO) -> dict:
    product = PRODUCTS.get(checkout.product_id)
    if product is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
            errors=[APIErrorItem(field="product_id", message="Product not found", suggestion="Use a product ID returned by GET /api/v1/products.")],
        )
    if checkout.quantity > product["available_quantity"]:
        maximum = min(product["available_quantity"], 5)
        raise APIException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requested quantity is unavailable",
            errors=[APIErrorItem(field="quantity", message="Requested quantity is unavailable", suggestion=f"Enter a quantity between 1 and {maximum}.")],
        )
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

    line_total = round(product["price"] * checkout.quantity, 2)
    order_items = [{
        "product_id": product["id"], "product_name": product["name"], "quantity": checkout.quantity,
        "unit_price": product["price"], "line_total": line_total, "currency": product["currency"],
    }]
    product["available_quantity"] -= checkout.quantity

    order_id = f"ORDER-{uuid4().hex[:8].upper()}"
    created_order = {
        "id": order_id,
        "status": "confirmed",
        "message": "Order sent",
        "items": order_items,
        "item_count": checkout.quantity,
        "total": line_total,
        "currency": product["currency"],
    }
    ORDERS[order_id] = created_order
    return created_order


def get_order_by_id(order_id: str) -> dict:
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order
