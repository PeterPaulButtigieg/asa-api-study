from copy import deepcopy
import unittest

from starlette.testclient import TestClient

from app.data import CARTS, ORDERS, PRODUCTS
from app.main import app
from app.services.accessibility_service import load_wcag_index


CHECKOUT_PAYLOAD = {
    "customer": {"full_name": "Jane Doe", "email": "jane@example.com"},
    "delivery_address": {"address_line": "1 Main Street", "city": "Valletta", "postcode": "VLT1010"},
    "payment": {
        "cardholder_name": "Jane Doe",
        "card_number": "4242 4242 4242 4242",
        "expiry_date": "12/30",
        "security_code": "123",
    },
}
ORIGINAL_PRODUCTS = deepcopy(PRODUCTS)


class StudyApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def setUp(self):
        CARTS.clear()
        ORDERS.clear()
        PRODUCTS.clear()
        PRODUCTS.update(deepcopy(ORIGINAL_PRODUCTS))
        load_wcag_index.cache_clear()

    def create_cart(self) -> str:
        response = self.client.post("/api/v1/carts")
        self.assertEqual(response.status_code, 201)
        return response.json()["data"]["id"]

    def add_item(self, cart_id: str, product_id: int, quantity: int):
        response = self.client.post(f"/api/v1/carts/{cart_id}/items", json={"product_id": product_id, "quantity": quantity})
        self.assertEqual(response.status_code, 200)
        return response

    def test_cart_item_update_replaces_quantity_and_order_reduces_stock_only_on_success(self):
        initial_stock = PRODUCTS[1]["available_quantity"]
        cart_id = self.create_cart()
        self.add_item(cart_id, 1, 3)

        update_response = self.client.patch(f"/api/v1/carts/{cart_id}/items/1", json={"quantity": 2})
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["data"]["items"][0]["quantity"], 2)
        self.assertEqual(update_response.json()["data"]["item_count"], 2)
        self.assertEqual(update_response.json()["data"]["total"], 1.0)
        self.assertEqual(PRODUCTS[1]["available_quantity"], initial_stock)

        order_response = self.client.post(f"/api/v1/carts/{cart_id}/orders", json=CHECKOUT_PAYLOAD)
        self.assertEqual(order_response.status_code, 201)
        self.assertIn("/api/v1/orders/", order_response.headers["Location"])
        self.assertEqual(PRODUCTS[1]["available_quantity"], initial_stock - 2)

    def test_cart_item_remove_returns_updated_cart_and_empty_cart_checkout_conflicts(self):
        cart_id = self.create_cart()
        self.add_item(cart_id, 1, 2)
        self.add_item(cart_id, 2, 1)

        remove_first = self.client.delete(f"/api/v1/carts/{cart_id}/items/1")
        self.assertEqual(remove_first.status_code, 200)
        self.assertEqual(remove_first.json()["data"]["item_count"], 1)
        self.assertEqual(remove_first.json()["data"]["total"], 2.1)
        self.assertEqual([item["product_id"] for item in remove_first.json()["data"]["items"]], [2])

        remove_second = self.client.delete(f"/api/v1/carts/{cart_id}/items/2")
        self.assertEqual(remove_second.status_code, 200)
        self.assertEqual(remove_second.json()["data"]["items"], [])

        order_response = self.client.post(f"/api/v1/carts/{cart_id}/orders", json=CHECKOUT_PAYLOAD)
        self.assertEqual(order_response.status_code, 409)
        self.assertEqual(order_response.json(), {"detail": "Cart is empty"})

    def test_cart_item_update_and_remove_errors(self):
        self.assertEqual(
            self.client.patch("/api/v1/carts/CART-UNKNOWN/items/1", json={"quantity": 2}).json(),
            {"detail": "Cart not found"},
        )

        cart_id = self.create_cart()
        missing_product = self.client.patch(f"/api/v1/carts/{cart_id}/items/999", json={"quantity": 2})
        self.assertEqual(missing_product.status_code, 404)
        self.assertEqual(missing_product.json(), {"detail": "Product not found"})

        missing_item = self.client.patch(f"/api/v1/carts/{cart_id}/items/1", json={"quantity": 2})
        self.assertEqual(missing_item.status_code, 404)
        self.assertEqual(missing_item.json(), {"detail": "Product is not in the cart"})

        PRODUCTS[2]["available_quantity"] = 3
        self.add_item(cart_id, 2, 1)
        stock_conflict = self.client.patch(f"/api/v1/carts/{cart_id}/items/2", json={"quantity": 4})
        self.assertEqual(stock_conflict.status_code, 409)
        self.assertEqual(stock_conflict.json(), {"detail": "Requested quantity is unavailable"})

        invalid_quantity = self.client.patch(f"/api/v1/carts/{cart_id}/items/2", json={"quantity": 0})
        self.assertEqual(invalid_quantity.status_code, 422)
        self.assertIn("detail", invalid_quantity.json())

        remove_missing_item = self.client.delete(f"/api/v1/carts/{cart_id}/items/1")
        self.assertEqual(remove_missing_item.status_code, 404)
        self.assertEqual(remove_missing_item.json(), {"detail": "Product is not in the cart"})

    def test_accessibility_header_controls_cart_response_and_item_action_nudges(self):
        cart_id = self.create_cart()
        self.add_item(cart_id, 1, 1)

        plain_response = self.client.get(f"/api/v1/carts/{cart_id}")
        self.assertEqual(plain_response.status_code, 200)
        self.assertNotIn("accessibility", plain_response.json())
        self.assertEqual(plain_response.headers.get("Vary"), "Accessibility")
        self.assertEqual(
            [link["rel"] for link in plain_response.json()["data"]["items"][0]["links"]],
            ["update-item", "remove-item"],
        )

        enhanced_response = self.client.get(f"/api/v1/carts/{cart_id}", headers={"Accessibility": "true"})
        self.assertEqual(enhanced_response.status_code, 200)
        nudges = enhanced_response.json()["accessibility"]["nudges"]
        item_action_nudge = next(nudge for nudge in nudges if nudge["message"] == "Use the link or button label as the accessible name of each cart-item action control.")
        self.assertEqual(item_action_nudge["success_criterion"], "4.1.2 - Name, Role, Value")
        self.assertEqual(
            item_action_nudge["target"],
            ["data.items[0].links[rel=update-item].label", "data.items[0].links[rel=remove-item].label"],
        )
        self.assertEqual(item_action_nudge["values"], ["Update item quantity", "Remove item from cart"])

    def test_validation_and_payment_errors_use_annotation_and_structured_service_metadata(self):
        cart_id = self.create_cart()
        self.add_item(cart_id, 1, 1)

        plain_validation = self.client.patch(f"/api/v1/carts/{cart_id}/items/1", json={"quantity": 0})
        self.assertEqual(plain_validation.status_code, 422)
        self.assertIn("detail", plain_validation.json())
        self.assertNotIn("errors", plain_validation.json())

        enhanced_validation = self.client.patch(
            f"/api/v1/carts/{cart_id}/items/1",
            json={"quantity": 0},
            headers={"Accessibility": "true"},
        )
        self.assertEqual(enhanced_validation.status_code, 422)
        self.assertEqual(enhanced_validation.json()["errors"][0]["field"], "quantity")
        self.assertEqual(enhanced_validation.json()["errors"][0]["suggestion"], "Enter a whole number within the allowed range.")
        self.assertEqual(
            {nudge["success_criterion"] for nudge in enhanced_validation.json()["accessibility"]["nudges"]},
            {
                "4.1.3 - Status Messages",
                "3.3.1 - Error Identification",
                "3.3.3 - Error Suggestion",
            },
        )

        bad_checkout = deepcopy(CHECKOUT_PAYLOAD)
        bad_checkout["payment"]["card_number"] = "1111 1111 1111 1111"
        plain_payment = self.client.post(f"/api/v1/carts/{cart_id}/orders", json=bad_checkout)
        self.assertEqual(plain_payment.status_code, 402)
        self.assertEqual(plain_payment.json(), {"detail": "Payment failed"})

        enhanced_payment = self.client.post(
            f"/api/v1/carts/{cart_id}/orders",
            json=bad_checkout,
            headers={"Accessibility": "true"},
        )
        self.assertEqual(enhanced_payment.status_code, 402)
        self.assertEqual(enhanced_payment.json()["errors"][0]["field"], "payment.card_number")
        self.assertEqual(
            enhanced_payment.json()["errors"][0]["suggestion"],
            "Use the successful test card number 4242 4242 4242 4242.",
        )

    def test_existing_product_and_order_accessibility_nudges_still_work(self):
        product_response = self.client.get("/api/v1/products/1", headers={"Accessibility": "true"})
        self.assertEqual(product_response.status_code, 200)
        product_criteria = {nudge["success_criterion"] for nudge in product_response.json()["accessibility"]["nudges"]}
        self.assertIn("1.1.1 - Non-text Content", product_criteria)
        self.assertIn("1.3.1 - Info and Relationships", product_criteria)
        self.assertIn("2.4.6 - Headings and Labels", product_criteria)

        cart_id = self.create_cart()
        self.add_item(cart_id, 1, 1)
        order_response = self.client.post(
            f"/api/v1/carts/{cart_id}/orders",
            json=CHECKOUT_PAYLOAD,
            headers={"Accessibility": "true"},
        )
        self.assertEqual(order_response.status_code, 201)
        order_criteria = {nudge["success_criterion"] for nudge in order_response.json()["accessibility"]["nudges"]}
        self.assertIn("4.1.3 - Status Messages", order_criteria)

    def test_wcag_index_is_cached_and_centralized(self):
        first_index = load_wcag_index()
        second_index = load_wcag_index()
        cache_info = load_wcag_index.cache_info()

        self.assertIs(first_index, second_index)
        self.assertEqual(cache_info.misses, 1)
        self.assertGreaterEqual(cache_info.hits, 1)
        self.assertEqual(first_index["1.1.1"].name, "Non-text Content")
        self.assertTrue(first_index["1.1.1"].description.startswith("All non-text content"))
        self.assertEqual(first_index["1.1.1"].href, "https://www.w3.org/TR/WCAG22/#non-text-content")


if __name__ == "__main__":
    unittest.main()
