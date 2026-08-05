from fastapi import HTTPException, status

from app.data import PRODUCTS

def get_product_by_id(product_id: int) -> dict:
    product = PRODUCTS.get(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product
