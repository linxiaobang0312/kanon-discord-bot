import asyncio
import os
import unittest
from unittest.mock import patch
import inventory_lookup as lookup

class InventoryTests(unittest.TestCase):
    def test_reference_without_card_identifier(self):
        self.assertTrue(lookup.is_product_query("香音這張還有嗎？"))
        self.assertIsNone(lookup.extract_card_term("香音這張還有嗎？"))

    def test_card_number_recognized(self):
        self.assertEqual(
            lookup.extract_card_term("香音 PL!HS-pb1-007-P+ 還有嗎"),
            "PL!HS-pb1-007-P+",
        )

    def test_chat_not_intercepted(self):
        self.assertFalse(lookup.is_product_query("你好，我喜歡你"))

    def test_missing_stock_not_zero(self):
        item = {"card_number": "A-001", "card_name": "測試", "unit_price": 35}
        reply = lookup.format_card(item)
        self.assertIn("未提供（需人工確認）", reply)
        self.assertIn("NT$35/張", reply)

    def test_zero_stock_not_missing(self):
        item = {"card_number": "A-001", "card_name": "測試", "available_quantity": 0, "unit_price": 0}
        reply = lookup.format_card(item)
        self.assertIn("已無庫存", reply)
        self.assertIn("NT$0/張", reply)

    def test_variants_not_merged_and_no_admin_url(self):
        cards = [
            {"card_number": "PL!HS-pb1-007-P+", "card_name": "小香", "variant": "P+",
             "available_quantity": 1, "unit_price": 100, "admin_url": "https://example.com/admin"},
            {"card_number": "PL!HS-pb1-008-R", "card_name": "小香", "variant": "R",
             "available_quantity": 4, "unit_price": 50},
        ]
        with patch.dict(os.environ, {"CARD_SEARCH_API_URL": "https://example.com/api/public/cards"}):
            with patch.object(lookup, "fetch_cards", return_value=(cards, False)):
                reply = asyncio.run(lookup.answer_product_question("小香庫存"))
        self.assertIn("P+", reply)
        self.assertIn("R", reply)
        self.assertIn("1 張", reply)
        self.assertIn("4 張", reply)
        self.assertNotIn("admin", reply)
        self.assertNotIn("https://", reply)

    def test_no_guess_on_connectivity_error(self):
        with patch.dict(os.environ, {"CARD_SEARCH_API_URL": "https://example.com/api/public/cards"}):
            with patch.object(lookup, "fetch_cards", side_effect=TimeoutError("fail")):
                reply = asyncio.run(lookup.answer_product_question("小香庫存"))
        self.assertIn("不能亂猜", reply)
        self.assertNotIn("已無庫存", reply)

    def test_query_has_no_exposed_metadata(self):
        card = {"card_no": "PL!HS-pb1-007-P+", "card_name": "小香",
                "available_quantity": 3, "unit_price": 200,
                "backend_link": "https://internal.example/admin"}
        self.assertNotIn("internal.example", lookup.format_card(card))

if __name__ == "__main__":
    unittest.main()
