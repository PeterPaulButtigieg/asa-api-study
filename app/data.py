PRODUCTS = {
    1: {
        "id": 1,
        "name": "Pen",
        "description": "An ordinary Pen",
        "price": 0.50,
        "currency": "EUR",
        "image_path": "images/pen.jpg",
        "available_quantity": 100,
        "features": ["Blue Ink", "Oil-Based Paste Ink", "Can write on diverse surfaces"],
    },
    2: {
        "id": 2,
        "name": "Lighter",
        "description": "A Refillable Lighter",
        "price": 2.10,
        "currency": "EUR",
        "image_path": "images/lighter.jpeg",
        "available_quantity": 12,
        "features": ["High durability", "Refillable"],
    },
}

CARTS: dict[str, dict] = {}
ORDERS: dict[str, dict] = {}

SUCCESSFUL_TEST_CARD = "4242424242424242"
