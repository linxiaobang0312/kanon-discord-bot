"""Public read-only product search for the Kanon Discord bot."""
import os, re, json, asyncio
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request, urlopen

MISSING_CARD = "想查哪一張卡呢？請提供卡號或卡名，我才能確認是哪個版本～"
NOT_CONNECTED = "商品即時查詢還沒完成連線，現在不能確認價格和庫存，請找筱邦確認。"
FAILED = "目前連不上最新商品資料，價格和庫存我不能亂猜，請稍後再試或找筱邦確認。"
HINTS = ("這張還有", "還有嗎", "有貨嗎", "有沒有貨", "還有貨", "庫存", "剩幾",
         "剩多少", "可售", "查卡", "找卡", "查商品", "多少錢", "價格", "價錢", "售價", "現貨")
CODE = re.compile(r"(?<!\w)[A-Za-z0-9!+]+(?:-[A-Za-z0-9!+]+){2,}(?!\w)")
SIMPLE = {"", "這張", "那張", "卡片", "卡", "商品", "什麼", "llocg"}

def is_product_query(message):
    text = (message or "").replace(" ", "").lower()
    return any(word in text for word in HINTS)

def extract_card_term(message):
    raw = (message or "").strip()
    found = CODE.search(raw)
    if found:
        return found.group(0)
    text = re.sub(r"<@!?\d+>", "", raw)
    text = re.sub(r"^(?:香音|請問|麻煩|不好意思|幫我|我想問)+[，：:\s]*", "", text)
    text = re.sub(r"(?:這張|那張)?(?:卡片|卡|商品)?(?:目前)?"
                  r"(?:還有嗎|還有貨嗎|還有|有貨嗎|有沒有貨|剩幾張|剩多少|多少錢|價格|價錢|售價|庫存|現貨|可售|查卡|找卡|查商品)",
                  " ", text)
    text = re.sub(r"(?:我想買|想買|幫我查|幫我找|有嗎|嗎|呢|呀|啊|？|\?|！|!)+", " ", text)
    text = " ".join(text.strip(" ，,。:：『』「」()（）<>").split())
    if text.lower().replace(" ", "") in SIMPLE or len(text) < 2:
        return None
    return text[:100]

def field(row, *keys):
    for k in keys:
        if row.get(k) is not None and row.get(k) != "":
            return row[k]
    return None

def number(value, whole=False):
    if value is None or isinstance(value, bool):
        return None
    try:
        v = Decimal(str(value).replace(",", "").strip())
        if not v.is_finite() or v < 0 or (whole and v != v.to_integral_value()):
            return None
        return int(v) if whole else v
    except (InvalidOperation, ValueError):
        return None

def safe(value):
    value = re.sub(r"[\r\n\t]+", " ", str(value or "").replace("@", "＠"))[:120]
    return re.sub(r"([\\*_~>|])", r"\\\1", value)

def fetch_cards(query):
    # 現有 GET /api/cards 只支援完整清單；添加 q/limit 會觸發 HTTP 錯誤。
    # 只請求公開完整清單；由 answer_product_question 在本機依卡號/名稱篩選。
    url = os.getenv("CARD_SEARCH_API_URL", "").strip()
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise ValueError("Invalid API endpoint")
    headers = {"Accept": "application/json", "User-Agent": "KanonCustomerBot/1.0"}
    token = os.getenv("CARD_SEARCH_API_TOKEN", "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(url, headers=headers, method="GET"), timeout=7) as resp:
        if "json" not in resp.headers.get("Content-Type", ""):
            raise ValueError("Not JSON")
        raw = resp.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("API payload too large")
    payload = json.loads(raw)
    if isinstance(payload, list):
        return payload, False
    if not isinstance(payload, dict) or payload.get("ok") is False or payload.get("success") is False:
        raise ValueError("API failure")
    data = payload.get("data", payload)
    if isinstance(data, list):
        return data, bool(payload.get("has_more"))
    if isinstance(data, dict):
        for key in ("items", "cards", "results", "products"):
            if isinstance(data.get(key), list):
                return data[key], bool(data.get("has_more", data.get("hasMore", False)))
    raise ValueError("Unknown API result format")

def format_card(card):
    code = field(card, "card_number", "card_no", "cardNo", "number", "sku")
    name = field(card, "display_name", "custom_name", "card_name", "cardName", "name", "official_name", "title")
    variant = field(card, "variant", "version", "rarity")
    if code is None and name is None:
        return None
    quantity = number(field(card, "quantity", "available_quantity", "availableQuantity", "available_qty",
                            "saleable_quantity", "saleableQuantity"), whole=True)
    price = number(field(card, "unit_price", "unitPrice", "price"))
    currency = str(field(card, "currency", "currency_code") or "TWD").upper()
    price_text = "未提供" if price is None else (
        ("NT$" if currency in ("TWD", "NTD") else safe(currency) + " ") +
        (format(price, ",.0f") if price == price.to_integral_value() else format(price, ",.2f")) + "/張"
    )
    stock_text = "未提供（需人工確認）" if quantity is None else ("已無庫存" if quantity == 0 else str(quantity) + " 張")
    title = "｜".join(safe(v) for v in (code, name, variant) if v is not None)
    return "**" + title + "**\n可售：" + stock_text + "｜價格：" + price_text

async def answer_product_question(message):
    term = extract_card_term(message)
    if not term:
        return MISSING_CARD
    if not os.getenv("CARD_SEARCH_API_URL", "").strip():
        return NOT_CONNECTED
    try:
        cards, more = await asyncio.wait_for(asyncio.to_thread(fetch_cards, term), timeout=9)
    except Exception:
        return FAILED
    key = re.sub(r"\s+", "", term).casefold()
    lines = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        values = (field(card, "card_number", "card_no", "cardNo", "number", "sku"),
                  field(card, "display_name", "custom_name", "card_name", "cardName", "name", "official_name", "title"))
        if any(key in re.sub(r"\s+", "", str(v)).casefold() for v in values if v is not None):
            text = format_card(card)
            if text:
                lines.append(text)
    if not lines:
        return "目前查不到符合「" + safe(term) + "」的公開商品資料，可以提供完整卡號或卡名嗎？"
    result = "找到以下商品版本：\n\n" + "\n\n".join(lines[:5])
    if len(lines) > 5 or more:
        result += "\n\n還有其他版本，請給我更完整的卡號。"
    return result[:1850]


def probe_card_api():
    """Diagnostic for deployment logs. Print schema/type names only, never item values."""
    from urllib.error import HTTPError, URLError
    endpoint = os.getenv("CARD_SEARCH_API_URL", "").strip()
    p = urlsplit(endpoint)
    if p.scheme != "https" or not p.hostname:
        return "not configured"
    url = endpoint
    headers = {"Accept": "application/json", "User-Agent": "KanonCustomerBot/1.0"}
    token = os.getenv("CARD_SEARCH_API_TOKEN", "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with urlopen(Request(url, headers=headers, method="GET"), timeout=9) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read(3 * 1024 * 1024 + 1)
        if len(raw) > 3 * 1024 * 1024:
            return "status=%d too-large body" % status
        doc = json.loads(raw)
        keys = sorted(doc.keys())[:30] if isinstance(doc, dict) else []
        candidates = [doc] if isinstance(doc, dict) else []
        while candidates:
            value = candidates.pop(0)
            if isinstance(value, list):
                if value and isinstance(value[0], dict):
                    return "status=%d type=%s root_keys=%s item_keys=%s count=%d" % (
                        status, content_type, keys, sorted(value[0].keys())[:60], len(value))
            elif isinstance(value, dict):
                for key in ("data", "items", "cards", "products", "results", "list"):
                    if key in value:
                        candidates.append(value[key])
        return "status=%d type=%s root_type=%s root_keys=%s (no sample)" % (
            status, content_type, type(doc).__name__, keys)
    except HTTPError as exc:
        return "HTTP error %d" % exc.code
    except URLError as exc:
        return "network error: %s" % type(exc.reason).__name__
    except (ValueError, OSError) as exc:
        return "probe parse/network error: %s" % type(exc).__name__
