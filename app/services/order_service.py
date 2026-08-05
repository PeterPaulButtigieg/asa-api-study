from uuid import uuid4

from fastapi import HTTPException, status

from app.data import ORDERS, PRODUCTS, SUCCESSFUL_TEST_CARD
from app.dtos.order_dtos import OrderInDTO


def create_order(order: OrderInDTO) -> dict:
    product = PRODUCTS.get(order.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if order.quantity > product["available_quantity"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requested quantity is unavailable")
    normalized_card_number = order.payment.card_number.replace(" ", "").replace("-", "")
    if normalized_card_number != SUCCESSFUL_TEST_CARD:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Payment failed")
    order_id = f"TEST-{uuid4().hex[:8].upper()}"
    total = round(product["price"] * order.quantity, 2)
    created_order = {
        "id": order_id,
        "status": "confirmed",
        "message": "Order sent",
        "product_id": product["id"],
        "product_name": product["name"],
        "quantity": order.quantity,
        "total": total,
        "currency": product["currency"],
    }
    # Customer and payment information are not stored.
    ORDERS[order_id] = created_order
    return created_order