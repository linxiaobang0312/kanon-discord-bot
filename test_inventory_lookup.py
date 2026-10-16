import asyncio
import os
import unittest
from unittest.mock import patch
import inventory_lookup as lookup

class InventoryTests(unittest.TestCase):

    def test_fetch_uses_unmodified_get_endpoint(self):
        import json
        response = json.dumps({
            "cards": [{"number": "PL!HS-pb1-007-P+", "display_name": "示例",
                       "quantity": 2, "price": 70, "rarity": "P+"}],
            "series": [], "sections": [], "admin": {}
        }).encode("utf-8")

        class FakeResponse:
            headers = {"Content-Type": "application/json"}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return response

        url = "https://example.org/api/cards"
        with patch.dict(os.environ, {"CARD_SEARCH_API_URL": url}):
            with patch.object(lookup, "urlopen", return_value=FakeResponse()) as mock:
                cards, more = lookup.fetch_cards("PL!HS-pb1-007-P+")
                req = mock.call_args.args[0]
        self.assertEqual(req.full_url, url)
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(len(cards), 1)
        self.assertFalse(more)

    def test_real_customer_query_routes_to_inventory(self):
        question = "XB-518ae91b-3cf 這個商品還有幾隻"
        self.assertTrue(lookup.is_product_query(question))
        self.assertEqual(lookup.extract_card_term(question), "XB-518ae91b-3cf")
        self.assertTrue(lookup.is_product_query("XB-518ae91b-3cf"))
        self.assertTrue(lookup.is_product_query("櫻坂雫X高咲侑還有幾件"))
        self.assertFalse(lookup.is_product_query("香音，你今天心情如何？"))

    def test_missing_code_prompts_for_item(self):
        self.assertTrue(lookup.is_product_query("這個商品還有幾隻？"))
        self.assertIsNone(lookup.extract_card_term("這個商品還有幾隻？"))
        with patch.dict(os.environ, {"CARD_SEARCH_API_URL": "https://example.org/api/cards"}):
            reply = asyncio.run(lookup.answer_product_question("這個商品還有幾隻？"))
        self.assertIn("卡號或卡名", reply)

    def test_other_toy_exact_id_live_lookup(self):
        records = [
            {"id": "id-one", "number": "XB-518ae91b-3cf",
             "display_name": "櫻坂雫X高咲侑", "section_name": "其他玩具",
             "card_type": "商品", "quantity": 1, "price": 70,
             "admin_url": "https://hidden.example.org/admin"},
        ]
        with patch.dict(os.environ, {"CARD_SEARCH_API_URL": "https://example.org/api/cards"}):
            with patch.object(lookup, "fetch_cards", return_value=(records, False)):
                reply = asyncio.run(lookup.answer_product_question("XB-518ae91b-3cf 這個商品還有幾隻"))
        self.assertIn("XB-518ae91b-3cf", reply)
        self.assertIn("櫻坂雫X高咲侑", reply)
        self.assertIn("1 件", reply)
        self.assertIn("NT$70/件", reply)
        self.assertNotIn("/admin", reply)
        self.assertNotIn("hidden.example.org", reply)

    def test_other_toy_partial_name_lookup(self):
        records = [
            {"number": "XB-518ae91b-3cf", "display_name": "櫻坂雫X高咲侑",
             "quantity": 1, "price": 70},
        ]
        with patch.dict(os.environ, {"CARD_SEARCH_API_URL": "https://example.org/api/cards"}):
            with patch.object(lookup, "fetch_cards", return_value=(records, False)):
                reply = asyncio.run(lookup.answer_product_question("高咲侑還有幾件"))
        self.assertIn("XB-518ae91b-3cf", reply)
        self.assertIn("1 件", reply)

    def test_match_public_id_when_number_missing(self):
        records = [{"id": "XB-518ae91b-3cf", "display_name": "櫻坂雫X高咲侑",
                    "quantity": 1, "price": 70}]
        with patch.dict(os.environ, {"CARD_SEARCH_API_URL": "https://example.org/api/cards"}):
            with patch.object(lookup, "fetch_cards", return_value=(records, False)):
                reply = asyncio.run(lookup.answer_product_question("XB-518ae91b-3cf 有貨嗎"))
        self.assertIn("1 件", reply)

    def test_natural_language_card_discovery(self):
        question = "請問還有跟澀谷香音相關的卡牌嗎"
        self.assertTrue(lookup.is_product_query(question))
        self.assertEqual(lookup.extract_card_term(question), "澀谷香音")
        self.assertTrue(lookup.is_product_query("有沒有澀谷香音的卡片？"))
        self.assertTrue(lookup.is_product_query("找有關渋谷かのん的卡牌"))
        self.assertEqual(lookup.extract_card_term("找有關渋谷かのん的卡牌"), "渋谷かのん")
        self.assertFalse(lookup.is_product_query("你喜歡澀谷香音嗎？"))
        self.assertFalse(lookup.is_product_query("香音今天心情好嗎"))

    def test_character_alias_search_in_api_names(self):
        cards = [
            {"number": "PL-001-R", "display_name": "渋谷かのん", "rarity": "R",
             "quantity": 2, "price": 30},
            {"number": "PL-001-PE+", "official_name": "澁谷かのん",
             "display_name": "Love Live! 卡片", "rarity": "PE+",
             "quantity": 1, "price": 180},
            {"number": "PL-002-R", "display_name": "唐可可",
             "quantity": 7, "price": 40}
        ]
        with patch.dict(os.environ, {"CARD_SEARCH_API_URL": "https://example.org/api/cards"}):
            with patch.object(lookup, "fetch_cards", return_value=(cards, False)):
                result = asyncio.run(lookup.answer_product_question("請問還有跟澀谷香音相關的卡牌嗎"))
        self.assertIn("渋谷かのん", result)
        self.assertIn("PL-001-PE+", result)
        self.assertIn("2 張", result)
        self.assertIn("1 張", result)
        self.assertIn("NT$180", result)
        self.assertNotIn("唐可可", result)

    def test_discovery_prefers_in_stock_and_separates_out_of_stock(self):
        cards = [
            {"number": "PL-002-R", "display_name": "渋谷かのん", "quantity": 0, "price": 10},
            {"number": "PL-002-P", "display_name": "渋谷かのん", "quantity": 3, "price": 90},
        ]
        with patch.dict(os.environ, {"CARD_SEARCH_API_URL": "https://example.org/api/cards"}):
            with patch.object(lookup, "fetch_cards", return_value=(cards, False)):
                result = asyncio.run(lookup.answer_product_question("還有跟澀谷香音相關的卡牌嗎"))
        self.assertIn("其中 1 個有現貨", result)
        self.assertLess(result.index("PL-002-P"), result.index("PL-002-R"))
        self.assertIn("已無庫存", result)

    def test_dont_confuse_missing_stock_with_available(self):
        with patch.dict(os.environ, {"CARD_SEARCH_API_URL": "https://example.org/api/cards"}):
            with patch.object(lookup, "fetch_cards", return_value=([
                {"number": "PL-003", "name": "渋谷かのん", "quantity": None, "price": 50}
            ], False)):
                result = asyncio.run(lookup.answer_product_question("澀谷香音的卡牌"))
        self.assertIn("沒有可確認的現貨", result)
        self.assertIn("未提供（需人工確認）", result)

    def test_reference_without_card_identifier(self):
        self.assertTrue(lookup.is_product_query("香音這張還有嗎？"))
        self.assertIsNone(lookup.extract_card_term("香音這張還有嗎？"))

    def test_card_number_recognized(self):
        self.assertEqual(
            lookup.extract_card_term("香音 PL!HS-pb1-007-P+ 還有嗎"),
            "PL!HS-pb1-007-P+",
        )

    def test_howto_faq_not_intercepted(self):
        self.assertFalse(lookup.is_product_query("怎麼找卡"))
        self.assertFalse(lookup.is_product_query("價格怎麼看"))
        self.assertFalse(lookup.is_product_query("庫存怎麼看"))
        self.assertTrue(lookup.is_product_query("瑠璃乃庫存"))

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


    def test_real_site_api_schema(self):
        """/api/cards returns a dict with cards list; number, display_name, quantity, price, rarity."""
        payload = {
            "admin": {"private": "NOT FOR CUSTOMERS"},
            "cards": [
                {"number": "PL!HS-pb1-007-P+", "display_name": "瑠璃乃",
                 "quantity": 2, "price": 160, "rarity": "P+",
                 "import_source_url": "https://example.org/internal"}
            ],
            "sections": [], "series": []
        }
        cards, more = lookup.fetch_cards.__globals__["json"].loads(
            lookup.fetch_cards.__globals__["json"].dumps(payload)
        )["cards"], False
        self.assertFalse(more)
        rendered = lookup.format_card(cards[0])
        self.assertIn("瑠璃乃", rendered)
        self.assertIn("P+", rendered)
        self.assertIn("2 張", rendered)
        self.assertIn("NT$160/張", rendered)
        self.assertNotIn("import_source_url", rendered)
        self.assertNotIn("example.org", rendered)

    def test_readonly_site_payload_multiple_rarities(self):
        cards = [
            {"number": "PL!HS-pb1-007-P+", "display_name": "瑠璃乃", "rarity": "P+", "quantity": 1, "price": 500},
            {"number": "PL!HS-pb1-007-R", "display_name": "瑠璃乃", "rarity": "R", "quantity": 0, "price": 30},
        ]
        with patch.dict(os.environ, {"CARD_SEARCH_API_URL": "https://example.org/api/cards"}):
            with patch.object(lookup, "fetch_cards", return_value=(cards, False)):
                reply = asyncio.run(lookup.answer_product_question("瑠璃乃庫存"))
        self.assertIn("P+", reply)
        self.assertIn("R", reply)
        self.assertIn("1 張", reply)
        self.assertIn("已無庫存", reply)
        self.assertIn("NT$500", reply)
        self.assertIn("NT$30", reply)

    def test_query_has_no_exposed_metadata(self):
        card = {"card_no": "PL!HS-pb1-007-P+", "card_name": "小香",
                "available_quantity": 3, "unit_price": 200,
                "backend_link": "https://internal.example/admin"}
        self.assertNotIn("internal.example", lookup.format_card(card))

if __name__ == "__main__":
    unittest.main()
