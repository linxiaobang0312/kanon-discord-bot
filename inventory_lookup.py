"""Public read-only product search for the Kanon Discord bot."""
import os, re, json, asyncio, unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request, urlopen

MISSING_CARD = "想查哪一張卡呢？請提供卡號或卡名，我才能確認是哪個版本～"
NOT_CONNECTED = "商品即時查詢還沒完成連線，現在不能確認價格和庫存，請找筱邦確認。"
FAILED = "目前連不上最新商品資料，價格和庫存我不能亂猜，請稍後再試或找筱邦確認。"
HINTS = ("這張還有", "還有嗎", "還有幾", "有幾件", "有幾張", "有幾隻", "還剩幾",
         "幾件", "幾張", "幾隻", "幾個", "幾盒", "有貨嗎", "有沒有貨", "還有貨",
         "庫存", "剩幾", "剩多少", "可售", "查卡", "找卡", "查商品",
         "多少錢", "價格", "價錢", "售價", "現貨", "買得到嗎", "有賣嗎")
CODE = re.compile(r"(?<!\w)[A-Za-z0-9!+]+(?:-[A-Za-z0-9!+]+){2,}(?!\w)")
SIMPLE = {"", "這張", "那張", "卡片", "卡", "商品", "什麼", "llocg"}

def is_product_query(message):
    text = (message or "").replace(" ", "").lower()
    # 平台操作教學不是商品搜尋；普通聊天也不應被「香音」這個角色名攔截。
    howto = ("怎麼找卡", "如何找卡", "怎麼搜尋", "如何搜尋",
             "價格怎麼看", "庫存怎麼看", "怎麼操作", "怎麼使用")
    if any(phrase in text for phrase in howto):
        return False
    if CODE.search(message or "") or any(word in text for word in HINTS):
        return True
    return bool(
        re.search(r"(?:相關|有關).{0,5}(?:卡牌|卡片|成員卡|live卡|卡|商品)", text)
        or re.search(r"(?:有沒有|還有|想找|想買|查詢|找找|幫我找|幫我查).{1,48}(?:卡牌|卡片|成員卡|live卡)", text)
        or re.search(r"(?:卡牌|卡片|成員卡|live卡).{0,12}(?:有哪些|有嗎|還有嗎|有賣)", text)
    )

def extract_card_term(message):
    raw = (message or "").strip()
    found = CODE.search(raw)
    if found:
        return found.group(0)
    text = re.sub(r"<@!?\d+>", "", raw).strip()
    # 「香音」可能是稱呼 Bot，也可能就是在找角色「澀谷香音」，不能無條件刪掉。
    text = re.sub(r"^香音[，,！!：:\s]+", "", text)
    text = re.sub(r"^香音(?=(?:這張|這個|那張|請問))", "", text)
    text = re.sub(r"^(?:(?:請問|麻煩|不好意思|我想問|想問|可以幫我|幫我)[，,：:\s]*)+", "", text)
    # 「請問還有跟澀谷香音相關的卡牌嗎？」→「澀谷香音」
    text = re.sub(r"(?:相關|有關)(?:的)?(?:卡牌|卡片|成員卡|卡|商品)(?:嗎|呢|呀)?[？?！!]*$", "", text)
    text = re.sub(r"(?:的)?(?:卡牌|卡片|成員卡|商品)(?:還有嗎|有嗎|有哪些|嗎|呢)?[？?！!]*$", "", text)
    text = re.sub(r"^(?:(?:還有|有沒有|是否還有|有|想找|想買|我要買|幫我找|幫我查|查詢|搜尋|搜索|找找|找|查)[，,：:\s]*)+", "", text)
    text = re.sub(r"^(?:跟|和|與|關於|有關|相關)[，,：:\s]*", "", text)
    text = re.sub(r"(?:這個|那個|這張|那張)?(?:商品|玩具|卡片|卡)?(?:目前)?"
                  r"(?:還有幾(?:隻|件|張|個|盒)?|還剩幾(?:隻|件|張|個|盒)?|有幾(?:隻|件|張|個|盒)?"
                  r"|還有嗎|還有貨嗎|還有|有貨嗎|有沒有貨|剩幾(?:隻|件|張|個|盒)?"
                  r"|剩多少|多少錢|價格|價錢|售價|庫存|現貨|可售|查卡|找卡|查商品|買得到嗎|有賣嗎)",
                  " ", text)
    text = re.sub(r"(?:我想買|想買|幫我查|幫我找|有嗎|嗎|呢|呀|啊|？|\?|！|!)+", " ", text)
    text = " ".join(text.strip(" ，,。:：『』「」()（）<>").split())
    if text.lower().replace(" ", "") in SIMPLE or len(text) < 2:
        return None
    if re.fullmatch(r"(?:這|那)(?:個|張)?(?:商品|玩具|卡片|卡)?", text):
        return None
    return text[:100]

# 受控別名：用戶的繁中名稱與網站可能採用的日文／羅馬名稱對照。
# 搜尋結果仍必須由實際 API 商品名稱匹配，不能憑角色知識捏造卡片。
ALIASES = {
    "澀谷香音": (
        "澀谷香音", "澁谷香音", "渋谷香音", "涩谷香音",
        "澀谷かのん", "澁谷かのん", "渋谷かのん", "しぶやかのん",
        "shibuyakanon", "kanonshibuya", "香音", "かのん",
    )
}

def compact(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\s　・･·_\-／/]+", "", value)

def search_variants(term):
    needle = compact(term)
    result = {needle}
    for names in ALIASES.values():
        if needle in {compact(name) for name in names}:
            result.update(compact(name) for name in names)
    return {value for value in result if len(value) >= 2}

def match_card(card, variants):
    """Return grounded relevance; only names, code and public category are inspected."""
    keys = ("card_number", "card_no", "cardNo", "number", "sku", "id",
            "display_name", "custom_name", "card_name", "cardName",
            "name", "official_name", "title")
    best = 0
    for key in keys:
        value = compact(card.get(key))
        if not value:
            continue
        for wanted in variants:
            if wanted == value:
                best = max(best, 100 if key in keys[:6] else 90)
            elif wanted in value:
                best = max(best, 80 if key in keys[:6] else 70)
    # 團體、系列支援文字檢索，但相關程度比角色／卡名低。
    for key in ("group_name", "series", "section_name"):
        value = compact(card.get(key))
        if value and any(wanted in value for wanted in variants):
            best = max(best, 35)
    return best

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
    code = field(card, "card_number", "card_no", "cardNo", "number", "sku", "id")
    name = field(card, "display_name", "custom_name", "card_name", "cardName", "name", "official_name", "title")
    variant = field(card, "variant", "version", "rarity")
    if code is None and name is None:
        return None
    quantity = number(field(card, "quantity", "available_quantity", "availableQuantity", "available_qty",
                            "saleable_quantity", "saleableQuantity"), whole=True)
    price = number(field(card, "unit_price", "unitPrice", "price"))
    currency = str(field(card, "currency", "currency_code") or "TWD").upper()
    section = str(field(card, "section_name", "section") or "")
    product_type = str(field(card, "card_type", "type") or "")
    code_text = str(code or "")
    # 其他玩具在網站是「件」，卡牌則是「張」。
    unit = "件" if (code_text.upper().startswith("XB-")
                 or "玩具" in section or product_type == "商品") else "張"
    price_text = "未提供" if price is None else (
        ("NT$" if currency in ("TWD", "NTD") else safe(currency) + " ") +
        (format(price, ",.0f") if price == price.to_integral_value() else format(price, ",.2f")) + "/" + unit
    )
    stock_text = "未提供（需人工確認）" if quantity is None else ("已無庫存" if quantity == 0 else str(quantity) + " " + unit)
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

    variants = search_variants(term)
    matches = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        score = match_card(card, variants)
        if score:
            formatted = format_card(card)
            if formatted:
                amount = number(field(card, "quantity", "available_quantity", "availableQuantity",
                                      "available_qty", "saleable_quantity", "saleableQuantity"), whole=True)
                matches.append((card, score, amount, formatted))

    if not matches:
        return "我查了目前公開上架的資料，但沒有找到與「" + safe(term) + "」符合的商品。可以試試其他角色名、日文名稱或卡號喔～"

    # 相關卡片優先展示有庫存的版本；零庫存與未知庫存不能被算成現貨。
    matches.sort(key=lambda item: (item[2] is not None and item[2] > 0,
                                   item[1], item[2] if item[2] is not None else -1), reverse=True)
    stocked = sum(1 for _, _, qty, _ in matches if qty is not None and qty > 0)
    unknown = sum(1 for _, _, qty, _ in matches if qty is None)
    if stocked:
        intro = ("找到與「" + safe(term) + "」相關的 " + str(len(matches))
                 + " 個商品版本，其中 " + str(stocked) + " 個有現貨：")
    elif unknown:
        intro = ("找到與「" + safe(term) + "」相關的 " + str(len(matches))
                 + " 個商品版本，但目前沒有可確認的現貨：")
    else:
        intro = ("找到與「" + safe(term) + "」相關的 " + str(len(matches))
                 + " 個商品版本，目前都顯示沒有現貨：")

    # 輸出長度受 Discord 限制；逐筆保留版本與價格，絕不附內部連結。
    selected = []
    max_rows = 5
    for _, _, _, description in matches:
        if len(selected) >= max_rows:
            break
        draft = intro + "\n\n" + "\n\n".join(selected + [description])
        if len(draft) > 1650:
            break
        selected.append(description)
    result = intro + "\n\n" + "\n\n".join(selected)
    if len(matches) > len(selected) or more:
        result += ("\n\n只列出前 " + str(len(selected))
                   + " 個版本，想縮小範圍可以再給我卡號、版本或更完整的名稱。")
    return result[:1850]
