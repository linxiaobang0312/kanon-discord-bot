"""Safe, read-only smoke test for a known public product code."""
import inventory_lookup as inventory

target = "XB-518ae91b-3cf"
try:
    items, more = inventory.fetch_cards(target)
    exact_number = [
        c for c in items if isinstance(c, dict)
        and str(c.get("number", "")).casefold() == target.casefold()
    ]
    exact_id = [
        c for c in items if isinstance(c, dict)
        and str(c.get("id", "")).casefold() == target.casefold()
    ]
    print("LIVE_CATALOG items=%d exact_number_matches=%d exact_id_matches=%d has_more=%s"
          % (len(items), len(exact_number), len(exact_id), more))
    records = exact_number or exact_id
    if records:
        matched = records[0]
        print("LIVE_ITEM status=found sku=%s stock=%s price=%s"
              % (str(matched.get("number", ""))[:40],
                 str(matched.get("quantity", "unknown"))[:20],
                 str(matched.get("price", "unknown"))[:20]))
        print("LIVE_ITEM_FORMAT " + str(inventory.format_card(matched)).replace("\n", " | ")[:400])
    else:
        names = [c for c in items if isinstance(c, dict) and "高咲侑" in str(c.get("display_name") or c.get("name") or "")]
        print("LIVE_CATALOG related_public_name_matches=%d" % len(names))
except Exception as exc:
    print("LIVE_CATALOG diagnostic_failure=%s" % type(exc).__name__)


print("TEXT_SEARCH smoke:")
for query in ("請問還有跟澀谷香音相關的卡牌嗎", "有沒有澀谷香音的卡片？", "渋谷かのん庫存"):
    try:
        term = inventory.extract_card_term(query)
        versions = inventory.search_variants(term) if term else set()
        related = []
        for item in items:
            if isinstance(item, dict) and inventory.match_card(item, versions):
                related.append(item)
        live = [c for c in related if (inventory.number(c.get("quantity"), whole=True) or 0) > 0]
        print("TEXT_SEARCH query_type=%s term=%s found=%d in_stock=%d" % (
            "cn" if "澀" in query else "jp", term, len(related), len(live)))
        for card in live[:3]:
            print("TEXT_SEARCH sample code=%s name=%s stock=%s price=%s" % (
                str(card.get("number", ""))[:40],
                str(card.get("display_name") or card.get("official_name") or "")[:70],
                str(card.get("quantity", ""))[:10], str(card.get("price", ""))[:20]))
    except Exception as exc:
        print("TEXT_SEARCH error=%s" % type(exc).__name__)
