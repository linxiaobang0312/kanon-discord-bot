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
