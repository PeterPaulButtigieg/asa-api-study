from copy import deepcopy
import unittest

from starlette.testclient import TestClient

from app.data import ORDERS, PRODUCTS
from app.main import app
from app.services.accessibility_service import load_wcag_index


CHECKOUT_PAYLOAD = {
    "product_id": 1,
    "quantity": 2,
    "customer": {"full_name": "Jane Doe", "email": "jane@example.com"},
    "delivery_address": {"address_line": "1 Main Street", "city": "Valletta", "postcode": "VLT1010"},
    "payment": {
        "cardholder_name": "Jane Doe", "card_number": "4242 4242 4242 4242", "expiry_date": "12/30", "security_code": "123",
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
        ORDERS.clear()
        PRODUCTS.clear()
        PRODUCTS.update(deepcopy(ORIGINAL_PRODUCTS))
        load_wcag_index.cache_clear()

    def test_product_detail_exposes_buy_now_order_action(self):
        response = self.client.get("/api/v1/products/1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Vary"), "Accessibility")
        self.assertEqual(response.json()["links"][-1], {"href": "/api/v1/orders", "rel": "order", "type": "POST", "label": "Buy now"})
        self.assertNotIn("accessibility", response.json())

    def test_direct_order_reduces_product_stock_and_can_be_retrieved(self):
        initial_stock = PRODUCTS[1]["available_quantity"]
        response = self.client.post("/api/v1/orders", json=CHECKOUT_PAYLOAD)

        self.assertEqual(response.status_code, 201)
        self.assertIn("/api/v1/orders/", response.headers["Location"])
        self.assertEqual(response.json()["data"]["items"][0]["product_id"], 1)
        self.assertEqual(response.json()["data"]["item_count"], 2)
        self.assertEqual(response.json()["data"]["total"], 1.0)
        self.assertEqual(PRODUCTS[1]["available_quantity"], initial_stock - 2)

        order_id = response.json()["data"]["id"]
        retrieval = self.client.get(f"/api/v1/orders/{order_id}")
        self.assertEqual(retrieval.status_code, 200)
        self.assertEqual(retrieval.json()["data"]["id"], order_id)

    def test_direct_order_errors_preserve_plain_responses_and_enhance_when_requested(self):
        invalid_product = deepcopy(CHECKOUT_PAYLOAD)
        invalid_product["product_id"] = 999
        plain_product = self.client.post("/api/v1/orders", json=invalid_product)
        self.assertEqual(plain_product.status_code, 404)
        self.assertEqual(plain_product.json(), {"detail": "Product not found"})

        enhanced_product = self.client.post("/api/v1/orders", json=invalid_product, headers={"Accessibility": "true"})
        self.assertEqual(enhanced_product.status_code, 404)
        self.assertEqual(enhanced_product.json()["errors"][0]["field"], "product_id")

        unavailable = deepcopy(CHECKOUT_PAYLOAD)
        unavailable["quantity"] = 5
        PRODUCTS[1]["available_quantity"] = 3
        enhanced_quantity = self.client.post("/api/v1/orders", json=unavailable, headers={"Accessibility": "true"})
        self.assertEqual(enhanced_quantity.status_code, 409)
        self.assertEqual(enhanced_quantity.json()["errors"][0]["suggestion"], "Enter a quantity between 1 and 3.")

        bad_payment = deepcopy(CHECKOUT_PAYLOAD)
        bad_payment["payment"]["card_number"] = "1111 1111 1111 1111"
        enhanced_payment = self.client.post("/api/v1/orders", json=bad_payment, headers={"Accessibility": "true"})
        self.assertEqual(enhanced_payment.status_code, 402)
        self.assertEqual(enhanced_payment.json()["errors"][0]["field"], "payment.card_number")

    def test_accessibility_metadata_covers_product_and_buy_now_control(self):
        response = self.client.get("/api/v1/products/1", headers={"Accessibility": "true"})

        self.assertEqual(response.status_code, 200)
        nudges = response.json()["accessibility"]["nudges"]
        criteria = {nudge["success_criterion"] for nudge in nudges}
        self.assertTrue({"1.1.1 - Non-text Content", "1.3.1 - Info and Relationships", "2.4.6 - Headings and Labels", "4.1.2 - Name, Role, Value", "2.5.3 - Label in Name"}.issubset(criteria))
        buy_now_nudge = next(nudge for nudge in nudges if nudge["success_criterion"] == "4.1.2 - Name, Role, Value")
        self.assertEqual(buy_now_nudge["target"], ["links[rel=order].label"])
        self.assertEqual(buy_now_nudge["values"], ["Buy now"])

    def test_direct_order_validation_and_success_status_nudges(self):
        invalid_request = deepcopy(CHECKOUT_PAYLOAD)
        invalid_request["quantity"] = 0
        validation_response = self.client.post("/api/v1/orders", json=invalid_request, headers={"Accessibility": "true"})
        self.assertEqual(validation_response.status_code, 422)
        self.assertEqual(validation_response.json()["errors"][0]["field"], "quantity")
        self.assertEqual(validation_response.json()["errors"][0]["suggestion"], "Enter a whole number within the allowed range.")

        order_response = self.client.post("/api/v1/orders", json=CHECKOUT_PAYLOAD, headers={"Accessibility": "true"})
        self.assertEqual(order_response.status_code, 201)
        criteria = {nudge["success_criterion"] for nudge in order_response.json()["accessibility"]["nudges"]}
        self.assertIn("4.1.3 - Status Messages", criteria)

    def test_wcag_index_is_cached_and_centralized(self):
        first_index = load_wcag_index()
        second_index = load_wcag_index()

        self.assertIs(first_index, second_index)
        self.assertEqual(load_wcag_index.cache_info().misses, 1)
        self.assertEqual(first_index["1.1.1"].name, "Non-text Content")
        self.assertTrue(first_index["1.1.1"].description.startswith("All non-text content"))


if __name__ == "__main__":
    unittest.main()
